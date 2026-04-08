"""
计算地址特征并保存到 hl_address_features 表
基于 hl_fills 和 hl_position_snapshots/details 计算各项指标

特征列表：
  基础统计（来自 hl_fills）：
    - total_trades, win_rate, avg_win_pnl, avg_loss_pnl
    - profit_loss_ratio, total_realized_pnl, total_fee
    - active_days, avg_trades_per_day, last_trade_time
  风险指标（来自 hl_position_details/snapshots）：
    - avg_leverage, max_leverage
    - avg_margin_utilization, max_margin_utilization
  行为模式（来自 hl_fills）：
    - full_close_loss_count：全仓止损次数（sz≈start_position + Close + pnl<0）
    - coin_concentration：最多交易币种占总交易量比例
  亏损特征（来自 hl_position_snapshots）：
    - pnl_all_time：历史总盈亏
    - pnl_loss_ratio：|pnl_all_time| / 当前账户价值（亏损倍数）
"""
import sys
import os
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

# 全仓止损判定阈值：sz 与 start_position 差异 < 2%
FULL_CLOSE_DIFF_THRESHOLD = 0.02


def get_active_addresses() -> List[str]:
    """获取所有活跃地址"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT address FROM hl_address_list
            WHERE status = 'active'
            ORDER BY last_updated_at DESC
        ''')
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def calculate_basic_stats(address: str, cursor) -> Optional[Dict]:
    """
    计算基础统计指标（来自 hl_fills Close 记录）

    胜率定义：Close 方向记录中 closed_pnl > 0 的比例
    盈亏比定义：avg_win / |avg_loss|（平均盈利 / 平均亏损绝对值）
    """
    print(f"   📊 计算基础统计（胜率/盈亏比/交易频率）...")

    cursor.execute('''
        SELECT
            COUNT(*) as total_close,
            SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) as win_count,
            AVG(CASE WHEN closed_pnl > 0 THEN closed_pnl END) as avg_win_pnl,
            AVG(CASE WHEN closed_pnl < 0 THEN closed_pnl END) as avg_loss_pnl,
            SUM(closed_pnl) as total_realized_pnl,
            SUM(fee) as total_fee,
            MIN(time) as data_start,
            MAX(time) as data_end
        FROM hl_fills
        WHERE address = %s AND dir LIKE 'Close%%'
    ''', (address,))

    row = cursor.fetchone()
    if not row or not row[0]:
        print(f"   ⚠️ 无平仓数据")
        return None

    total_close, win_count, avg_win, avg_loss, total_pnl, total_fee, data_start, data_end = row

    win_rate = float(win_count) / float(total_close) * 100 if total_close else 0
    # 盈亏比：平均盈利 / 平均亏损绝对值，avg_loss 为负数
    profit_loss_ratio = abs(float(avg_win or 0)) / abs(float(avg_loss or 1)) if avg_loss and avg_loss < 0 else 0

    days = (data_end - data_start) / 1000 / 86400 if data_end and data_start else 0
    avg_trades_per_day = total_close / days if days > 0 else 0

    return {
        'total_trades': int(total_close),
        'win_rate': Decimal(str(round(win_rate, 4))),
        'avg_win_pnl': Decimal(str(round(float(avg_win or 0), 6))),
        'avg_loss_pnl': Decimal(str(round(float(avg_loss or 0), 6))),
        'profit_loss_ratio': Decimal(str(round(profit_loss_ratio, 6))),
        'total_realized_pnl': Decimal(str(round(float(total_pnl or 0), 6))),
        'total_fee': Decimal(str(round(float(total_fee or 0), 6))),
        'data_period_start': int(data_start) if data_start else 0,
        'data_period_end': int(data_end) if data_end else 0,
        'active_days': int(days),
        'avg_trades_per_day': Decimal(str(round(avg_trades_per_day, 4))),
        'last_trade_time': int(data_end) if data_end else 0,
    }


def calculate_risk_indicators(address: str, cursor) -> Dict:
    """
    计算风险指标（来自 hl_position_details + hl_position_snapshots）

    平均杠杆：AVG(leverage_value) 跨所有快照
    保证金使用率：AVG(total_margin_used / account_value)
    注意：快照数据初期较少，随每日积累逐渐准确
    """
    print(f"   ⚙️ 计算风险指标（杠杆/保证金使用率）...")

    cursor.execute('''
        SELECT
            AVG(d.leverage_value) as avg_leverage,
            MAX(d.leverage_value) as max_leverage,
            AVG(s.total_margin_used / NULLIF(s.account_value, 0) * 100) as avg_margin_util,
            MAX(s.total_margin_used / NULLIF(s.account_value, 0) * 100) as max_margin_util
        FROM hl_position_details d
        JOIN hl_position_snapshots s ON d.snapshot_id = s.id
        WHERE s.address = %s AND s.account_value > 0
    ''', (address,))

    row = cursor.fetchone()
    if not row or row[0] is None:
        return {
            'avg_leverage': Decimal('0'),
            'max_leverage': Decimal('0'),
            'avg_margin_utilization': Decimal('0'),
            'max_margin_utilization': Decimal('0'),
        }

    return {
        'avg_leverage': Decimal(str(round(float(row[0] or 0), 2))),
        'max_leverage': Decimal(str(round(float(row[1] or 0), 2))),
        'avg_margin_utilization': Decimal(str(round(float(row[2] or 0), 4))),
        'max_margin_utilization': Decimal(str(round(float(row[3] or 0), 4))),
    }


def calculate_behavior_indicators(address: str, cursor) -> Dict:
    """
    计算行为模式指标（来自 hl_fills）

    全仓止损次数：sz ≈ start_position（差异<2%）+ Close + closed_pnl < 0
    单币种集中度：交易量最多的币种 / 总交易量
    """
    print(f"   🔍 计算行为模式（全仓止损次数/币种集中度）...")

    # 1. 全仓止损次数
    cursor.execute('''
        SELECT COUNT(*) FROM hl_fills
        WHERE address = %s
          AND dir LIKE 'Close%%'
          AND closed_pnl < 0
          AND start_position > 0
          AND ABS(sz - start_position) / NULLIF(start_position, 0) < %s
    ''', (address, FULL_CLOSE_DIFF_THRESHOLD))
    full_close_loss_count = cursor.fetchone()[0] or 0

    # 2. 单币种集中度（按交易次数）
    cursor.execute('''
        SELECT coin, COUNT(*) as cnt
        FROM hl_fills
        WHERE address = %s
        GROUP BY coin
        ORDER BY cnt DESC
        LIMIT 1
    ''', (address,))
    top_coin_row = cursor.fetchone()

    cursor.execute('SELECT COUNT(*) FROM hl_fills WHERE address = %s', (address,))
    total_count = cursor.fetchone()[0] or 1

    coin_concentration = 0.0
    if top_coin_row:
        coin_concentration = float(top_coin_row[1]) / float(total_count) * 100

    return {
        'full_close_loss_count': int(full_close_loss_count),
        'coin_concentration': Decimal(str(round(coin_concentration, 4))),
    }


def calculate_pnl_features(address: str, cursor) -> Dict:
    """
    计算亏损特征（来自 hl_position_snapshots）

    pnl_all_time：最新快照的历史总盈亏
    pnl_loss_ratio：|pnl_all_time| / 当前账户价值（亏损倍数，反映亏损严重程度）
    """
    print(f"   📉 计算亏损特征（历史总盈亏/亏损倍数）...")

    cursor.execute('''
        SELECT pnl_all_time, account_value
        FROM hl_position_snapshots
        WHERE address = %s AND pnl_all_time IS NOT NULL
        ORDER BY snapshot_time DESC
        LIMIT 1
    ''', (address,))

    row = cursor.fetchone()
    if not row:
        return {
            'pnl_all_time': Decimal('0'),
            'pnl_loss_ratio': Decimal('0'),
        }

    pnl_all_time = float(row[0])
    account_value = float(row[1]) if row[1] else 0

    # 亏损倍数：|历史总亏损| / 当前账户价值（只有亏损时才有意义）
    if pnl_all_time < 0 and account_value > 0:
        pnl_loss_ratio = abs(pnl_all_time) / account_value
    else:
        pnl_loss_ratio = 0.0

    return {
        'pnl_all_time': Decimal(str(round(pnl_all_time, 6))),
        'pnl_loss_ratio': Decimal(str(round(pnl_loss_ratio, 4))),
    }


def calculate_features(address: str) -> Optional[Dict]:
    """
    计算单个地址的所有特征

    Returns:
        特征字典，数据不足时返回 None
    """
    print(f"\n[计算特征] {address}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        basic = calculate_basic_stats(address, cursor)
        if not basic:
            return None

        risk = calculate_risk_indicators(address, cursor)
        behavior = calculate_behavior_indicators(address, cursor)
        pnl = calculate_pnl_features(address, cursor)

        features = {**basic, **risk, **behavior, **pnl}

        print(f"   ✅ 特征计算完成")
        print(f"      胜率: {features['win_rate']:.2f}% | 盈亏比: {features['profit_loss_ratio']:.2f}")
        print(f"      平均杠杆: {features['avg_leverage']:.1f}x | 保证金使用率: {features['avg_margin_utilization']:.1f}%")
        print(f"      全仓止损次数: {features['full_close_loss_count']} | 币种集中度: {features['coin_concentration']:.1f}%")
        print(f"      历史总盈亏: {features['pnl_all_time']:.0f} USDC | 亏损倍数: {features['pnl_loss_ratio']:.1f}x")

        return features

    except Exception as e:
        print(f"   ❌ 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()


def save_features(address: str, features: Dict) -> int:
    """
    保存特征到 hl_address_features 表

    Returns:
        插入的 feature_id
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO hl_address_features (
                address, calculated_at,
                data_period_start, data_period_end,
                total_trades, win_rate, avg_win_pnl, avg_loss_pnl,
                profit_loss_ratio, total_realized_pnl, total_fee,
                avg_leverage, max_leverage,
                avg_margin_utilization, max_margin_utilization,
                coin_concentration, liquidation_count, max_drawdown,
                active_days, avg_trades_per_day, last_trade_time
            ) VALUES (
                %s, NOW(),
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
        ''', (
            address,
            features['data_period_start'],
            features['data_period_end'],
            features['total_trades'],
            features['win_rate'],
            features['avg_win_pnl'],
            features['avg_loss_pnl'],
            features['profit_loss_ratio'],
            features['total_realized_pnl'],
            features['total_fee'],
            features['avg_leverage'],
            features['max_leverage'],
            features['avg_margin_utilization'],
            features['max_margin_utilization'],
            features['coin_concentration'],
            features['full_close_loss_count'],   # → liquidation_count 字段复用
            features['pnl_loss_ratio'],           # → max_drawdown 字段复用存亏损倍数
            features['active_days'],
            features['avg_trades_per_day'],
            features['last_trade_time'],
        ))

        conn.commit()
        feature_id = cursor.lastrowid
        print(f"   💾 特征已保存（ID: {feature_id}）")
        return feature_id

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    """
    主函数

    用法：
        python calculate_address_features.py              # 计算所有 active 地址
        python calculate_address_features.py <address>   # 计算单个地址
    """
    print("=" * 70)
    print("地址特征计算")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if len(sys.argv) > 1:
        addresses = [sys.argv[1]]
    else:
        print("\n📋 正在获取地址列表...")
        addresses = get_active_addresses()
        if not addresses:
            print("❌ 没有找到活跃地址")
            return
        print(f"✅ 找到 {len(addresses)} 个活跃地址")

    success_count = skip_count = fail_count = 0

    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}] {address}")
        try:
            features = calculate_features(address)
            if not features:
                skip_count += 1
                continue
            save_features(address, features)
            success_count += 1
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"执行完成! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ 成功: {success_count} | ⚠️ 跳过: {skip_count} | ❌ 失败: {fail_count} | 总计: {len(addresses)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
