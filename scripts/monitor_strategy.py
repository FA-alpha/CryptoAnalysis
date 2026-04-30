"""
策略版监控服务（strategy-aware）

架构：
  - 独立进程，独立于 API 服务运行
  - 从 hl_strategy_addresses 加载所有活跃策略的地址+币种对（合并去重）
  - HTTP 串行轮询（与 monitor_combined.py 相同节奏，1000ms 间隔）
  - 发现信号后：
      1. 写入 hl_reverse_signals（含 strategy_id）
      2. TODO: 写入 Redis（key=signals:{strategy_id}，由 redis_publisher 实现）
  - 每 STRATEGY_RELOAD_INTERVAL 秒重新加载策略配置（感知 start/stop 变化）

信号不推送飞书（由各策略的交易执行服务自行处理）

运行方式：
  python scripts/monitor_strategy.py          # 持续运行
  python scripts/monitor_strategy.py --once   # 只跑一轮（调试用）

后台启动：
  nohup venv/bin/python scripts/monitor_strategy.py > logs/monitor_strategy.log 2>&1 &

停止：
  kill <PID>  或  pkill -f monitor_strategy.py
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time as _time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import httpx
import pymysql.cursors

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_connection
from utils.signal_producer import send_signal

# ============================================================
# 配置
# ============================================================
HL_API_URL               = "https://api.hyperliquid.xyz/info"
HTTP_REQUEST_TIMEOUT     = 15        # 单次请求超时（秒）
HTTP_MIN_INTERVAL_MS     = 900      # 两次请求最小间隔（毫秒）
HTTP_429_BACKOFF         = [10, 30, 60]
STRATEGY_RELOAD_INTERVAL = 60        # 策略配置重新加载间隔（秒）
FILL_LOOKBACK_MS         = 300_000   # 无 last_fill_time 时的回退窗口（毫秒）

# ============================================================
# 日志
# ============================================================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/monitor_strategy.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
# 降噪：关闭 httpx/httpcore 成功请求 INFO 日志，仅保留 warning/error
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ============================================================
# 策略池状态（所有活跃策略合并）
# ============================================================

class StrategyPoolState:
    """
    运行时策略池状态。

    核心数据结构：
      address_coin_strategies: {(address, coin) -> set of strategy_ids}
        — 某个 address+coin 对被哪些策略监控

      addr_info: {address -> {coins, last_fill_time: ms | None}}
        — 地址运行时状态（last_fill_time 来自 hl_monitor_cursors 初始化，运行时更新）
    """

    def __init__(self) -> None:
        # (address, coin) -> set[strategy_id]
        self.address_coin_strategies: Dict[Tuple[str, str], Set[str]] = {}
        # address -> {coins: set, last_fill_time: ms | None}
        self.addr_info: Dict[str, Dict] = {}
        # strategy_id -> {"single_addr_limit_pct": float|None, "coin_symbol_map": {coin: symbol}}
        self.strategy_params: Dict[str, Dict] = {}

    @property
    def all_addresses(self) -> List[str]:
        return list(self.addr_info.keys())

    @property
    def total_pairs(self) -> int:
        return len(self.address_coin_strategies)


# ============================================================
# 加载策略池
# ============================================================

def load_strategy_pool() -> StrategyPoolState:
    """
    从 hl_strategy_addresses 加载所有活跃策略的地址+币种对。

    游标表 `hl_monitor_cursors` 为 address-only：
      - 同一 address 的 last_fill_time 对所有 coins 共用。

    Returns:
        StrategyPoolState
    """
    conn = get_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # 先确保所有 active 的 address 在游标表里存在
        cur.execute("""
            INSERT IGNORE INTO hl_monitor_cursors (address, last_fill_time)
            SELECT DISTINCT sa.address, NULL
            FROM hl_strategy_addresses sa
            JOIN hl_strategies s ON sa.strategy_id = s.strategy_id
            WHERE s.status = 'active'
              AND sa.excluded_at IS NULL
        """)
        conn.commit()

        cur.execute("""
            SELECT
                sa.strategy_id,
                sa.address,
                sa.coin,
                sa.score,
                sa.level,
                mc.last_fill_time,
                s.filter_params
            FROM hl_strategy_addresses sa
            JOIN hl_strategies s ON sa.strategy_id = s.strategy_id
            LEFT JOIN hl_monitor_cursors mc
                ON sa.address = mc.address
            WHERE s.status = 'active'
              AND sa.excluded_at IS NULL
            ORDER BY sa.address, sa.coin
        """)
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    state = StrategyPoolState()

    for row in rows:
        addr = row["address"]
        coin = row["coin"]
        sid  = row["strategy_id"]
        lft  = row["last_fill_time"]  # 可能为 None（来自 hl_monitor_cursors）

        # address_coin_strategies
        key = (addr, coin)
        if key not in state.address_coin_strategies:
            state.address_coin_strategies[key] = set()
        state.address_coin_strategies[key].add(sid)

        # addr_info
        if addr not in state.addr_info:
            state.addr_info[addr] = {
                "coins": set(),
                "last_fill_time": None,
            }
        state.addr_info[addr]["coins"].add(coin)

        # last_fill_time：address-only，直接赋值（不同 coin 下值相同）
        if state.addr_info[addr]["last_fill_time"] is None and lft is not None:
            state.addr_info[addr]["last_fill_time"] = lft

        # 策略参数：透传执行层使用（单地址投入上限比例 + coin->symbol 映射）
        if sid not in state.strategy_params:
            single_addr_limit_pct = None
            coin_symbol_map: Dict[str, str] = {}
            fp_raw = row.get("filter_params")
            if fp_raw:
                try:
                    fp_obj = json.loads(fp_raw) if isinstance(fp_raw, str) else fp_raw
                    v = fp_obj.get("single_addr_limit_pct")
                    if v is not None:
                        single_addr_limit_pct = float(v)

                    # tracked_coins: {COIN: "COIN/USDT:USDT"} 或 [{COIN: "..."}]
                    tracked = fp_obj.get("tracked_coins")
                    if isinstance(tracked, dict):
                        coin_symbol_map = {str(k): str(val) for k, val in tracked.items()}
                    elif isinstance(tracked, list):
                        for item in tracked:
                            if isinstance(item, dict) and len(item) == 1:
                                (k, val), = item.items()
                                coin_symbol_map[str(k)] = str(val)
                except Exception:
                    # 参数解析失败不阻断主流程
                    pass
            state.strategy_params[sid] = {
                "single_addr_limit_pct": single_addr_limit_pct,
                "coin_symbol_map": coin_symbol_map,
            }

    active_strategies = {
        sid
        for sids in state.address_coin_strategies.values()
        for sid in sids
    }
    logger.info(
        "策略池加载完成: 活跃策略=%d, 地址=%d, 币种对=%d",
        len(active_strategies),
        len(state.addr_info),
        state.total_pairs,
    )
    return state


def upsert_monitor_cursors(updates: List[Tuple[str, int]]) -> None:
    """
    批量更新全局游标表（address）。
    仅前进不回退：写入值与现有值取较大者。
    """
    if not updates:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO hl_monitor_cursors (address, last_fill_time)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                last_fill_time = CASE
                    WHEN last_fill_time IS NULL THEN VALUES(last_fill_time)
                    ELSE GREATEST(last_fill_time, VALUES(last_fill_time))
                END
            """,
            updates,
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning("更新 hl_monitor_cursors 失败: %s", e)
    finally:
        cur.close()
        conn.close()


# ============================================================
# 信号写入
# ============================================================

def make_signal_id(
    strategy_id: str,
    address: str,
    fill_hash: Optional[str],
    fill_time: int,
    coin: str,
) -> str:
    """生成信号唯一ID（含 strategy_id，保证同一 fill 对不同策略产生不同 signal_id）"""
    raw = f"{strategy_id}|{address}|{fill_hash or ''}|{fill_time}|{coin}"
    return hashlib.md5(raw.encode()).hexdigest()[:50]


def save_signal(
    strategy_id: str,
    address: str,
    coin: str,
    action: str,
    price: float,
    size: float,
    side: str,
    fill_time: int,
    fill_hash: Optional[str],
) -> Tuple[bool, str]:
    """
    写入 hl_reverse_signals（含 strategy_id），重复跳过。

    Returns:
        (是否新信号, signal_id)
    """
    type_map = {
        "open":   "new_position",
        "add":    "add_position",
        "close":  "close_position",
        "reduce": "close_position",
    }
    signal_type       = type_map.get(action, "new_position")
    orig_direction    = "long" if side == "B" else "short"
    reverse_direction = "short" if side == "B" else "long"
    signal_id         = make_signal_id(strategy_id, address, fill_hash, fill_time, coin)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT IGNORE INTO hl_reverse_signals (
                signal_id, strategy_id, source_address, coin, signal_type,
                original_direction, original_size, original_price,
                original_fill_time, reverse_direction, reverse_size,
                reverse_weight, signal_status, generated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1.0,'pending',NOW())
            """,
            (
                signal_id, strategy_id, address, coin, signal_type,
                orig_direction, size, price,
                fill_time, reverse_direction, size,
            ),
        )
        conn.commit()
        inserted = cur.rowcount > 0
        if inserted:
            logger.info(
                "新信号: strategy=%s addr=%s...%s coin=%s action=%s price=%.4f",
                strategy_id,
                address[:6],
                address[-4:],
                coin,
                action,
                price,
            )
        return inserted, signal_id
    except Exception as e:
        conn.rollback()
        logger.error("保存信号失败: %s", e, exc_info=True)
        return False, signal_id
    finally:
        cur.close()
        conn.close()


def publish_to_redis(strategy_id: str, signal_data: dict) -> None:
    """
    将信号写入 Redis Stream（fa:signal）。
    """
    action = str(signal_data.get("action", "")).lower()
    side = str(signal_data.get("side", "")).upper()
    symbol = str(signal_data.get("symbol", "")).strip()
    signal_id = str(signal_data.get("signal_id", "")).strip()

    # action + side -> 执行层 signal_type（基于反向策略语义）
    signal_type = None
    if action == "open" and side == "B":
        signal_type = "entry_short"
    elif action == "open" and side == "A":
        signal_type = "entry_long"
    elif action == "close" and side == "B":
        signal_type = "exit_short"
    elif action == "close" and side == "A":
        signal_type = "exit_long"

    if not signal_type or not symbol or not signal_id:
        logger.warning(
            "Redis信号跳过: strategy=%s signal_id=%s action=%s side=%s symbol=%s",
            strategy_id,
            signal_id,
            action,
            side,
            symbol,
        )
        return

    data = {
        "address": signal_data.get("address"),
        "price": signal_data.get("price"),
        "size": signal_data.get("size"),
        "fill_time": signal_data.get("fill_time"),
        "generated_at": signal_data.get("generated_at"),
    }
    message_id = send_signal(
        strategy_id=strategy_id,
        symbol=symbol,
        signal_type=signal_type,
        signal_id=signal_id,
        data=data,
    )
    if message_id:
        logger.info(
            "Redis信号已发送: strategy=%s signal_id=%s message_id=%s type=%s",
            strategy_id,
            signal_id,
            message_id,
            signal_type,
        )


def query_current_margin_used(strategy_id: str, source_address: str, coin: str) -> float:
    """
    查询当前 strategy+address+coin 已占用保证金（来自 hl_follow_trades.margin_used）。

    说明：
      - 仅 SUM(margin_used)；callback 写入前该字段可能全为 NULL，汇总结果为 0。
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(margin_used), 0)
            FROM hl_follow_trades
            WHERE strategy_id = %s
              AND source_address = %s
              AND coin = %s
              AND trade_status = 'open'
            """,
            (strategy_id, source_address, coin),
        )
        row = cur.fetchone()
        return float(row[0] or 0)
    except Exception as e:
        logger.warning(
            "查询当前 margin_used 失败: strategy=%s addr=%s...%s coin=%s err=%s",
            strategy_id,
            source_address[:6],
            source_address[-4:],
            coin,
            e,
        )
        return 0.0
    finally:
        cur.close()
        conn.close()


# ============================================================
# Fill 解析
# ============================================================

def parse_action(direction: str) -> Optional[str]:
    """
    从 fill.dir 解析动作类型。

    Returns:
        'open' | 'close' | None
    """
    d = direction.lower()
    if "open" in d:
        return "open"
    if "close" in d:
        return "close"
    # 爆仓也按平仓信号处理（例如：Liquidated Cross/Isolated Long/Short）
    if "liquidated" in d:
        return "close"
    return None


# ============================================================
# 处理一批 fills
# ============================================================

async def process_fills(
    fills: List[dict],
    address: str,
    pool_state: StrategyPoolState,
) -> int:
    """
    处理 fill 列表，按 address+coin 批内汇总后再生成信号。

    汇总规则（单个 coin）：
      - 统计 open_count / close_count
      - close_count > open_count => 生成 close
      - open_count > close_count => 生成 open
      - 二者相等 => 跳过（方向不明确）
      - price/size/side/fill_time/fill_hash 取“胜出方向”里最新一笔

    Args:
        fills: API 返回的 fill 列表
        address: 地址
        pool_state: 当前策略池状态

    Returns:
        新信号数量（跨所有策略）
    """
    if address not in pool_state.addr_info:
        return 0

    addr_info = pool_state.addr_info[address]
    new_count = 0

    # coin -> 聚合结果
    coin_agg: Dict[str, Dict] = {}

    for fill in fills:
        coin = str(fill.get("coin", "")).strip()
        if coin not in addr_info["coins"]:
            continue

        direction = str(fill.get("dir", ""))
        action = parse_action(direction)
        if not action:
            logger.debug(
                "跳过无法解析的 fill: addr=%s coin=%s dir=%r",
                address[:10],
                coin,
                direction,
            )
            continue

        fill_time = int(fill.get("time", 0))
        item = {
            "side": str(fill.get("side", "")),
            "price": float(fill.get("px", 0)),
            "size": float(fill.get("sz", 0)),
            "fill_time": fill_time,
            "fill_hash": fill.get("hash") or None,
        }

        if coin not in coin_agg:
            coin_agg[coin] = {
                "open_count": 0,
                "close_count": 0,
                "latest_open": None,
                "latest_close": None,
                "max_fill_time": 0,
            }
        agg = coin_agg[coin]
        agg["max_fill_time"] = max(agg["max_fill_time"], fill_time)

        if action == "open":
            agg["open_count"] += 1
            latest_open = agg["latest_open"]
            if latest_open is None or item["fill_time"] >= latest_open["fill_time"]:
                agg["latest_open"] = item
        else:
            agg["close_count"] += 1
            latest_close = agg["latest_close"]
            if latest_close is None or item["fill_time"] >= latest_close["fill_time"]:
                agg["latest_close"] = item

    for coin, agg in coin_agg.items():
        open_count = int(agg["open_count"])
        close_count = int(agg["close_count"])

        if open_count == close_count:
            logger.info(
                "[HTTP] 汇总后跳过: addr=%s...%s coin=%s open=%d close=%d",
                address[:6],
                address[-4:],
                coin,
                open_count,
                close_count,
            )
            continue

        action = "open" if open_count > close_count else "close"
        selected = agg["latest_open"] if action == "open" else agg["latest_close"]
        if not selected:
            continue

        logger.info(
            "[HTTP] 汇总结果: addr=%s...%s coin=%s action=%s open=%d close=%d price=%.6f size=%.8f",
            address[:6],
            address[-4:],
            coin,
            action,
            open_count,
            close_count,
            float(selected["price"]),
            float(selected["size"]),
        )

        # 获取关注这个 (address, coin) 的所有策略
        strategy_ids = pool_state.address_coin_strategies.get((address, coin), set())
        if not strategy_ids:
            continue

        for strategy_id in strategy_ids:
            current_margin_used = query_current_margin_used(
                strategy_id=strategy_id,
                source_address=address,
                coin=coin,
            )
            strategy_cfg = pool_state.strategy_params.get(strategy_id, {})
            is_new, signal_id = save_signal(
                strategy_id=strategy_id,
                address=address,
                coin=coin,
                action=action,
                price=float(selected["price"]),
                size=float(selected["size"]),
                side=str(selected["side"]),
                fill_time=int(selected["fill_time"]),
                fill_hash=selected["fill_hash"],
            )
            if is_new:
                signal_data = {
                    "signal_id": signal_id,
                    "strategy_id": strategy_id,
                    "address": address,
                    "symbol": (strategy_cfg.get("coin_symbol_map") or {}).get(
                        coin, f"{coin}/USDT:USDT"
                    ),
                    "action": action,
                    "side": str(selected["side"]),
                    "price": float(selected["price"]),
                    "size": float(selected["size"]),
                    "fill_time": int(selected["fill_time"]),
                    "current_margin_used": current_margin_used,
                    # 新口径：按 strategy+address+coin 暴露控制
                    "max_alloc_pct_per_address_coin": strategy_cfg.get("single_addr_limit_pct"),
                    "generated_at": datetime.now().isoformat(),
                }
                publish_to_redis(strategy_id, signal_data)
                new_count += 1

    return new_count


# ============================================================
# HTTP 拉取 fills
# ============================================================

async def http_fetch_fills(
    client: httpx.AsyncClient,
    address: str,
    start_time_ms: int,
) -> Optional[List[dict]]:
    """
    拉取单地址增量 fills（userFillsByTime）。
    遇到 429 按退避序列重试。
    """
    backoff_seq = [0] + HTTP_429_BACKOFF
    for attempt in range(len(backoff_seq)):
        wait = backoff_seq[attempt]
        if wait:
            logger.warning(
                "[HTTP] 429 退避 %ds addr=%s（第%d次重试）",
                wait,
                address[:10],
                attempt,
            )
            await asyncio.sleep(wait)
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
                retry_after = int(
                    resp.headers.get(
                        "Retry-After",
                        HTTP_429_BACKOFF[min(attempt, len(HTTP_429_BACKOFF) - 1)],
                    )
                )
                logger.warning(
                    "[HTTP] 429 addr=%s Retry-After=%ds",
                    address[:10],
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            fills = resp.json() or []
            if fills:
                preview = [
                    {
                        "coin": f.get("coin"),
                        "dir": f.get("dir"),
                        "side": f.get("side"),
                        "size": f.get("sz"),
                        "time": f.get("time"),
                    }
                    for f in fills[:3]
                ]
                logger.info(
                    "[HTTP] fills返回 addr=%s...%s count=%d preview=%s",
                    address[:6],
                    address[-4:],
                    len(fills),
                    preview,
                )
            return fills
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                w = HTTP_429_BACKOFF[min(attempt, len(HTTP_429_BACKOFF) - 1)]
                await asyncio.sleep(w)
                continue
            logger.warning("[HTTP] 请求失败 addr=%s: %s", address[:10], e)
            return None
        except Exception as e:
            logger.warning("[HTTP] 请求失败 addr=%s: %s", address[:10], e)
            return None

    logger.error("[HTTP] addr=%s 重试耗尽，跳过", address[:10])
    return None


# ============================================================
# HTTP 串行轮询
# ============================================================

async def run_http_poll(pool_ref: list, once: bool = False) -> None:
    """
    HTTP 串行轮询，与 monitor_combined.py 逻辑一致。
    pool_ref[0] 由 strategy_reload_loop 定期替换。
    """
    logger.info(
        "[HTTP] 启动串行轮询 间隔=%dms",
        HTTP_MIN_INTERVAL_MS,
    )

    last_req_ms: int = 0
    round_num: int = 0

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=2),
    ) as client:
        while True:
            pool_state: StrategyPoolState = pool_ref[0]
            all_addrs = pool_state.all_addresses

            if not all_addrs:
                logger.info("[HTTP] 无监控地址，等待 10s...")
                await asyncio.sleep(10)
                if once:
                    break
                continue

            round_start_ms = int(_time.time() * 1000)
            logger.info("[HTTP] 开始轮询地址中... 本轮地址=%d", len(all_addrs))

            for address in all_addrs:
                pool_state = pool_ref[0]
                if address not in pool_state.addr_info:
                    continue

                addr_info = pool_state.addr_info[address]

                # 起始时间：address-only cursor
                lft = addr_info["last_fill_time"]
                now_ms = int(_time.time() * 1000)
                start_ms = (lft + 1) if lft is not None else (now_ms - FILL_LOOKBACK_MS)

                # 毫秒间隔控制
                elapsed = now_ms - last_req_ms
                if elapsed < HTTP_MIN_INTERVAL_MS:
                    await asyncio.sleep((HTTP_MIN_INTERVAL_MS - elapsed) / 1000)

                last_req_ms = int(_time.time() * 1000)
                fills = await http_fetch_fills(client, address, start_ms)
                last_req_ms = int(_time.time() * 1000)

                if fills is None:
                    continue

                # 请求成功：保存 address 级最新时间（不依赖 fills 是否为空）
                cursor_now_ms = int(_time.time() * 1000)
                addr_info["last_fill_time"] = cursor_now_ms
                upsert_monitor_cursors([(address, cursor_now_ms)])

                if fills:
                    new_cnt = await process_fills(fills, address, pool_state)
                    if new_cnt:
                        logger.info(
                            "[HTTP] addr=%s...%s 新信号 %d 条",
                            address[:6],
                            address[-4:],
                            new_cnt,
                        )

            round_elapsed = (int(_time.time() * 1000) - round_start_ms) / 1000
            round_num += 1
            logger.info(
                "[HTTP] 第 %d 轮完成: %d 地址 耗时=%.1fs",
                round_num,
                len(all_addrs),
                round_elapsed,
            )

            if once:
                break


# ============================================================
# 策略配置定时 reload
# ============================================================

async def strategy_reload_loop(pool_ref: list) -> None:
    """定期重新加载策略池，替换 pool_ref[0]"""
    while True:
        await asyncio.sleep(STRATEGY_RELOAD_INTERVAL)
        logger.info("🔄 重新加载策略池...")
        try:
            new_state = load_strategy_pool()
            pool_ref[0] = new_state
            logger.info(
                "🔄 策略池已更新: 地址=%d 币种对=%d",
                len(new_state.addr_info),
                new_state.total_pairs,
            )
        except Exception as e:
            logger.error("🔄 策略池重新加载失败: %s", e, exc_info=True)


# ============================================================
# 主入口
# ============================================================

async def run(once: bool = False) -> None:
    logger.info("=" * 60)
    logger.info("策略版监控服务启动")
    logger.info("=" * 60)

    pool_state = load_strategy_pool()
    if not pool_state.addr_info:
        logger.warning("⚠️  当前无活跃策略地址，服务继续运行，等待策略启动...")

    pool_ref = [pool_state]

    logger.info(
        "监控地址: %d 个 | 总币种对: %d | 策略 reload 间隔: %ds",
        len(pool_state.addr_info),
        pool_state.total_pairs,
        STRATEGY_RELOAD_INTERVAL,
    )

    tasks = [asyncio.create_task(run_http_poll(pool_ref, once=once))]
    if not once:
        tasks.append(asyncio.create_task(strategy_reload_loop(pool_ref)))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("监控服务已停止")


def main() -> None:
    parser = argparse.ArgumentParser(description="策略版监控服务")
    parser.add_argument("--once", action="store_true", help="只跑一轮（调试用）")
    args = parser.parse_args()

    try:
        asyncio.run(run(once=args.once))
    except KeyboardInterrupt:
        logger.info("用户中断，服务退出")


if __name__ == "__main__":
    main()
