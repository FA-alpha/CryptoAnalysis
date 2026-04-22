"""
交易信号监控脚本

逻辑：
  1. 从 hl_monitor_addresses 拉取所有 active 的 address+coin
  2. 对每个地址：
     a. 拉取挂单（openOrders）→ 新挂单生成 order 信号
     b. 拉取最新 fills（userFillsByTime 增量）→ Open/Close 生成 fill 信号
  3. 信号写入 hl_trade_signals，推送飞书通知
  4. 每 60 秒轮询一次

运行方式：
  python scripts/monitor_signals.py          # 持续运行
  python scripts/monitor_signals.py --once   # 只跑一次（调试用）
"""

import sys
import os
import json
import time
import hashlib
import logging
import argparse
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

# ============================================================
# 配置
# ============================================================
LARK_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/b820bda8-4d32-4f11-8530-2dc37bcdcaad"
HL_API_URL = "https://api.hyperliquid.xyz/info"
POLL_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT = 30
INTER_ADDRESS_DELAY = 0.5  # 地址间间隔(秒)

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/monitor_signals.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# Hyperliquid API
# ============================================================

def fetch_open_orders(address: str) -> list:
    """获取地址当前挂单列表"""
    try:
        resp = httpx.post(
            HL_API_URL,
            json={"type": "openOrders", "user": address},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json() or []
    except Exception as e:
        logger.error(f"获取挂单失败 {address}: {e}")
        return []


def fetch_fills_by_time(address: str, start_time_ms: int) -> list:
    """增量拉取 fills（从 start_time_ms 开始）"""
    try:
        resp = httpx.post(
            HL_API_URL,
            json={
                "type": "userFillsByTime",
                "user": address,
                "startTime": start_time_ms,
                "aggregateByTime": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json() or []
    except Exception as e:
        logger.error(f"获取 fills 失败 {address}: {e}")
        return []

# ============================================================
# 数据库操作
# ============================================================

def get_monitor_addresses() -> list:
    """获取所有 active 的监控地址"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, address, coin, label, last_fill_time, last_order_ids
            FROM hl_monitor_addresses
            WHERE status = 'active'
            ORDER BY id
        """)
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "address": r[1],
                "coin": r[2],
                "label": r[3] or r[1][:10],
                "last_fill_time": r[4],
                "last_order_ids": set(json.loads(r[5])) if r[5] else set(),
            })
        return result
    finally:
        cur.close()
        conn.close()


def update_last_fill_time(monitor_id: int, last_fill_time: int) -> None:
    """更新 last_fill_time"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE hl_monitor_addresses SET last_fill_time = %s WHERE id = %s",
            (last_fill_time, monitor_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def update_last_order_ids(monitor_id: int, order_ids: set) -> None:
    """更新已处理的挂单 ID 列表"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE hl_monitor_addresses SET last_order_ids = %s WHERE id = %s",
            (json.dumps(list(order_ids)), monitor_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_signal(signal: dict) -> bool:
    """
    保存信号到 hl_trade_signals。

    Returns:
        True = 新信号已保存，False = 已存在跳过
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT IGNORE INTO hl_trade_signals (
                signal_id, address, coin, signal_source, action,
                price, size, fill_hash, fill_time, order_id,
                raw_direction, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            signal["signal_id"],
            signal["address"],
            signal["coin"],
            signal["signal_source"],
            signal["action"],
            signal["price"],
            signal["size"],
            signal.get("fill_hash"),
            signal.get("fill_time"),
            signal.get("order_id"),
            signal.get("raw_direction"),
        ))
        conn.commit()
        return cur.rowcount > 0
    finally:
        cur.close()
        conn.close()


def mark_signal_notified(signal_id: str) -> None:
    """标记信号为已通知"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE hl_trade_signals SET status = 'notified' WHERE signal_id = %s",
            (signal_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

# ============================================================
# 信号判断
# ============================================================

def make_signal_id(*parts) -> str:
    """生成信号唯一 ID"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def parse_fill_action(direction: str, side: str) -> Optional[str]:
    """
    根据 fill 的 dir 和 side 判断动作。

    direction: fill['dir']，如 "Open Long" / "Close Short" 等
    side: fill['side']，"B"=Buy / "A"=Ask(Sell)

    Returns:
        'open_long' | 'open_short' | 'close_long' | 'close_short' | None
    """
    d = direction.lower()
    if "open" in d:
        return "open_long" if side == "B" else "open_short"
    elif "close" in d:
        # close_long = 平多（卖出）= side A；close_short = 平空（买入）= side B
        return "close_long" if side == "A" else "close_short"
    return None


def process_fills(monitor: dict, fills: list) -> list:
    """
    处理 fills，生成信号列表。

    Returns:
        新生成的 signal 列表
    """
    coin = monitor["coin"]
    address = monitor["address"]
    signals = []

    # 只处理当前监控币种，且时间 > last_fill_time
    last_time = monitor["last_fill_time"] or 0
    relevant = [
        f for f in fills
        if f.get("coin") == coin and int(f.get("time", 0)) > last_time
    ]
    # 按时间升序处理
    relevant.sort(key=lambda x: x["time"])

    for fill in relevant:
        direction = fill.get("dir", "")
        side = fill.get("side", "")
        action = parse_fill_action(direction, side)
        if not action:
            continue

        fill_hash = fill.get("hash") or ""
        fill_time = int(fill.get("time", 0))
        price = Decimal(str(fill.get("px", 0)))
        size = Decimal(str(fill.get("sz", 0)))

        signal_id = make_signal_id(address, fill_hash, fill_time)
        signals.append({
            "signal_id": signal_id,
            "address": address,
            "coin": coin,
            "signal_source": "fill",
            "action": action,
            "price": price,
            "size": size,
            "fill_hash": fill_hash if fill_hash else None,
            "fill_time": fill_time,
            "order_id": None,
            "raw_direction": side,
            "_fill_time": fill_time,  # 用于更新 last_fill_time
        })

    return signals


def process_orders(monitor: dict, orders: list) -> list:
    """
    处理挂单，生成新增挂单的信号（已出现过的跳过）。

    Returns:
        新生成的 signal 列表
    """
    coin = monitor["coin"]
    address = monitor["address"]
    last_order_ids = monitor["last_order_ids"]
    signals = []

    relevant = [o for o in orders if o.get("coin") == coin]

    for order in relevant:
        order_id = str(order.get("oid", ""))
        if order_id in last_order_ids:
            continue  # 已处理过

        side = order.get("side", "")  # "B" or "A"
        # 挂单没有 dir 字段，通过 side 判断买/卖意图
        # 挂买单(B) → 准备开多或平空；挂卖单(A) → 准备开空或平多
        # 无法精确判断 open/close，用 side 近似
        action = "open_long" if side == "B" else "open_short"

        price = Decimal(str(order.get("limitPx", 0)))
        size = Decimal(str(order.get("sz", 0)))

        signal_id = make_signal_id(address, coin, order_id)
        signals.append({
            "signal_id": signal_id,
            "address": address,
            "coin": coin,
            "signal_source": "order",
            "action": action,
            "price": price,
            "size": size,
            "fill_hash": None,
            "fill_time": None,
            "order_id": order_id,
            "raw_direction": side,
        })

    return signals

# ============================================================
# 飞书通知
# ============================================================

ACTION_EMOJI = {
    "open_long":   "🟢 开多",
    "open_short":  "🔴 开空",
    "close_long":  "⬇️ 平多",
    "close_short": "⬆️ 平空",
}

SOURCE_LABEL = {
    "fill":  "✅ 已成交（fill）",
    "order": "📋 挂单（order）⚠️ 可能撤单",
}


def send_lark_notification(signal: dict, label: str) -> None:
    """推送飞书通知"""
    action_text = ACTION_EMOJI.get(signal["action"], signal["action"])
    source_text = SOURCE_LABEL.get(signal["signal_source"], signal["signal_source"])
    ts = signal.get("fill_time")
    time_str = (
        datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        if ts else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    content = (
        f"**🚨 跟单信号 [{signal['coin']}]**\n\n"
        f"来源地址：`{signal['address'][:6]}...{signal['address'][-4:]}` ({label})\n"
        f"动作：{action_text}\n"
        f"价格：{signal['price']}\n"
        f"数量：{signal['size']} {signal['coin']}\n"
        f"时间：{time_str}\n"
        f"来源：{source_text}"
    )

    payload = {
        "msg_type": "interactive",
        "card": {
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content},
                }
            ],
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"跟单信号 · {signal['coin']} · {action_text}",
                },
                "template": "red" if "open" in signal["action"] else "blue",
            },
        },
    }

    try:
        resp = httpx.post(LARK_WEBHOOK, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"飞书通知已发送: {signal['signal_id'][:8]}...")
    except Exception as e:
        logger.error(f"飞书通知失败: {e}")

# ============================================================
# 主轮询逻辑
# ============================================================

def poll_once() -> None:
    """执行一次完整轮询"""
    monitors = get_monitor_addresses()
    if not monitors:
        logger.info("无监控地址，跳过本次轮询")
        return

    logger.info(f"开始轮询，共 {len(monitors)} 个监控地址")

    for monitor in monitors:
        address = monitor["address"]
        coin = monitor["coin"]
        label = monitor["label"]
        logger.info(f"  处理 {label} [{coin}] {address[:10]}...")

        new_signals = []

        # ① 挂单信号
        orders = fetch_open_orders(address)
        order_signals = process_orders(monitor, orders)
        new_signals.extend(order_signals)

        # 更新已知挂单 ID（当前所有挂单，含旧的）
        current_order_ids = {str(o.get("oid", "")) for o in orders if o.get("coin") == coin}
        update_last_order_ids(monitor["id"], current_order_ids)

        # ② Fill 信号（增量）
        start_time = (monitor["last_fill_time"] or int(time.time() * 1000)) + 1
        fills = fetch_fills_by_time(address, start_time)
        fill_signals = process_fills(monitor, fills)
        new_signals.extend(fill_signals)

        # 更新 last_fill_time
        if fill_signals:
            max_fill_time = max(s["_fill_time"] for s in fill_signals)
            update_last_fill_time(monitor["id"], max_fill_time)
        elif monitor["last_fill_time"] is None:
            # 新地址首次轮询，没有 fill，记录当前时间防止下次全量拉取
            update_last_fill_time(monitor["id"], int(time.time() * 1000))

        # ③ 保存 + 通知
        for signal in new_signals:
            is_new = save_signal(signal)
            if is_new:
                send_lark_notification(signal, label)
                mark_signal_notified(signal["signal_id"])
                logger.info(
                    f"    ✅ 新信号: {signal['action']} {signal['coin']} "
                    f"@ {signal['price']} ({signal['signal_source']})"
                )

        if not new_signals:
            logger.info(f"    无新信号")

        time.sleep(INTER_ADDRESS_DELAY)

    logger.info("本次轮询完成")


def main() -> None:
    parser = argparse.ArgumentParser(description="交易信号监控")
    parser.add_argument("--once", action="store_true", help="只运行一次（调试用）")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)

    if args.once:
        logger.info("=== 单次运行模式 ===")
        poll_once()
        return

    logger.info("=== 持续监控模式启动（每 60 秒轮询）===")
    while True:
        try:
            poll_once()
        except Exception as e:
            logger.error(f"轮询异常: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
