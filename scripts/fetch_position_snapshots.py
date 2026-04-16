"""
获取地址的持仓快照（clearinghouseState）
包括账户价值、保证金使用、持仓明细等
"""
import sys
import os
from typing import List, Dict, Optional
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info
from utils.db_utils import get_connection


def get_fund_level_by_account_value(account_value: Decimal) -> Optional[str]:
    """
    根据 accountValue 映射资金等级
    - L1: [2,000, 5,000)
    - L2: [5,000, 20,000)
    - L3: [20,000, 50,000)
    - L4: [50,000, 100,000)
    - L5: [100,000, +inf)
    """
    if account_value >= Decimal("100000"):
        return "L5"
    if account_value >= Decimal("50000"):
        return "L4"
    if account_value >= Decimal("20000"):
        return "L3"
    if account_value >= Decimal("5000"):
        return "L2"
    if account_value >= Decimal("2000"):
        return "L1"
    return None


def fetch_clearinghouse_state(address: str) -> Optional[Dict]:
    """
    获取地址的持仓状态
    
    Args:
        address: 钱包地址
        
    Returns:
        持仓状态数据，失败返回 None
    """
    print(f"\n📥 正在获取地址持仓状态...")
    print(f"   地址: {address}")
    
    try:
        info = Info(skip_ws=True)
        # 使用 user_state 获取持仓状态
        state = info.user_state(address)
        
        if not state:
            print("⚠️ 地址无持仓数据")
            return None
        
        print(f"✅ 成功获取持仓快照")
        
        # 显示账户汇总
        margin = state.get('marginSummary', {})
        print(f"\n=== 账户汇总 ===")
        print(f"   账户价值: {margin.get('accountValue')} USDC")
        print(f"   已用保证金: {margin.get('totalMarginUsed')} USDC")
        print(f"   可提现: {state.get('withdrawable')} USDC")
        
        # 显示持仓
        positions = state.get('assetPositions', [])
        if positions:
            print(f"\n=== 持仓明细（{len(positions)} 个）===")
            for pos in positions:
                p = pos.get('position', {})
                coin = p.get('coin')
                szi = p.get('szi')
                direction = '多' if float(szi) > 0 else '空'
                print(f"   {coin}: {direction} {abs(float(szi))} | 未实现盈亏: {p.get('unrealizedPnl')} USDC")
        
        return state
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()
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
    print(f"\n💾 正在保存持仓快照...")
    
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
        
        # 获取刚插入的 snapshot_id
        if cursor.rowcount == 0:
            # 已存在，获取现有 ID
            cursor.execute('''
                SELECT id FROM hl_position_snapshots 
                WHERE address = %s AND snapshot_time = %s
            ''', (address, snapshot_time))
            result = cursor.fetchone()
            if not result:
                print("❌ 快照已存在但无法获取 ID")
                return False
            snapshot_id = result[0]
            print(f"   ℹ️ 快照已存在（ID: {snapshot_id}）")
        else:
            snapshot_id = cursor.lastrowid
            print(f"   ✓ 账户快照已保存（ID: {snapshot_id}）")
        
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
            
            print(f"   ✓ 持仓明细已保存（{len(positions)} 个）")
        else:
            print(f"   ℹ️ 无持仓（空仓状态）")
        
        # 同步更新 hl_address_list 资金分层与最新账户资产
        account_value_val = Decimal(str(margin.get('accountValue', 0)))
        fund_level = get_fund_level_by_account_value(account_value_val)
        cursor.execute('''
            UPDATE hl_address_list
            SET latest_account_value = %s, fund_level = %s
            WHERE address = %s
        ''', (account_value_val, fund_level, address))

        conn.commit()
        print(f"✅ 保存完成! fund_level={fund_level} account_value={account_value_val}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        # 默认地址
        address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872'
    
    print("=" * 70)
    print("Hyperliquid 地址持仓快照获取")
    print("=" * 70)
    
    # 1. 获取持仓状态
    state = fetch_clearinghouse_state(address)
    
    if not state:
        print("\n❌ 未获取到数据")
        return
    
    # 2. 保存到数据库
    success = save_snapshot(address, state)
    
    print("\n" + "=" * 70)
    if success:
        print("✅ 完成!")
    else:
        print("❌ 保存失败")
    print("=" * 70)


if __name__ == '__main__':
    main()
