"""
计算地址特征并保存到 hl_address_features 表
基于 hl_fills 和 hl_position_snapshots 计算各项指标
"""
import sys
import os
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection


def get_active_addresses() -> List[str]:
    """获取所有活跃地址"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT address 
            FROM hl_address_list 
            WHERE status = 'active'
            ORDER BY last_updated_at DESC
        ''')
        
        return [row[0] for row in cursor.fetchall()]
        
    finally:
        cursor.close()
        conn.close()


def calculate_basic_stats(address: str, cursor) -> Dict:
    """
    计算基础统计指标（基于 hl_fills）
    
    Returns:
        包含基础统计的字典
    """
    print(f"   📊 计算基础统计...")
    
    # 1. 总交易次数、胜率、盈亏
    cursor.execute('''
        SELECT 
            COUNT(*) as total_trades,
            COUNT(CASE WHEN closed_pnl > 0 THEN 1 END) as win_count,
            AVG(CASE WHEN closed_pnl > 0 THEN closed_pnl END) as avg_win_pnl,
            AVG(CASE WHEN closed_pnl < 0 THEN closed_pnl END) as avg_loss_pnl,
            SUM(closed_pnl) as total_realized_pnl,
            SUM(fee) as total_fee,
            MIN(time) as data_start,
            MAX(time) as data_end
        FROM hl_fills
        WHERE address = %s
          AND closed_pnl != 0  -- 排除开仓订单
    ''', (address,))
    
    row = cursor.fetchone()
    
    if not row or row[0] == 0:
        print(f"   ⚠️ 无交易数据")
        return None
    
    total_trades, win_count, avg_win_pnl, avg_loss_pnl, total_pnl, total_fee, data_start, data_end = row
    
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    profit_loss_ratio = abs(avg_win_pnl / avg_loss_pnl) if avg_loss_pnl and avg_loss_pnl < 0 else 0
    
    # 2. 活跃天数
    days = (data_end - data_start) / 1000 / 86400
    avg_trades_per_day = total_trades / days if days > 0 else 0
    
    return {
        'total_trades': total_trades,
        'win_rate': Decimal(str(win_rate)),
        'avg_win_pnl': Decimal(str(avg_win_pnl or 0)),
        'avg_loss_pnl': Decimal(str(avg_loss_pnl or 0)),
        'profit_loss_ratio': Decimal(str(profit_loss_ratio)),
        'total_realized_pnl': Decimal(str(total_pnl or 0)),
        'total_fee': Decimal(str(total_fee or 0)),
        'data_period_start': data_start,
        'data_period_end': data_end,
        'active_days': int(days),
        'avg_trades_per_day': Decimal(str(avg_trades_per_day)),
        'last_trade_time': data_end
    }


def calculate_risk_indicators(address: str, cursor) -> Dict:
    """
    计算风险指标（基于 hl_position_snapshots 和 hl_position_details）
    
    Returns:
        包含风险指标的字典
    """
    print(f"   ⚙️ 计算风险指标...")
    
    # 1. 平均杠杆和保证金使用率
    cursor.execute('''
        SELECT 
            AVG(d.leverage_value) as avg_leverage,
            MAX(d.leverage_value) as max_leverage,
            AVG(s.total_margin_used / s.account_value * 100) as avg_margin_util,
            MAX(s.total_margin_used / s.account_value * 100) as max_margin_util
        FROM hl_position_details d
        JOIN hl_position_snapshots s ON d.snapshot_id = s.id
        WHERE s.address = %s
          AND s.account_value > 0
    ''', (address,))
    
    row = cursor.fetchone()
    
    if not row or row[0] is None:
        return {
            'avg_leverage': Decimal('0'),
            'max_leverage': Decimal('0'),
            'avg_margin_utilization': Decimal('0'),
            'max_margin_utilization': Decimal('0'),
            'coin_concentration': Decimal('0')
        }
    
    avg_lev, max_lev, avg_margin, max_margin = row
    
    # 2. 单币种集中度（最新快照）
    cursor.execute('''
        SELECT 
            MAX(ABS(d.position_value)) / SUM(ABS(d.position_value)) * 100 as concentration
        FROM hl_position_details d
        JOIN hl_position_snapshots s ON d.snapshot_id = s.id
        WHERE s.address = %s
          AND s.snapshot_time = (
              SELECT MAX(snapshot_time) 
              FROM hl_position_snapshots 
              WHERE address = %s
          )
    ''', (address, address))
    
    concentration_row = cursor.fetchone()
    concentration = concentration_row[0] if concentration_row and concentration_row[0] else 0
    
    return {
        'avg_leverage': Decimal(str(avg_lev or 0)),
        'max_leverage': Decimal(str(max_lev or 0)),
        'avg_margin_utilization': Decimal(str(avg_margin or 0)),
        'max_margin_utilization': Decimal(str(max_margin or 0)),
        'coin_concentration': Decimal(str(concentration))
    }


def calculate_liquidation_count(address: str, cursor) -> int:
    """
    估算清算次数（基于 hl_fills 推断）
    
    逻辑：大额亏损 + 持仓清空 = 疑似清算
    """
    print(f"   🔥 计算清算次数...")
    
    cursor.execute('''
        SELECT COUNT(*) 
        FROM hl_fills
        WHERE address = %s
          AND closed_pnl < -1000  -- 大额亏损
          AND ABS(ABS(start_position) - ABS(sz)) < 0.01  -- 持仓清空
    ''', (address,))
    
    return cursor.fetchone()[0]


def calculate_max_drawdown(address: str, cursor) -> Decimal:
    """
    计算最大回撤（基于 hl_position_snapshots）
    """
    print(f"   📉 计算最大回撤...")
    
    cursor.execute('''
        SELECT account_value
        FROM hl_position_snapshots
        WHERE address = %s
        ORDER BY snapshot_time ASC
    ''', (address,))
    
    values = [float(row[0]) for row in cursor.fetchall()]
    
    if len(values) < 2:
        return Decimal('0')
    
    max_value = values[0]
    max_drawdown = 0
    
    for value in values:
        if value > max_value:
            max_value = value
        drawdown = (max_value - value) / max_value * 100 if max_value > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    return Decimal(str(max_drawdown))


def calculate_features(address: str) -> Optional[Dict]:
    """
    计算单个地址的所有特征
    
    Returns:
        特征字典，如果数据不足返回 None
    """
    print(f"\n[计算特征] {address[:10]}...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. 基础统计
        basic_stats = calculate_basic_stats(address, cursor)
        if not basic_stats:
            return None
        
        # 2. 风险指标
        risk_indicators = calculate_risk_indicators(address, cursor)
        
        # 3. 清算次数
        liquidation_count = calculate_liquidation_count(address, cursor)
        
        # 4. 最大回撤
        max_drawdown = calculate_max_drawdown(address, cursor)
        
        # 合并所有特征
        features = {
            **basic_stats,
            **risk_indicators,
            'liquidation_count': liquidation_count,
            'max_drawdown': max_drawdown
        }
        
        print(f"   ✅ 特征计算完成")
        print(f"      胜率: {features['win_rate']:.2f}%")
        print(f"      平均杠杆: {features['avg_leverage']:.1f}x")
        print(f"      清算次数: {liquidation_count}")
        
        return features
        
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
            features['liquidation_count'],
            features['max_drawdown'],
            features['active_days'],
            features['avg_trades_per_day'],
            features['last_trade_time']
        ))
        
        conn.commit()
        feature_id = cursor.lastrowid
        
        print(f"   💾 特征已保存（ID: {feature_id}）")
        return feature_id
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        raise
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("=" * 70)
    print("地址特征计算")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 获取所有活跃地址
    print("\n📋 正在获取地址列表...")
    addresses = get_active_addresses()
    
    if not addresses:
        print("❌ 没有找到活跃地址")
        return
    
    print(f"✅ 找到 {len(addresses)} 个活跃地址\n")
    
    # 2. 逐个计算特征
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}] {address}")
        
        try:
            # 计算特征
            features = calculate_features(address)
            
            if not features:
                print(f"   ⚠️ 跳过（数据不足）")
                skip_count += 1
                continue
            
            # 保存特征
            save_features(address, features)
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ 计算失败: {e}")
            fail_count += 1
    
    # 3. 统计结果
    print("\n" + "=" * 70)
    print("执行完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n统计:")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ⚠️ 跳过: {skip_count}")
    print(f"  ❌ 失败: {fail_count}")
    print(f"  📋 总计: {len(addresses)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
