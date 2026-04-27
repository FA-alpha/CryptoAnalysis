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

# ============================================================
# 配置
# ============================================================
HL_API_URL               = "https://api.hyperliquid.xyz/info"
HTTP_REQUEST_TIMEOUT     = 15        # 单次请求超时（秒）
HTTP_MIN_INTERVAL_MS     = 1000      # 两次请求最小间隔（毫秒）
HTTP_429_BACKOFF         = [10, 30, 60]
STRATEGY_RELOAD_INTERVAL = 60        # 策略配置重新加载间隔（秒）

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


# ============================================================
# 策略池状态（所有活跃策略合并）
# ============================================================

class StrategyPoolState:
    """
    运行时策略池状态。

    核心数据结构：
      address_coin_strategies: {(address, coin) -> set of strategy_ids}
        — 某个 address+coin 对被哪些策略监控

      addr_info: {address -> {coins, last_fill_time: {coin -> ms}}}
        — 地址运行时状态（last_fill_time 来自 hl_strategy_addresses 初始化，运行时更新）
    """

    def __init__(self) -> None:
        # (address, coin) -> set[strategy_id]
        self.address_coin_strategies: Dict[Tuple[str, str], Set[str]] = {}
        # address -> {coins: set, last_fill_time: {coin: ms | None}}
        self.addr_info: Dict[str, Dict] = {}

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

    合并规则：多个策略监控同一 (address, coin) 时合并为一条监控记录，
    last_fill_time 取最小值（保守起点，避免漏信号）。

    Returns:
        StrategyPoolState
    """
    conn = get_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT
                sa.strategy_id,
                sa.address,
                sa.coin,
                sa.score,
                sa.level,
                fp.last_fill_time
            FROM hl_strategy_addresses sa
            JOIN hl_strategies s ON sa.strategy_id = s.strategy_id
            LEFT JOIN hl_fragile_pool fp
                ON sa.address = fp.address AND sa.coin = fp.coin
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
        lft  = row["last_fill_time"]  # 可能为 None

        # address_coin_strategies
        key = (addr, coin)
        if key not in state.address_coin_strategies:
            state.address_coin_strategies[key] = set()
        state.address_coin_strategies[key].add(sid)

        # addr_info
        if addr not in state.addr_info:
            state.addr_info[addr] = {
                "coins": set(),
                "last_fill_time": {},
            }
        state.addr_info[addr]["coins"].add(coin)

        # last_fill_time：多策略时取最小值（保守）
        existing_lft = state.addr_info[addr]["last_fill_time"].get(coin)
        if existing_lft is None:
            state.addr_info[addr]["last_fill_time"][coin] = lft
        elif lft is not None and lft < existing_lft:
            state.addr_info[addr]["last_fill_time"][coin] = lft

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
) -> bool:
    """
    写入 hl_reverse_signals（含 strategy_id），重复跳过。

    Returns:
        True = 新信号, False = 已存在
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
        return inserted
    except Exception as e:
        conn.rollback()
        logger.error("保存信号失败: %s", e, exc_info=True)
        return False
    finally:
        cur.close()
        conn.close()


def publish_to_redis(strategy_id: str, signal_data: dict) -> None:
    """
    TODO: 将信号写入 Redis。
    Redis 连接配置由调用方补充。

    暂时只记录日志，待 Redis 配置补全后实现。
    """
    logger.debug(
        "[Redis TODO] strategy=%s signal=%s",
        strategy_id,
        signal_data,
    )


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
    处理 fill 列表，对每条 fill 遍历所有关联策略写信号。

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

    for fill in fills:
        coin      = fill.get("coin", "")
        side      = fill.get("side", "")
        direction = fill.get("dir", "")
        price     = float(fill.get("px", 0))
        size      = float(fill.get("sz", 0))
        fill_time = int(fill.get("time", 0))
        fill_hash = fill.get("hash") or None

        if coin not in addr_info["coins"]:
            continue

        action = parse_action(direction)
        if not action:
            logger.debug(
                "跳过无法解析的 fill: addr=%s coin=%s dir=%r",
                address[:10],
                coin,
                direction,
            )
            continue

        # 获取关注这个 (address, coin) 的所有策略
        strategy_ids = pool_state.address_coin_strategies.get((address, coin), set())
        if not strategy_ids:
            continue

        for strategy_id in strategy_ids:
            is_new = save_signal(
                strategy_id=strategy_id,
                address=address,
                coin=coin,
                action=action,
                price=price,
                size=size,
                side=side,
                fill_time=fill_time,
                fill_hash=fill_hash,
            )
            if is_new:
                signal_data = {
                    "strategy_id": strategy_id,
                    "address": address,
                    "coin": coin,
                    "action": action,
                    "side": side,
                    "price": price,
                    "size": size,
                    "fill_time": fill_time,
                    "generated_at": datetime.now().isoformat(),
                }
                publish_to_redis(strategy_id, signal_data)
                new_count += 1

        # 更新 last_fill_time（运行时状态）
        existing_lft = addr_info["last_fill_time"].get(coin) or 0
        if fill_time > existing_lft:
            addr_info["last_fill_time"][coin] = fill_time

    return new_count


# ============================================================
# HTTP 拉取 fills
# ============================================================

async def http_fetch_fills(
    client: httpx.AsyncClient,
    address: str,
    start_time_ms: int,
) -> List[dict]:
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
            return resp.json() or []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                w = HTTP_429_BACKOFF[min(attempt, len(HTTP_429_BACKOFF) - 1)]
                await asyncio.sleep(w)
                continue
            logger.warning("[HTTP] 请求失败 addr=%s: %s", address[:10], e)
            return []
        except Exception as e:
            logger.warning("[HTTP] 请求失败 addr=%s: %s", address[:10], e)
            return []

    logger.error("[HTTP] addr=%s 重试耗尽，跳过", address[:10])
    return []


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

            for address in all_addrs:
                pool_state = pool_ref[0]
                if address not in pool_state.addr_info:
                    continue

                addr_info = pool_state.addr_info[address]

                # 起始时间：取各监控 coin 的 last_fill_time 最小值
                min_lft: Optional[int] = None
                for coin in addr_info["coins"]:
                    lft = addr_info["last_fill_time"].get(coin)
                    if lft is None:
                        min_lft = None
                        break
                    if min_lft is None or lft < min_lft:
                        min_lft = lft

                start_ms = (min_lft + 1) if min_lft else (int(_time.time() * 1000) - 60_000)

                # 毫秒间隔控制
                now_ms = int(_time.time() * 1000)
                elapsed = now_ms - last_req_ms
                if elapsed < HTTP_MIN_INTERVAL_MS:
                    await asyncio.sleep((HTTP_MIN_INTERVAL_MS - elapsed) / 1000)

                last_req_ms = int(_time.time() * 1000)
                fills = await http_fetch_fills(client, address, start_ms)
                last_req_ms = int(_time.time() * 1000)

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
