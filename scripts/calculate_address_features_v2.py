"""
计算地址特征并保存到 hl_address_features 表（v2 新评分模型）
基于 hl_fills 和 hl_position_snapshots 计算各项指标

新增特征：
  - liquidation_per_month: 清算次数/月（官方清算 + 近似清算）
  - has_refill_behavior: 是否有后续补仓行为
  - consecutive_loss_add_count: 连续亏损后加仓次数
  - add_position_score: 加仓效果得分（双向±分）
  - scalping_score: 做T行为得分（双向±分）
"""
import sys
import os
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

# 清算识别阈值
FULL_CLOSE_DIFF_THRESHOLD = 0.02  # sz 与 start_position 差异 < 2%
NEAR_LIQUIDATION_LOSS_PCT = 0.5   # 亏损占名义价值 >= 50%


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
    """计算基础统计指标（胜率/盈亏比/交易频率）"""
    print(f"   📊 基础统计...")

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
    profit_loss_ratio = abs(float(avg_win or 0)) / abs(float(avg_loss or 1)) if avg_loss and avg_loss < 0 else 0
    days = (data_end - data_start) / 1000 / 86400 if data_end and data_start else 0
    avg_trades_per_day = total_close / days if days > 0 else 0

    return {
        'total_trades': int(total_close),
        'win_rate': Decimal(str(round(win_rate, 2))),
        'avg_win_pnl': Decimal(str(round(float(avg_win or 0), 6))),
        'avg_loss_pnl': Decimal(str(round(float(avg_loss or 0), 6))),
        'profit_loss_ratio': Decimal(str(round(profit_loss_ratio, 2))),
        'total_realized_pnl': Decimal(str(round(float(total_pnl or 0), 6))),
        'total_fee': Decimal(str(round(float(total_fee or 0), 6))),
        'data_period_start': int(data_start) if data_start else 0,
        'data_period_end': int(data_end) if data_end else 0,
        'active_days': int(days),
        'avg_trades_per_day': Decimal(str(round(avg_trades_per_day, 2))),
        'last_trade_time': int(data_end) if data_end else 0,
    }


def calculate_leverage_from_snapshots(address: str, cursor) -> Dict:
    """从快照计算账户整体杠杆（total_ntl_pos / account_value）"""
    print(f"   ⚙️ 账户杠杆（快照）...")

    cursor.execute('''
        SELECT
            AVG(total_ntl_pos / NULLIF(account_value, 0)) as avg_leverage,
            MAX(total_ntl_pos / NULLIF(account_value, 0)) as max_leverage,
            AVG(total_margin_used / NULLIF(account_value, 0) * 100) as avg_margin_util,
            MAX(total_margin_used / NULLIF(account_value, 0) * 100) as max_margin_util
        FROM hl_position_snapshots
        WHERE address = %s AND account_value > 0 AND total_ntl_pos > 0
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
        'avg_margin_utilization': Decimal(str(round(float(row[2] or 0), 2))),
        'max_margin_utilization': Decimal(str(round(float(row[3] or 0), 2))),
    }


def calculate_liquidation_stats(address: str, cursor) -> Dict:
    """
    计算清算统计（官方清算 + 近似清算）
    
    近似清算定义：
      - sz ≈ |start_position|（全仓平）
      - closed_pnl < 0
      - |closed_pnl| / (sz × px) >= 50%
    """
    print(f"   🔥 清算统计...")

    # 官方清算
    cursor.execute('''
        SELECT COUNT(*) FROM hl_fills
        WHERE address = %s AND dir LIKE 'Liquidat%%'
    ''', (address,))
    official_liq = cursor.fetchone()[0] or 0

    # 近似清算
    cursor.execute('''
        SELECT COUNT(*) FROM hl_fills
        WHERE address = %s
          AND dir LIKE 'Close%%'
          AND closed_pnl < 0
          AND start_position > 0
          AND ABS(sz - ABS(start_position)) / NULLIF(ABS(start_position), 0) < %s
          AND ABS(closed_pnl) / NULLIF(ABS(sz * px), 0) >= %s
    ''', (address, FULL_CLOSE_DIFF_THRESHOLD, NEAR_LIQUIDATION_LOSS_PCT))
    near_liq = cursor.fetchone()[0] or 0

    total_liq = official_liq + near_liq

    # 活跃月数
    cursor.execute('SELECT MIN(time), MAX(time) FROM hl_fills WHERE address = %s', (address,))
    row = cursor.fetchone()
    if row and row[0] and row[1]:
        days = (row[1] - row[0]) / 1000 / 86400
        months = days / 30 if days > 0 else 0
        liq_per_month = total_liq / months if months > 0 else 0
    else:
        liq_per_month = 0

    print(f"      官方清算: {official_liq} | 近似清算: {near_liq} | 清算/月: {liq_per_month:.2f}")

    return {
        'liquidation_count': int(total_liq),
        'liquidation_per_month': Decimal(str(round(liq_per_month, 2))),
    }


def calculate_refill_behavior(address: str, cursor) -> Dict:
    """
    是否有后续补仓行为
    
    识别：同 coin + 同方向，持仓未归零前再次 Open
    """
    print(f"   📈 补仓行为...")

    cursor.execute('''
        SELECT coin, dir, time, sz, start_position
        FROM hl_fills
        WHERE address = %s AND (dir LIKE 'Open%%' OR dir LIKE 'Close%%')
        ORDER BY coin, time
    ''', (address,))

    fills = cursor.fetchall()
    has_refill = False

    # 简化判断：同一 coin，连续两次 Open 且中间没有归零
    by_coin = defaultdict(list)
    for coin, dir, time, sz, start_pos in fills:
        by_coin[coin].append((dir, time, float(sz), float(start_pos or 0)))

    for coin, trades in by_coin.items():
        for i in range(len(trades) - 1):
            curr_dir, curr_time, curr_sz, curr_start = trades[i]
            next_dir, next_time, next_sz, next_start = trades[i + 1]
            
            # 连续两次 Open
            if 'Open' in curr_dir and 'Open' in next_dir:
                has_refill = True
                break
        if has_refill:
            break

    return {'has_refill_behavior': int(has_refill)}


def calculate_consecutive_loss_add(address: str, cursor) -> Dict:
    """
    连续亏损后加仓次数 + 最长连续亏损笔数
    
    改进逻辑（方案D）：
      - 同 coin + 同方向 + 1小时内的连续 Close，算同一次亏损事件
      - 中间有盈利 Close，归零计数
      - 同时统计最长连续亏损笔数
    """
    print(f"   🎲 连续亏损分析...")

    cursor.execute('''
        SELECT dir, coin, closed_pnl, time
        FROM hl_fills
        WHERE address = %s
        ORDER BY time
    ''', (address,))

    fills = cursor.fetchall()
    
    TIME_WINDOW_MS = 3600000  # 1小时
    consecutive_loss_count = 0
    consecutive_loss_add_count = 0
    max_consecutive_loss = 0
    
    last_close_coin = None
    last_close_dir = None
    last_close_time = 0

    for i, (dir, coin, pnl, time) in enumerate(fills):
        if 'Close' in dir:
            pnl_val = float(pnl or 0)
            
            # 判断是否同一持仓的分批平仓
            is_same_position = (
                coin == last_close_coin and
                ('Long' in dir and 'Long' in last_close_dir or 'Short' in dir and 'Short' in last_close_dir) and
                (time - last_close_time < TIME_WINDOW_MS)
            )
            
            if pnl_val < 0:
                if not is_same_position:
                    consecutive_loss_count += 1  # 新一轮亏损
                    max_consecutive_loss = max(max_consecutive_loss, consecutive_loss_count)
            else:
                consecutive_loss_count = 0  # 盈利归零
            
            last_close_coin = coin
            last_close_dir = dir
            last_close_time = time
            
        elif 'Open' in dir and consecutive_loss_count >= 2:
            consecutive_loss_add_count += 1
            # 注意：加仓后不归零 consecutive_loss_count，继续累计

    return {
        'consecutive_loss_add_count': int(consecutive_loss_add_count),
        'max_consecutive_loss_count': int(max_consecutive_loss),
    }


def calculate_add_position_score(address: str, cursor) -> Dict:
    """
    加仓效果得分（双向±分）
    
    简化版本：按 coin 分组，统计加仓后最终盈亏
      - 加仓后亏损扩大 > 20% → +4分/次（上限+8分）
      - 加仓后成功减亏且最终盈利 → -3分/次（下限-6分）
    """
    print(f"   💰 加仓效果（简化）...")
    # TODO: 完整版需要持仓状态机，此处先返回 0
    return {'add_position_score': Decimal('0')}


def calculate_scalping_score(address: str, cursor) -> Dict:
    """
    做T行为得分（双向±分）
    
    识别：同 coin，持仓周期内 Open/Close 交替 >= 2次
    """
    print(f"   ⚡ 做T行为（简化）...")
    # TODO: 完整版需要精细识别，此处先返回 0
    return {'scalping_score': Decimal('0')}


def calculate_other_features(address: str, cursor) -> Dict:
    """其他特征：币种集中度"""
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

    return {'coin_concentration': Decimal(str(round(coin_concentration, 2)))}


def calculate_features(address: str) -> Optional[Dict]:
    """计算单个地址的所有特征"""
    print(f"\n[计算特征] {address}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        basic = calculate_basic_stats(address, cursor)
        if not basic:
            return None

        leverage = calculate_leverage_from_snapshots(address, cursor)
        liquidation = calculate_liquidation_stats(address, cursor)
        refill = calculate_refill_behavior(address, cursor)
        consecutive_loss = calculate_consecutive_loss_add(address, cursor)
        add_score = calculate_add_position_score(address, cursor)
        scalping = calculate_scalping_score(address, cursor)
        other = calculate_other_features(address, cursor)

        features = {**basic, **leverage, **liquidation, **refill, **consecutive_loss, **add_score, **scalping, **other}

        print(f"   ✅ 完成")
        print(f"      胜率: {features['win_rate']}% | 杠杆: {features['avg_leverage']}x | 清算/月: {features['liquidation_per_month']}")
        print(f"      补仓: {'有' if features['has_refill_behavior'] else '无'} | 连亏后加仓: {features['consecutive_loss_add_count']}次")

        return features

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()


def save_features(address: str, features: Dict) -> int:
    """保存特征到 hl_address_features 表"""
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
                coin_concentration, liquidation_count, liquidation_per_month,
                has_refill_behavior, consecutive_loss_add_count, max_consecutive_loss_count,
                add_position_score, scalping_score,
                active_days, avg_trades_per_day, last_trade_time
            ) VALUES (
                %s, NOW(),
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s
            )
        ''', (
            address,
            features['data_period_start'], features['data_period_end'],
            features['total_trades'], features['win_rate'], features['avg_win_pnl'], features['avg_loss_pnl'],
            features['profit_loss_ratio'], features['total_realized_pnl'], features['total_fee'],
            features['avg_leverage'], features['max_leverage'],
            features['avg_margin_utilization'], features['max_margin_utilization'],
            features['coin_concentration'], features['liquidation_count'], features['liquidation_per_month'],
            features['has_refill_behavior'], features['consecutive_loss_add_count'], features['max_consecutive_loss_count'],
            features['add_position_score'], features['scalping_score'],
            features['active_days'], features['avg_trades_per_day'], features['last_trade_time'],
        ))

        conn.commit()
        feature_id = cursor.lastrowid
        print(f"   💾 已保存（ID: {feature_id}）")
        return feature_id

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    print("=" * 70)
    print("地址特征计算 v2（新评分模型）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if len(sys.argv) > 1:
        addresses = [sys.argv[1]]
    else:
        print("\n📋 获取地址列表...")
        addresses = get_active_addresses()
        if not addresses:
            print("❌ 无活跃地址")
            return
        print(f"✅ {len(addresses)} 个地址")

    success_count = skip_count = fail_count = 0

    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}]")
        try:
            features = calculate_features(address)
            if not features:
                skip_count += 1
                continue
            save_features(address, features)
            success_count += 1
        except Exception as e:
            print(f"   ❌ {e}")
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"完成! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ {success_count} | ⚠️ {skip_count} | ❌ {fail_count} | 总计: {len(addresses)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
