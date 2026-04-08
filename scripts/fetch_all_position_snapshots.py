"""
批量获取 hl_address_list 中所有地址的持仓快照
轮询所有活跃地址并获取持仓状态
"""
import sys
import os
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info
from utils.db_utils import get_connection


def get_active_addresses() -> List[tuple]:
    """
    从 hl_address_list 获取所有活跃地址
    
    Returns:
        地址列表 [(address, label), ...]
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT address, label 
            FROM hl_address_list 
            WHERE status = 'active'
            ORDER BY last_updated_at DESC
        ''')
        
        addresses = cursor.fetchall()
        return addresses
        
    finally:
        cursor.close()
        conn.close()


def fetch_clearinghouse_state(address: str) -> Optional[Dict]:
    """
    获取地址的持仓状态
    
    Args:
        address: 钱包地址
        
    Returns:
        持仓状态数据，失败返回 None
    """
    try:
        info = Info(skip_ws=True)
        state = info.user_state(address)
        return state
        
    except Exception as e:
        print(f"   ❌ 获取失败: {e}")
        return None


def save_snapshot(address: str, state: Dict) -> bool:
    """
    保存持仓快照到数据库
    
    Args:
        address: 钱包地址
        state: clearinghouseState 数据
        
    Returns:
        是否保存成功
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 提取账户汇总数据
        margin = state.get('marginSummary', {})
        snapshot_time = state.get('time')
        
        # 插入账户快照
        cursor.execute('''
            INSERT IGNORE INTO hl_position_snapshots 
            (address, snapshot_time, account_value, total_margin_used, 
             total_raw_usd, total_ntl_pos, withdrawable)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            address,
            snapshot_time,
            Decimal(str(margin.get('accountValue', 0))),
            Decimal(str(margin.get('totalMarginUsed', 0))),
            Decimal(str(margin.get('totalRawUsd', 0))),
            Decimal(str(margin.get('totalNtlPos', 0))),
            Decimal(str(state.get('withdrawable', 0)))
        ))
        
        # 获取 snapshot_id
        if cursor.rowcount == 0:
            # 已存在，获取现有 ID
            cursor.execute('''
                SELECT id FROM hl_position_snapshots 
                WHERE address = %s AND snapshot_time = %s
            ''', (address, snapshot_time))
            result = cursor.fetchone()
            if not result:
                return False
            snapshot_id = result[0]
        else:
            snapshot_id = cursor.lastrowid
        
        # 插入持仓明细
        positions = state.get('assetPositions', [])
        if positions:
            for pos_data in positions:
                pos = pos_data.get('position', {})
                leverage = pos.get('leverage', {})
                cum_funding = pos.get('cumFunding', {})
                
                cursor.execute('''
                    INSERT INTO hl_position_details 
                    (snapshot_id, coin, szi, entry_px, position_value, unrealized_pnl,
                     return_on_equity, liquidation_px, margin_used, leverage_type,
                     leverage_value, max_leverage, cum_funding_all_time, cum_funding_since_open)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    snapshot_id,
                    pos.get('coin'),
                    Decimal(str(pos.get('szi', 0))),
                    Decimal(str(pos.get('entryPx', 0))),
                    Decimal(str(pos.get('positionValue', 0))),
                    Decimal(str(pos.get('unrealizedPnl', 0))),
                    Decimal(str(pos.get('returnOnEquity', 0))),
                    Decimal(str(pos.get('liquidationPx'))) if pos.get('liquidationPx') else None,
                    Decimal(str(pos.get('marginUsed', 0))),
                    leverage.get('type'),
                    leverage.get('value'),
                    pos.get('maxLeverage'),
                    Decimal(str(cum_funding.get('allTime', 0))),
                    Decimal(str(cum_funding.get('sinceOpen', 0)))
                ))
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        return False
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("=" * 70)
    print("批量获取地址持仓快照")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 获取所有活跃地址
    print("\n📋 正在获取地址列表...")
    addresses = get_active_addresses()
    
    if not addresses:
        print("❌ 没有找到活跃地址")
        return
    
    print(f"✅ 找到 {len(addresses)} 个活跃地址\n")
    
    # 2. 逐个获取持仓快照
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, (address, label) in enumerate(addresses, 1):
        print(f"[{i}/{len(addresses)}] {label or address[:10] + '...'}")
        print(f"   地址: {address}")
        
        # 获取持仓状态
        state = fetch_clearinghouse_state(address)
        
        if not state:
            print(f"   ⚠️ 无持仓数据或获取失败")
            skip_count += 1
            print()
            continue
        
        # 显示账户信息
        margin = state.get('marginSummary', {})
        account_value = margin.get('accountValue', 0)
        positions = state.get('assetPositions', [])
        
        print(f"   💰 账户价值: {account_value} USDC")
        print(f"   📊 持仓数量: {len(positions)} 个")
        
        # 保存到数据库
        if save_snapshot(address, state):
            print(f"   ✅ 保存成功")
            success_count += 1
        else:
            print(f"   ❌ 保存失败")
            fail_count += 1
        
        print()
    
    # 3. 统计结果
    print("=" * 70)
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
