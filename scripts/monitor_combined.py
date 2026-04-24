"""
混合监控服务 - WebSocket 实时（TOP N）+ HTTP 串行轮询（其余地址）

架构：
  ┌──────────────────────────────────────────────────────────────┐
  │  hl_fragile_pool (monitor_status='active', exit_date IS NULL) │
  │                                                              │
  │  按近7日交易笔数排序                                          │
  │    TOP N  活跃地址 → WebSocket 实时订阅（零延迟）             │
  │    其余地址        → HTTP 串行轮询（≥1000ms 间隔）            │
  └──────────────────────────────────────────────────────────────┘

WebSocket 模式：
  - 订阅 Hyperliquid userFills 频道，成交即推送，无延迟
  - 官方限制：每个 IP 最多 10 个用户级 WS 订阅（TOP_N_WS = 10）
  - 自动重连（断连后 RECONNECT_DELAY 秒）
  - 应用层心跳：每 30s 发送 {"method": "ping"}

HTTP 串行轮询模式：
  - 单协程逐地址顺序拉取 userFillsByTime（增量，不重复）
  - 毫秒级间隔控制：记录上次请求时间戳，距上次 < HTTP_MIN_INTERVAL_MS 则等够再发
  - Hyperliquid 限流：1200 weight/分钟，userFillsByTime weight=20
    → 理论上限 60次/分钟（1次/秒）
    → 默认 HTTP_MIN_INTERVAL_MS=1000，53个地址约 53s 一轮
  - 遇到 429 自动按 HTTP_429_BACKOFF 退避重试（最多3次）
  - 一轮完成后立即开始下一轮，无额外等待

信号处理：
  - WS / HTTP 共用同一套 fill 解析和信号写入逻辑
  - 信号写入 hl_reverse_signals（INSERT IGNORE 去重）
  - 新信号推送飞书（开仓/加仓=🚨红色 / 平仓/减仓=📢蓝色）
  - 信号来源标注：⚡WS 或 🔄HTTP

池子管理：
  - 每 POOL_REFRESH_INTERVAL 秒重新加载 hl_fragile_pool
  - 刷新后 WS/HTTP 分配自动更新（WS 仍用原连接，不重订阅）

依赖表：
  读：hl_fragile_pool, hl_coin_address_features
  写：hl_reverse_signals, hl_fragile_pool.last_fill_time

运行方式：
  python scripts/monitor_combined.py          # 持续运行（推荐 nohup 后台）
  python scripts/monitor_combined.py --once   # HTTP 只跑一轮（调试用）

后台启动：
  nohup venv/bin/python scripts/monitor_combined.py > logs/monitor_combined.log 2>&1 &

查看日志：
  tail -f logs/monitor_combined.log

停止：
  kill <PID>  或  pkill -f monitor_combined.py

关键配置（文件顶部可调）：
  TOP_N_WS              = 10      WS 覆盖的最活跃地址数（官方上限 10）
  HTTP_MIN_INTERVAL_MS  = 1000   两次 HTTP 请求最小间隔（毫秒）
  HTTP_REQUEST_TIMEOUT  = 15     单次请求超时（秒）
  HTTP_429_BACKOFF      = [10,30,60]  429 退避时间序列（秒）
  POOL_REFRESH_INTERVAL = 3600   池子刷新间隔（秒）
"""

import sys
import os
import asyncio
import json
import hashlib
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Set

import httpx
import websockets
import websockets.exceptions

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_connection

# ============================================================
# 配置
# ============================================================
WS_URL               = "wss://api.hyperliquid.xyz/ws"
HL_API_URL           = "https://api.hyperliquid.xyz/info"
LARK_WEBHOOK         = "https://open.larksuite.com/open-apis/bot/v2/hook/b820bda8-4d32-4f11-8530-2dc37bcdcaad"

TOP_N_WS             = 10      # WS 覆盖的最活跃地址数
HTTP_REQUEST_TIMEOUT = 15      # 单次 HTTP 请求超时（秒）
HTTP_MIN_INTERVAL_MS = 1000    # 两次请求之间的最小间隔（毫秒）
HTTP_429_BACKOFF     = [10, 30, 60]  # 429 退避时间序列（秒）
POOL_REFRESH_INTERVAL= 3600    # 池子刷新间隔（秒）
RECONNECT_DELAY      = 5       # WS 断连重连等待（秒）
SUB_SEND_INTERVAL    = 0.05    # WS 订阅请求发送间隔（秒）

# ============================================================
# 日志
# ============================================================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/monitor_combined.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# 共享池子状态（asyncio 单线程，无需锁）
# ============================================================
class PoolState:
    """运行时池子状态，load_pool() 后替换整个对象"""

    def __init__(self):
        # address -> {label, coins: set, scores: {coin: {level, score}}}
        self.data: Dict[str, Dict] = {}
        # WS 负责的地址集合
        self.ws_addresses: Set[str] = set()
        # HTTP 负责的地址集合
        self.http_addresses: Set[str] = set()

    @property
    def all_addresses(self) -> List[str]:
        return list(self.data.keys())


# ============================================================
# 数据库：加载池子
# ============================================================

def load_pool() -> PoolState:
    """
    从 hl_fragile_pool 加载活跃地址，按 recent_7d_trades 排序，
    TOP_N_WS 分配给 WS，其余分配给 HTTP。

    Returns:
        PoolState
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 每个地址最新的 recent_7d_trades 之和，取 TOP N
        cur.execute("""
            SELECT p.address
            FROM hl_fragile_pool p
            INNER JOIN (
                SELECT address, coin, recent_7d_trades,
                       ROW_NUMBER() OVER (PARTITION BY address, coin ORDER BY calculated_at DESC) AS rn
                FROM hl_coin_address_features
            ) cf ON cf.address = p.address AND cf.coin = p.coin AND cf.rn = 1
            WHERE p.monitor_status = 'active' AND p.exit_date IS NULL
            GROUP BY p.address
            ORDER BY SUM(cf.recent_7d_trades) DESC
        """)
        ordered_addresses = [r[0] for r in cur.fetchall()]
        ws_set = set(ordered_addresses[:TOP_N_WS])

        # 加载所有地址的币种 + 评分 + last_fill_time
        cur.execute("""
            SELECT p.address, p.coin, p.label, p.fragile_level, p.total_score,
                   p.last_fill_time
            FROM hl_fragile_pool p
            WHERE p.monitor_status = 'active' AND p.exit_date IS NULL
            ORDER BY p.address, p.coin
        """)
        rows = cur.fetchall()

        state = PoolState()
        for address, coin, label, level, score, last_fill_time in rows:
            if address not in state.data:
                state.data[address] = {
                    "label": label or address[:10],
                    "coins": set(),
                    "scores": {},
                    "last_fill_time": {},   # coin -> last_fill_time_ms
                }
            state.data[address]["coins"].add(coin)
            state.data[address]["scores"][coin] = {
                "level": level or "L3",
                "score": float(score or 0),
            }
            # last_fill_time 按币种存储（同地址不同币种可能不同）
            state.data[address]["last_fill_time"][coin] = last_fill_time

        state.ws_addresses   = {a for a in ordered_addresses[:TOP_N_WS] if a in state.data}
        state.http_addresses = {a for a in state.data if a not in state.ws_addresses}

        total_pairs = sum(len(v["coins"]) for v in state.data.values())
        logger.info(
            f"池子加载完成: 总地址={len(state.data)} "
            f"WS={len(state.ws_addresses)} HTTP={len(state.http_addresses)} "
            f"币种对={total_pairs}"
        )
        return state
    finally:
        cur.close()
        conn.close()


# ============================================================
# 数据库：信号写入 + pool 更新
# ============================================================

def make_signal_id(address: str, fill_hash: Optional[str],
                   fill_time: int, coin: str) -> str:
    raw = f"{address}|{fill_hash or ''}|{fill_time}|{coin}"
    return hashlib.md5(raw.encode()).hexdigest()[:50]


def save_signal(address: str, coin: str, action: str,
                price: float, size: float, side: str,
                fill_time: int, fill_hash: Optional[str]) -> bool:
    """
    写入 hl_reverse_signals，重复跳过。

    Returns:
        True = 新信号，False = 已存在
    """
    type_map = {
        "open":   "new_position",
        "add":    "add_position",
        "close":  "close_position",
        "reduce": "close_position",
    }
    signal_type      = type_map.get(action, "new_position")
    orig_direction   = "long" if side == "B" else "short"
    reverse_direction = "short" if side == "B" else "long"
    signal_id        = make_signal_id(address, fill_hash, fill_time, coin)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT IGNORE INTO hl_reverse_signals (
                signal_id, source_address, coin, signal_type,
                original_direction, original_size, original_price,
                original_fill_time, reverse_direction, reverse_size,
                reverse_weight, signal_status, generated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1.0,'pending',NOW())
        """, (signal_id, address, coin, signal_type,
              orig_direction, size, price,
              fill_time, reverse_direction, size))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"保存信号失败: {e}", exc_info=True)
        return False
    finally:
        cur.close()
        conn.close()


def update_pool_fill_time(address: str, coin: str, fill_time_ms: int) -> None:
    """更新 hl_fragile_pool.last_fill_time"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hl_fragile_pool
               SET last_fill_time = %s, last_monitored_at = NOW()
             WHERE address = %s AND coin = %s AND monitor_status = 'active'
        """, (fill_time_ms, address, coin))
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ============================================================
# 信号解析
# ============================================================

def parse_action(direction: str) -> Optional[str]:
    """
    从 fill.dir 解析动作。

    Returns:
        'open' | 'close' | None
    """
    d = direction.lower()
    if "open" in d:
        return "open"
    if "close" in d:
        return "close"
    return None


# ============================================================
# 飞书推送
# ============================================================

ACTION_EMOJI = {
    ("open",  "B"): ("🔴 开多仓", "💡 反向建议：做空",  "red"),
    ("open",  "A"): ("🔴 开空仓", "💡 反向建议：做多",  "red"),
    ("close", "B"): ("⬜ 平空仓", "💡 反向多仓可考虑止盈", "blue"),
    ("close", "A"): ("⬜ 平多仓", "💡 反向空仓可考虑止盈", "blue"),
    ("add",   "B"): ("🔴 加多仓", "💡 反向建议：加空",  "red"),
    ("add",   "A"): ("🔴 加空仓", "💡 反向建议：加多",  "red"),
    ("reduce","B"): ("⬇️ 减空仓", "💡 反向仓位适当减少", "blue"),
    ("reduce","A"): ("⬇️ 减多仓", "💡 反向仓位适当减少", "blue"),
}


async def send_lark(
    address: str, coin: str, action: str, side: str,
    price: float, size: float, fill_time: int,
    label: str, level: str, score: float,
    source: str,  # "ws" | "http"
    closed_pnl: Optional[float] = None,
    start_position: Optional[float] = None,
) -> None:
    """异步推送飞书消息"""
    key = (action, side)
    action_text, suggest_text, color = ACTION_EMOJI.get(
        key, (f"{action}/{side}", "", "grey")
    )
    is_open = action in ("open", "add")
    # 北京时间 UTC+8
    from datetime import timezone, timedelta
    tz_cst = timezone(timedelta(hours=8))
    time_str = datetime.fromtimestamp(fill_time / 1000, tz=tz_cst).strftime("%Y-%m-%d %H:%M:%S")
    addr_short = f"{address[:6]}...{address[-4:]}"
    source_tag = "⚡WS" if source == "ws" else "🔄HTTP"

    # 附加盈亏和持仓信息
    extra_lines = ""
    if start_position is not None:
        if action in ("close", "reduce"):
            # 平仓/减仓：remaining = |startPosition| - sz
            if closed_pnl is not None:
                pnl_emoji = "🟢" if closed_pnl >= 0 else "🔴"
                extra_lines += f"**已实现盈亏**：{pnl_emoji} {closed_pnl:+.2f} USDC\n"
            remaining = max(abs(start_position) - size, 0.0)
            extra_lines += f"**剩余持仓**：{remaining:.5f} {coin}\n"
        elif action in ("open", "add"):
            # 开仓/加仓：new_position = |startPosition| + sz
            new_pos = abs(start_position) + size
            extra_lines += f"**当前持仓**：{new_pos:.5f} {coin}\n"

    content = (
        f"**地址**：`{addr_short}` ({label})  {source_tag}\n"
        f"**币种**：{coin}  |  **脆弱等级**：{level}（{score:.0f}分）\n"
        f"**动作**：{action_text}\n"
        f"**价格**：{price:.4f}  |  **数量**：{size} {coin}\n"
        f"{extra_lines}"
        f"**时间**：{time_str}（北京时间）\n\n"
        f"{suggest_text}"
    )
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{'🚨 反向信号' if is_open else '📢 平仓提示'} · {coin} · {action_text}",
                },
                "template": color,
            },
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(LARK_WEBHOOK, json=payload)
            resp.raise_for_status()
        logger.info(f"  📨 飞书推送 [{source_tag}]: {addr_short} {coin} {action_text}")
    except Exception as e:
        logger.error(f"  ❌ 飞书推送失败: {e}")


# ============================================================
# 通用：处理一批 fills
# ============================================================

async def process_fills(
    fills: List[dict],
    address: str,
    pool_state: PoolState,
    source: str,
) -> int:
    """
    处理 fill 列表，生成信号并推送。

    Args:
        fills: API 返回的 fill 列表
        address: 地址（WS 模式 fill 里有 user 字段；HTTP 模式外部传入）
        pool_state: 当前池子状态
        source: "ws" | "http"

    Returns:
        新信号数量
    """
    if address not in pool_state.data:
        return 0

    addr_info = pool_state.data[address]
    new_count = 0

    for fill in fills:
        coin           = fill.get("coin", "")
        side           = fill.get("side", "")
        direction      = fill.get("dir", "")
        price          = float(fill.get("px", 0))
        size           = float(fill.get("sz", 0))
        fill_time      = int(fill.get("time", 0))
        fill_hash      = fill.get("hash") or None
        closed_pnl_raw = fill.get("closedPnl")
        start_pos_raw  = fill.get("startPosition")
        closed_pnl     = float(closed_pnl_raw) if closed_pnl_raw is not None else None
        start_position = float(start_pos_raw) if start_pos_raw is not None else None

        # 只处理监控币种
        if coin not in addr_info["coins"]:
            logger.info(f"  [过滤] {address[:10]} coin={coin} dir={direction} side={side} （不在监控列表）")
            continue

        action = parse_action(direction)
        if not action:
            logger.info(f"  [过滤] {address[:10]} coin={coin} dir={direction!r} side={side!r} （无法解析动作）")
            continue

        is_new = save_signal(
            address=address, coin=coin, action=action,
            price=price, size=size, side=side,
            fill_time=fill_time, fill_hash=fill_hash,
        )

        if is_new:
            score_info = addr_info["scores"].get(coin, {})
            await send_lark(
                address=address, coin=coin, action=action, side=side,
                price=price, size=size, fill_time=fill_time,
                label=addr_info["label"],
                level=score_info.get("level", "L3"),
                score=score_info.get("score", 0.0),
                source=source,
                closed_pnl=closed_pnl,
                start_position=start_position,
            )
            # 更新内存中的 last_fill_time（减少重复拉取）
            old = addr_info["last_fill_time"].get(coin) or 0
            if fill_time > old:
                addr_info["last_fill_time"][coin] = fill_time
                update_pool_fill_time(address, coin, fill_time)
            new_count += 1

    return new_count


# ============================================================
# WebSocket 分片
# ============================================================

async def run_ws_shard(
    shard_id: int,
    addresses: List[str],
    pool_state: PoolState,
    pool_ref: list,       # pool_ref[0] 是最新 PoolState，供热刷新
) -> None:
    """
    运行 WS 分片，断连自动重连。
    pool_ref[0] 始终指向最新池子，fill 处理时从中取数据。
    """
    while True:
        try:
            logger.info(f"[WS分片{shard_id}] 连接中... ({len(addresses)} 个地址)")
            async with websockets.connect(
                WS_URL,
                ping_interval=None,
                close_timeout=5,
                open_timeout=15,
            ) as ws:
                logger.info(f"[WS分片{shard_id}] 已连接，发送订阅...")

                for addr in addresses:
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {
                            "type": "userFills",
                            "user": addr,
                            "aggregateByTime": True,
                        },
                    }))
                    await asyncio.sleep(SUB_SEND_INTERVAL)

                confirmed = 0

                # 应用层心跳
                async def heartbeat():
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send(json.dumps({"method": "ping"}))
                        except Exception:
                            break

                hb_task = asyncio.create_task(heartbeat())

                try:
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            continue
                        if raw == "ping":
                            await ws.send("pong")
                            continue
                        if not raw.startswith("{"):
                            logger.debug(f"[WS分片{shard_id}] 非JSON: {repr(raw[:80])}")
                            continue

                        msg     = json.loads(raw)
                        channel = msg.get("channel", "")

                        if channel == "subscriptionResponse":
                            confirmed += 1
                            if confirmed == len(addresses):
                                logger.info(f"[WS分片{shard_id}] ✅ {confirmed} 个订阅已确认")

                        elif channel == "userFills":
                            data        = msg.get("data", {})
                            is_snapshot = data.get("isSnapshot", False)
                            user        = data.get("user", "")
                            fills       = data.get("fills", [])

                            if is_snapshot:
                                continue  # 跳过历史快照

                            if fills:
                                logger.info(
                                    f"[WS分片{shard_id}] 📩 {user[:10]}... "
                                    f"fills={len(fills)}"
                                )
                                # 注入 user 字段
                                for f in fills:
                                    f["user"] = user
                                await process_fills(fills, user, pool_ref[0], "ws")

                        elif channel == "error":
                            logger.warning(f"[WS分片{shard_id}] ⚠️ 错误: {msg.get('data')}")
                finally:
                    hb_task.cancel()

        except websockets.exceptions.ConnectionClosedOK as e:
            logger.warning(f"[WS分片{shard_id}] 正常关闭 code={e.code}，{RECONNECT_DELAY}s 后重连")
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"[WS分片{shard_id}] 异常断开 code={e.code}，{RECONNECT_DELAY}s 后重连")
        except Exception as e:
            logger.error(f"[WS分片{shard_id}] 异常: {type(e).__name__}: {e}，{RECONNECT_DELAY}s 后重连")

        await asyncio.sleep(RECONNECT_DELAY)


# ============================================================
# HTTP 串行轮询（单协程，毫秒级间隔控制）
# ============================================================

import time as _time


async def http_fetch_fills(
    client: httpx.AsyncClient,
    address: str,
    start_time_ms: int,
) -> List[dict]:
    """
    拉取单地址增量 fills。
    遇到 429 按退避时间序列重试。
    """
    backoff_seq = [0] + HTTP_429_BACKOFF
    for attempt in range(len(backoff_seq)):
        extra_backoff = backoff_seq[attempt]
        if extra_backoff:
            logger.warning(f"  [HTTP] 429 退避 {extra_backoff}s {address[:10]}...（第{attempt}次重试）")
            await asyncio.sleep(extra_backoff)
        try:
            resp = await client.post(
                HL_API_URL,
                json={
                    "type": "userFillsByTime",
                    "user": address,
                    "startTime": start_time_ms,
                    "aggregateByTime": True,
                },
                timeout=HTTP_REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", HTTP_429_BACKOFF[min(attempt, len(HTTP_429_BACKOFF)-1)]))
                logger.warning(f"  [HTTP] 429 {address[:10]}... Retry-After={wait}s，等待后重试")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json() or []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # raise_for_status() 抛出的 429，使用 backoff_seq 下一档等待
                wait = HTTP_429_BACKOFF[min(attempt, len(HTTP_429_BACKOFF)-1)]
                logger.warning(f"  [HTTP] 429(exc) {address[:10]}... 等待 {wait}s 后重试")
                await asyncio.sleep(wait)
                continue
            logger.warning(f"  [HTTP] 请求失败 {address[:10]}...: {e}")
            return []
        except Exception as e:
            logger.warning(f"  [HTTP] 请求失败 {address[:10]}...: {e}")
            return []
    logger.error(f"  [HTTP] {address[:10]}... 重试耗尽，跳过")
    return []


async def run_http_poll(pool_ref: list, once: bool = False) -> None:
    """
    HTTP 串行轮询：单协程逐个地址处理。

    毫秒级间隔控制：记录上次请求发出的毫秒时间戳，
    下次请求前等待至距上次 >= HTTP_MIN_INTERVAL_MS 再发出。
    """
    n_addrs = len(pool_ref[0].http_addresses)
    logger.info(
        f"[HTTP] 启动串行轮询 间隔={HTTP_MIN_INTERVAL_MS}ms "
        f"预计每轮耗时≥{n_addrs * HTTP_MIN_INTERVAL_MS / 1000:.0f}s"
    )

    last_req_ms: int = 0   # 上次请求发出的毫秒时间戳
    round_num: int = 0

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=2),
    ) as client:
        while True:
            http_addrs = list(pool_ref[0].http_addresses)

            if not http_addrs:
                logger.info("[HTTP] 无 HTTP 地址，等待 10s...")
                await asyncio.sleep(10)
                continue

            round_start_ms = int(_time.time() * 1000)

            for address in http_addrs:
                pool_state = pool_ref[0]
                if address not in pool_state.data:
                    continue

                addr_info = pool_state.data[address]

                # 计算起始时间
                min_last_fill: Optional[int] = None
                for coin in addr_info["coins"]:
                    lft = addr_info["last_fill_time"].get(coin)
                    if lft is None:
                        min_last_fill = None
                        break
                    if min_last_fill is None or lft < min_last_fill:
                        min_last_fill = lft

                if min_last_fill is None:
                    start_ms = int(_time.time() * 1000) - 60_000
                else:
                    start_ms = min_last_fill + 1

                # 毫秒级间隔控制：距上次请求未满 HTTP_MIN_INTERVAL_MS 就等
                now_ms = int(_time.time() * 1000)
                elapsed_since_last = now_ms - last_req_ms
                if elapsed_since_last < HTTP_MIN_INTERVAL_MS:
                    wait_ms = HTTP_MIN_INTERVAL_MS - elapsed_since_last
                    await asyncio.sleep(wait_ms / 1000)

                # 记录发出时间（发出请求前记录）
                last_req_ms = int(_time.time() * 1000)
                fills = await http_fetch_fills(client, address, start_ms)
                # 429 重试会耗费较长时间，退避结束后重置时间戳确保下一个地址仍有间隔
                last_req_ms = int(_time.time() * 1000)

                if fills:
                    new_count = await process_fills(fills, address, pool_state, "http")
                    if new_count:
                        logger.info(
                            f"  [HTTP] {addr_info['label']} 新信号 {new_count} 条"
                        )

            round_elapsed = (int(_time.time() * 1000) - round_start_ms) / 1000
            round_num += 1
            logger.info(
                f"[HTTP] 第 {round_num} 轮完成: "
                f"{len(http_addrs)} 个地址，耗时 {round_elapsed:.1f}s"
            )

            if once:
                break


# ============================================================
# 池子刷新
# ============================================================

async def pool_refresh_loop(pool_ref: list) -> None:
    """定期刷新池子，替换 pool_ref[0]"""
    while True:
        await asyncio.sleep(POOL_REFRESH_INTERVAL)
        logger.info("🔄 刷新池子数据...")
        try:
            new_state = load_pool()
            pool_ref[0] = new_state
            logger.info(
                f"🔄 池子已更新: WS={len(new_state.ws_addresses)} "
                f"HTTP={len(new_state.http_addresses)}"
            )
        except Exception as e:
            logger.error(f"🔄 池子刷新失败: {e}", exc_info=True)


# ============================================================
# 飞书：启动通知
# ============================================================

async def send_lark_text(text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(LARK_WEBHOOK, json={
                "msg_type": "text",
                "content": {"text": text},
            })
    except Exception as e:
        logger.error(f"飞书文本推送失败: {e}")


# ============================================================
# 主入口
# ============================================================

async def run(once: bool = False) -> None:
    logger.info("=" * 60)
    logger.info("混合监控服务启动（WS + HTTP 并发）")
    logger.info("=" * 60)

    pool_state = load_pool()
    if not pool_state.data:
        logger.error("❌ 池子为空，请先运行 update_fragile_pool.py")
        return

    # pool_ref 是可变容器，所有协程共享同一引用，刷新时只替换 pool_ref[0]
    pool_ref = [pool_state]

    ws_addresses   = list(pool_state.ws_addresses)
    http_addresses = list(pool_state.http_addresses)

    logger.info(
        f"WS 地址: {len(ws_addresses)} 个 | "
        f"HTTP 地址: {len(http_addresses)} 个 | "
        f"HTTP 间隔: {HTTP_MIN_INTERVAL_MS}ms"
    )

    tasks = []

    # WS 任务（只在有 WS 地址时启动）
    if ws_addresses:
        tasks.append(
            asyncio.create_task(run_ws_shard(1, ws_addresses, pool_state, pool_ref))
        )

    # HTTP 轮询任务
    if http_addresses or not ws_addresses:
        tasks.append(
            asyncio.create_task(run_http_poll(pool_ref, once=once))
        )

    # 池子刷新任务（only=False 时才需要）
    if not once:
        tasks.append(asyncio.create_task(pool_refresh_loop(pool_ref)))

    # 启动通知
    total_pairs = sum(len(v["coins"]) for v in pool_state.data.values())
    await send_lark_text(
        f"✅ 混合监控服务已启动\n"
        f"⚡ WS 地址: {len(ws_addresses)} 个\n"
        f"🔄 HTTP 地址: {len(http_addresses)} 个（间隔={HTTP_MIN_INTERVAL_MS}ms）\n"
        f"📊 总监控币种对: {total_pairs} 个"
    )

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("监控服务已停止")


def main() -> None:
    parser = argparse.ArgumentParser(description="混合监控服务（WS + HTTP）")
    parser.add_argument("--once", action="store_true", help="HTTP 轮询只跑一轮（调试用）")
    args = parser.parse_args()

    try:
        asyncio.run(run(once=args.once))
    except KeyboardInterrupt:
        logger.info("用户中断，服务退出")


if __name__ == "__main__":
    main()
