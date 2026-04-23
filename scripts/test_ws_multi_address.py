"""
测试 Hyperliquid WebSocket 是否支持单连接订阅多个地址的 userFills

用法：
  python scripts/test_ws_multi_address.py [地址数量，默认10]

测试内容：
  1. 单个 WebSocket 连接，批量订阅 N 个地址的 userFills
  2. 观察订阅确认响应数量和速度
  3. 监听 30 秒，统计收到的实时消息数
  4. 验证是否被限流/断连
"""

import sys
import os
import asyncio
import json
import time
import logging
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets
from utils.db_utils import get_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

WS_URL = 'wss://api.hyperliquid.xyz/ws'
LISTEN_SECONDS = 30


def get_pool_addresses(limit: int) -> List[str]:
    """从 hl_fragile_pool 获取活跃地址"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT address FROM hl_fragile_pool
            WHERE monitor_status = 'active' AND exit_date IS NULL
            LIMIT %s
        ''', (limit,))
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


async def test_multi_address_ws(addresses: List[str]) -> None:
    logger.info(f"测试地址数量: {len(addresses)}")
    logger.info(f"WebSocket URL: {WS_URL}")
    logger.info(f"监听时长: {LISTEN_SECONDS}s")
    logger.info("=" * 60)

    sub_confirmed = 0
    fills_received = 0
    errors = 0
    start_time = time.time()

    try:
        async with websockets.connect(
            WS_URL,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            logger.info("✅ WebSocket 连接成功")

            # 批量发送订阅请求
            logger.info(f"📤 发送 {len(addresses)} 个订阅请求...")
            for addr in addresses:
                msg = json.dumps({
                    "method": "subscribe",
                    "subscription": {
                        "type": "userFills",
                        "user": addr,
                        "aggregateByTime": True
                    }
                })
                await ws.send(msg)
                await asyncio.sleep(0.05)  # 50ms 间隔，避免瞬间洪泛

            logger.info(f"✅ 订阅请求发送完毕，等待确认和推送...")
            logger.info("-" * 60)

            # 监听消息
            deadline = start_time + LISTEN_SECONDS
            while time.time() < deadline:
                remaining = deadline - time.time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(5.0, remaining))
                    msg = json.loads(raw)
                    channel = msg.get('channel', '')

                    if channel == 'subscriptionResponse':
                        sub_confirmed += 1
                        sub_type = msg.get('data', {}).get('subscription', {}).get('type', '')
                        user = msg.get('data', {}).get('subscription', {}).get('user', '')[:10]
                        logger.info(f"  📋 订阅确认 [{sub_confirmed}/{len(addresses)}] {sub_type} {user}...")

                    elif channel == 'userFills':
                        data = msg.get('data', {})
                        is_snapshot = data.get('isSnapshot', False)
                        fills = data.get('fills', [])
                        user = data.get('user', '')[:10]
                        if not is_snapshot:
                            fills_received += len(fills)
                            logger.info(f"  🔔 实时 Fill! user={user}... fills={len(fills)}")
                        # snapshot 不计入，只记录日志
                        elif fills:
                            logger.info(f"  📸 快照: user={user}... snapshot_fills={len(fills)}")

                    elif channel == 'error':
                        errors += 1
                        logger.warning(f"  ⚠️  错误消息: {msg}")

                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    logger.info(f"  ⏳ 等待中... 已过 {elapsed:.0f}s，已确认订阅 {sub_confirmed}/{len(addresses)}")
                    continue

    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"❌ 连接被关闭: {e}")
    except Exception as e:
        logger.error(f"❌ 异常: {e}", exc_info=True)

    # 结果汇总
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"📊 测试结果（{elapsed:.1f}s）：")
    logger.info(f"   订阅地址数:    {len(addresses)}")
    logger.info(f"   订阅确认数:    {sub_confirmed} / {len(addresses)}")
    logger.info(f"   实时 Fill 数:  {fills_received}")
    logger.info(f"   错误数:        {errors}")
    if sub_confirmed == len(addresses):
        logger.info("✅ 结论：单连接多地址订阅 OK")
    else:
        logger.warning(f"⚠️  结论：只确认了 {sub_confirmed}/{len(addresses)} 个订阅，可能有限制")
    logger.info("=" * 60)


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    addresses = get_pool_addresses(limit)
    if not addresses:
        logger.error("❌ hl_fragile_pool 中没有活跃地址，请先运行 update_fragile_pool.py")
        return

    logger.info(f"从池子中取到 {len(addresses)} 个地址")
    asyncio.run(test_multi_address_ws(addresses))


if __name__ == '__main__':
    main()
