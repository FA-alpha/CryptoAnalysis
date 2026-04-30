"""
手动发送测试信号到 Redis Stream（fa:signal）。

用法示例：
  python scripts/send_test_signal.py
  python scripts/send_test_signal.py --strategy-id 2 --symbol "BTC/USDT:USDT" --signal-type entry_short
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_connection
from utils.signal_producer import send_signal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="发送测试信号到 Redis")
    parser.add_argument("--strategy-id", default="test_strategy_001", help="策略ID")
    parser.add_argument("--source-address", default="0xtest000000000000000000000000000000000001", help="源地址（用于入库）")
    parser.add_argument("--symbol", default="BTC/USDT:USDT", help="交易对")
    parser.add_argument(
        "--signal-type",
        default="entry_long",
        choices=["entry_long", "entry_short", "exit_long", "exit_short"],
        help="信号类型",
    )
    parser.add_argument("--signal-id", default=None, help="信号ID（不传则自动生成）")
    parser.add_argument("--price", type=float, default=68000.0, help="价格")
    parser.add_argument("--size", type=float, default=0.01, help="数量")
    parser.add_argument("--fill-time", type=int, default=None, help="fill时间戳(ms)")
    return parser.parse_args()


def parse_coin(symbol: str) -> str:
    # BTC/USDT:USDT -> BTC
    return symbol.split("/")[0].strip().upper()


def map_for_reverse_signals(signal_type: str) -> tuple[str, str, str]:
    """
    将执行层信号类型映射到 hl_reverse_signals 所需字段：
      returns: (db_signal_type, original_direction, reverse_direction)
    """
    if signal_type == "entry_long":
        return ("new_position", "short", "long")
    if signal_type == "entry_short":
        return ("new_position", "long", "short")
    if signal_type == "exit_long":
        return ("close_position", "short", "long")
    if signal_type == "exit_short":
        return ("close_position", "long", "short")
    raise ValueError(f"不支持的 signal_type: {signal_type}")


def save_to_reverse_signals(
    *,
    signal_id: str,
    strategy_id: str,
    source_address: str,
    coin: str,
    signal_type: str,
    price: float,
    size: float,
    fill_time: int,
) -> bool:
    db_signal_type, original_direction, reverse_direction = map_for_reverse_signals(signal_type)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT IGNORE INTO hl_reverse_signals (
                signal_id, strategy_id, source_address, coin, signal_type,
                original_direction, original_size, original_price, original_fill_time,
                reverse_direction, reverse_size, reverse_weight, signal_status, generated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1.0, 'pending', NOW())
            """,
            (
                signal_id,
                strategy_id,
                source_address,
                coin,
                db_signal_type,
                original_direction,
                size,
                price,
                fill_time,
                reverse_direction,
                size,
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    args = parse_args()
    now_ms = int(datetime.now().timestamp() * 1000)
    fill_time = args.fill_time or now_ms
    cst = timezone(timedelta(hours=8))
    generated_at = datetime.now(cst).isoformat()
    signal_id = args.signal_id or f"test-{uuid.uuid4().hex[:20]}"
    coin = parse_coin(args.symbol)

    inserted = save_to_reverse_signals(
        signal_id=signal_id,
        strategy_id=args.strategy_id,
        source_address=args.source_address,
        coin=coin,
        signal_type=args.signal_type,
        price=args.price,
        size=args.size,
        fill_time=fill_time,
    )
    if inserted:
        print(f"✅ 已写入 hl_reverse_signals: signal_id={signal_id}")
    else:
        print(f"ℹ️ hl_reverse_signals 已存在同 signal_id，跳过: signal_id={signal_id}")

    data = {
        "address": args.source_address,
        "price": args.price,
        "size": args.size,
        "fill_time": fill_time,
        "generated_at": generated_at,
    }

    message_id = send_signal(
        strategy_id=args.strategy_id,
        symbol=args.symbol,
        signal_type=args.signal_type,
        signal_id=signal_id,
        data=data,
    )
    if message_id:
        print(f"✅ 测试信号发送成功: message_id={message_id}")
    else:
        print("❌ 测试信号发送失败，请检查 Redis 连接配置与可达性。")


if __name__ == "__main__":
    main()
