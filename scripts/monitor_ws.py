"""
WebSocket 实时监控服务 - 脆弱地址反向信号

架构：
  - 从 hl_fragile_pool 加载所有 active 的地址+币种
  - 每个 WebSocket 连接最多订阅 10 个地址（Hyperliquid 限制）
  - 多连接并发，断连自动重连
  - 监测到 fill 后判断动作（开仓/加仓/减仓/平仓），推送飞书

信号触发逻辑：
  - 开新仓 / 加仓 → 🚨 推送反向做单信号
  - 减仓 / 平仓   → 📢 推送平仓提示

运行方式：
  python scripts/monitor_ws.py

停止：Ctrl+C
"""

import sys
import os
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import httpx
import websockets
import websockets.exceptions

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

# ============================================================
# 配置
# ============================================================
WS_URL = 'wss://api.hyperliquid.xyz/ws'
LARK_WEBHOOK = 'https://open.larksuite.com/open-apis/bot/v2/hook/b820bda8-4d32-4f11-8530-2dc37bcdcaad'
MAX_USERS_PER_CONN = 10       # Hyperliquid IP 级别最多追踪用户数
TOP_N_ADDRESSES = 10          # 取活跃度最高的 N 个地址监控
RECONNECT_DELAY_SEC = 5       # 断连后重连等待秒数
SUB_SEND_INTERVAL = 0.05      # 订阅请求发送间隔（秒）
PING_INTERVAL = 20            # WebSocket ping 间隔
POOL_REFRESH_INTERVAL = 3600  # 每小时重新加载池子（秒）

# ============================================================
# 日志
# ============================================================
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/monitor_ws.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# 数据加载
# ============================================================

def load_pool() -> Dict[str, Dict]:
    """
    从 hl_fragile_pool 加载活跃度最高的 TOP_N 个地址，关联最新币种评分。
    活跃度按近7天所有监控币种交易总笔数排序。

    Returns:
        {address: {coins: set, label, scores: {coin: {level, score}}}}
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 先算出每个地址的近7天总交易笔数，取 TOP N
        cursor.execute('''
            SELECT p.address
            FROM hl_fragile_pool p
            INNER JOIN (
                SELECT address, coin, recent_7d_trades,
                       ROW_NUMBER() OVER (PARTITION BY address, coin ORDER BY calculated_at DESC) rn
                FROM hl_coin_address_features
            ) cf ON cf.address = p.address AND cf.coin = p.coin AND cf.rn = 1
            WHERE p.monitor_status = 'active' AND p.exit_date IS NULL
            GROUP BY p.address
            ORDER BY SUM(cf.recent_7d_trades) DESC
            LIMIT %s
        ''', (TOP_N_ADDRESSES,))
        top_addresses = {row[0] for row in cursor.fetchall()}

        # 加载这些地址的全部币种+评分
        cursor.execute('''
            SELECT p.address, p.coin, p.label, p.fragile_level, p.total_score
            FROM hl_fragile_pool p
            WHERE p.monitor_status = 'active' AND p.exit_date IS NULL
            ORDER BY p.address, p.coin
        ''')
        rows = cursor.fetchall()

        pool: Dict[str, Dict] = {}
        for address, coin, label, level, score in rows:
            if address not in top_addresses:
                continue
            if address not in pool:
                pool[address] = {
                    'label': label or address[:10],
                    'coins': set(),
                    'scores': {}
                }
            pool[address]['coins'].add(coin)
            pool[address]['scores'][coin] = {
                'level': level,
                'score': float(score or 0)
            }

        coin_count = sum(len(v['coins']) for v in pool.values())
        logger.info(f"池子加载完成: TOP {TOP_N_ADDRESSES} 活跃地址 = {len(pool)} 个，共 {coin_count} 个地址+币种组合")
        return pool
    finally:
        cursor.close()
        conn.close()


def make_signal_id(address: str, fill_hash: Optional[str], fill_time: int, coin: str) -> str:
    """生成信号唯一 ID（50字符以内）"""
    import hashlib
    raw = f"{address}|{fill_hash or ''}|{fill_time}|{coin}"
    return hashlib.md5(raw.encode()).hexdigest()[:50]


def save_signal_to_db(address: str, coin: str, action: str,
                      price: float, size: float, side: str,
                      fill_time: int, fill_hash: Optional[str]) -> bool:
    """
    保存信号到 hl_reverse_signals，重复则跳过。

    Returns:
        True=新信号，False=已存在
    """
    # 动作映射到表枚举值
    signal_type_map = {
        'open':   'new_position',
        'add':    'add_position',
        'close':  'close_position',
        'reduce': 'close_position',
    }
    signal_type = signal_type_map.get(action, 'new_position')
    original_direction = 'long' if side == 'B' else 'short'
    reverse_direction  = 'short' if side == 'B' else 'long'
    signal_id = make_signal_id(address, fill_hash, fill_time, coin)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT IGNORE INTO hl_reverse_signals
              (signal_id, source_address, coin, signal_type,
               original_direction, original_size, original_price,
               original_fill_time, reverse_direction, reverse_size,
               reverse_weight, signal_status, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1.0, 'pending', NOW())
        ''', (signal_id, address, coin, signal_type,
              original_direction, size, price,
              fill_time, reverse_direction, size))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"保存信号失败: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def update_pool_last_fill(address: str, coin: str, fill_time: int) -> None:
    """更新 hl_fragile_pool.last_fill_time"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE hl_fragile_pool
            SET last_fill_time = %s, last_monitored_at = NOW()
            WHERE address = %s AND coin = %s AND monitor_status = 'active'
        ''', (fill_time, address, coin))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# ============================================================
# 信号判断
# ============================================================

def parse_action(direction: str, side: str) -> Optional[str]:
    """
    解析 fill 动作。

    Args:
        direction: fill['dir']，如 "Open Long" / "Close Short"
        side: fill['side']，"B"=Buy / "A"=Ask(Sell)

    Returns:
        'open' | 'add' | 'close' | 'reduce' | None
    """
    d = direction.lower()
    if 'open' in d:
        return 'open'
    elif 'close' in d:
        return 'close'
    # 部分 fill 没有明确 dir，通过 startPosition 判断加仓/减仓
    return None


def format_action_text(action: str, side: str) -> Tuple[str, str]:
    """
    返回 (动作描述, 反向建议)

    side: B=做多, A=做空
    """
    position = '多' if side == 'B' else '空'
    reverse = '空' if side == 'B' else '多'

    if action == 'open':
        return f'🔴 开{position}仓', f'💡 反向建议：做{reverse}'
    elif action == 'close':
        return f'⬜ 平{position}仓', f'💡 持有反向{reverse}仓可考虑止盈'
    elif action == 'add':
        return f'🔴 加{position}仓', f'💡 反向建议：加做{reverse}'
    else:
        return f'⬇️ 减{position}仓', f'💡 反向仓位可适当减少'


# ============================================================
# 飞书推送
# ============================================================

async def send_lark(address: str, coin: str, action: str, side: str,
                    price: float, size: float, fill_time: int,
                    label: str, level: str, score: float) -> None:
    """异步推送飞书消息"""
    action_text, suggest_text = format_action_text(action, side)
    time_str = datetime.fromtimestamp(fill_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
    addr_short = f"{address[:6]}...{address[-4:]}"
    is_open = action in ('open', 'add')

    content = (
        f"**地址**：`{addr_short}` ({label})\n"
        f"**币种**：{coin}  |  **脆弱等级**：{level}（{score:.0f}分）\n"
        f"**动作**：{action_text}\n"
        f"**价格**：{price:.4f}  |  **数量**：{size} {coin}\n"
        f"**时间**：{time_str}\n\n"
        f"{suggest_text}"
    )

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{'🚨 反向信号' if is_open else '📢 平仓提示'} · {coin} · {action_text}"
                },
                "template": "red" if is_open else "blue"
            },
            "elements": [{
                "tag": "div",
                "text": {"tag": "lark_md", "content": content}
            }]
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(LARK_WEBHOOK, json=payload)
            resp.raise_for_status()
        logger.info(f"  📨 飞书推送成功: {addr_short} {coin} {action_text}")
    except Exception as e:
        logger.error(f"  ❌ 飞书推送失败: {e}")


# ============================================================
# Fill 处理
# ============================================================

async def handle_fill(fill: dict, pool: Dict[str, Dict]) -> None:
    """处理单条 fill，判断信号并推送"""
    address = fill.get('user', '')  # WsUserFills 里有 user 字段
    coin = fill.get('coin', '')
    side = fill.get('side', '')
    direction = fill.get('dir', '')
    price = float(fill.get('px', 0))
    size = float(fill.get('sz', 0))
    fill_time = int(fill.get('time', 0))
    fill_hash = fill.get('hash') or None

    # 只处理池子里监控的地址+币种
    if address not in pool:
        return
    addr_info = pool[address]
    if coin not in addr_info['coins']:
        return

    action = parse_action(direction, side)
    if not action:
        logger.debug(f"  无法解析动作: dir={direction} side={side}，跳过")
        return

    score_info = addr_info['scores'].get(coin, {})
    level = score_info.get('level', 'L3')
    score = score_info.get('score', 0.0)
    label = addr_info['label']

    logger.info(
        f"  🎯 Fill 命中: {label} {coin} | {direction} | "
        f"price={price} size={size} level={level}"
    )

    # 保存到数据库
    is_new = save_signal_to_db(
        address=address, coin=coin, action=action,
        price=price, size=size, side=side,
        fill_time=fill_time, fill_hash=fill_hash
    )

    if is_new:
        # 推送飞书
        await send_lark(
            address=address, coin=coin, action=action, side=side,
            price=price, size=size, fill_time=fill_time,
            label=label, level=level, score=score
        )
        # 更新最后成交时间
        update_pool_last_fill(address, coin, fill_time)
    else:
        logger.debug(f"  重复信号，跳过推送")


# ============================================================
# WebSocket 连接（单个分片）
# ============================================================

async def run_ws_shard(shard_id: int, addresses: List[str],
                       pool: Dict[str, Dict]) -> None:
    """
    运行单个 WebSocket 分片，断连自动重连。

    Args:
        shard_id: 分片编号（日志用）
        addresses: 本分片负责的地址列表（最多10个）
        pool: 完整池子数据（用于判断币种和评分）
    """
    while True:
        try:
            logger.info(f"[分片{shard_id}] 连接 WebSocket... ({len(addresses)} 个地址)")
            async with websockets.connect(
                WS_URL,
                ping_interval=30,     # 每 30s 发送 ping
                ping_timeout=60,      # 60s 内没收到 pong 才断连
                close_timeout=5,
            ) as ws:
                logger.info(f"[分片{shard_id}] 连接成功，发送订阅请求...")

                # 发送订阅
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
                    await asyncio.sleep(SUB_SEND_INTERVAL)

                confirmed = 0
                logger.info(f"[分片{shard_id}] 订阅请求发送完毕，等待推送...")

                async for raw in ws:
                    # Hyperliquid 心跟：服务端会发送文本 "ping"
                    if isinstance(raw, bytes):
                        logger.info(f"[分片{shard_id}] 收到 binary 消息: {raw[:50]}")
                        continue
                    if raw == 'ping':
                        await ws.send('pong')
                        logger.info(f"[分片{shard_id}] 心跟 pong 已回复")
                        continue
                    # 打印非常规消息（调试斷连原因）
                    if not raw.startswith('{'):
                        logger.info(f"[分片{shard_id}] 非 JSON 消息: {repr(raw[:100])}")

                    msg = json.loads(raw)
                    channel = msg.get('channel', '')

                    if channel == 'subscriptionResponse':
                        confirmed += 1
                        if confirmed == len(addresses):
                            logger.info(f"[分片{shard_id}] ✅ 全部 {confirmed} 个订阅已确认")

                    elif channel == 'userFills':
                        data = msg.get('data', {})
                        is_snapshot = data.get('isSnapshot', False)
                        user = data.get('user', '')
                        fills = data.get('fills', [])
                        logger.info(f"[分片{shard_id}] 📩 userFills: user={user[:10]}... snapshot={is_snapshot} fills={len(fills)}")
                        if fills:
                            logger.info(f"[分片{shard_id}] 原始消息: {json.dumps(msg, ensure_ascii=False)[:500]}")
                        if is_snapshot:
                            continue  # 跳过历史快照
                        for fill in fills:
                            fill['user'] = user  # 注入 user 字段
                            await handle_fill(fill, pool)

                    elif channel == 'error':
                        logger.warning(f"[分片{shard_id}] ⚠️ 错误: {msg.get('data')}")

                    else:
                        logger.debug(f"[分片{shard_id}] 未知消息: channel={channel}")

        except websockets.exceptions.ConnectionClosedOK as e:
            logger.warning(f"[分片{shard_id}] 连接正常关闭(OK): code={e.code} reason={e.reason}，{RECONNECT_DELAY_SEC}s 后重连...")
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"[分片{shard_id}] 连接异常断开: code={e.code} reason={e.reason}，{RECONNECT_DELAY_SEC}s 后重连...")
        except Exception as e:
            logger.error(f"[分片{shard_id}] 异常: {type(e).__name__}: {e}，{RECONNECT_DELAY_SEC}s 后重连...", exc_info=True)

        await asyncio.sleep(RECONNECT_DELAY_SEC)


# ============================================================
# 主流程
# ============================================================

async def send_lark_text(text: str) -> None:
    """发送纯文本飞书消息"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(LARK_WEBHOOK, json={
                'msg_type': 'text',
                'content': {'text': text}
            })
    except Exception as e:
        logger.error(f"飞书发送失败: {e}")


async def main() -> None:
    logger.info("=" * 60)
    logger.info("WebSocket 实时监控服务启动")
    logger.info("=" * 60)

    pool = load_pool()
    if not pool:
        logger.error("❌ 池子为空，请先运行 update_fragile_pool.py")
        return

    addresses = list(pool.keys())
    logger.info(f"共 {len(addresses)} 个地址，使用单个 WebSocket 连接监控")

    # 定期刷新池子
    async def refresh_loop():
        nonlocal pool
        while True:
            await asyncio.sleep(POOL_REFRESH_INTERVAL)
            logger.info("🔄 刷新池子数据...")
            pool = load_pool()

    tasks = [
        asyncio.create_task(run_ws_shard(1, addresses, pool)),
        asyncio.create_task(refresh_loop()),
    ]

    await send_lark_text(f"✅ 监控服务已启动\n监控地址: {len(addresses)} 个\n币种+地址组合: {sum(len(v['coins']) for v in pool.values())} 个\n等待实时 fill 推送...")
    logger.info(f"✅ 监控服务运行中（Ctrl+C 停止）")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("监控服务已停止")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断，服务退出")
