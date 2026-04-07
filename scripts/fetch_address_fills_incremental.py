"""
增量获取地址交易历史 (fills)
只获取上次更新后的新数据
"""
import sys
import os
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info
from utils.db_utils import get_connection


def get_last_fill_time(address: str) -> Optional[int]:
    """
    获取数据库中该地址最新的 fill 时间戳
    
    Returns:
        最新时间戳（毫秒），如果没有数据则返回 None
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT MAX(time) FROM hl_fills 
            WHERE address = %s
        ''', (address,))
        
        result = cursor.fetchone()
        last_time = result[0] if result else None
        
        if last_time:
            from datetime import datetime
            dt = datetime.fromtimestamp(last_time / 1000)
            print(f"📅 数据库中最新记录时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"📅 数据库中无该地址记录，将获取全部历史")
        
        return last_time
        
    finally:
        cursor.close()
        conn.close()


def fetch_fills_incremental(address: str, start_time: Optional[int] = None) -> List[Dict]:
    """
    增量获取 fills
    
    Args:
        address: 钱包地址
        start_time: 起始时间戳（毫秒），None 则获取全部
    """
    print(f"\n📥 正在获取地址交易数据（增量模式）...")
    print(f"   地址: {address}")
    
    try:
        info = Info(skip_ws=True)
        
        if start_time:
            # 从上次时间 +1ms 开始获取（避免重复）
            fills = info.user_fills_by_time(address, start_time=start_time + 1)
            print(f"   起始时间: {start_time + 1} (上次时间 +1ms)")
        else:
            # 获取全部历史
            fills = info.user_fills(address)
            print(f"   模式: 全量获取")
        
        print(f"✅ 成功获取 {len(fills)} 条 fills")
        
        if fills:
            print(f"\n=== 新数据示例（前3条）===")
            for i, fill in enumerate(fills[:3], 1):
                from datetime import datetime
                dt = datetime.fromtimestamp(fill.get('time', 0) / 1000)
                print(f"[{i}] {dt.strftime('%Y-%m-%d %H:%M:%S')} | {fill.get('coin')} | {fill.get('dir')} | 数量:{fill.get('sz')} | PnL:{fill.get('closedPnl', 0)}")
        
        return fills
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_fills_batch(address: str, fills: List[Dict]) -> int:
    """批量保存 fills（使用 INSERT IGNORE 跳过重复）"""
    if not fills:
        print("\n⚠️ 没有新数据需要保存")
        return 0
    
    print(f"\n💾 正在批量保存到数据库...")
    print(f"   总数: {len(fills)} 条")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        values = []
        for fill in fills:
            values.append((
                address,
                fill.get('coin', ''),
                fill.get('sz', 0),
                fill.get('px', 0),
                fill.get('dir', ''),
                fill.get('closedPnl', 0),
                fill.get('fee', 0),
                fill.get('feeToken', 'USDC'),
                fill.get('time', 0),
                fill.get('hash', ''),
                fill.get('tid', 0),
                fill.get('oid', 0),
                fill.get('twapId'),
                fill.get('side', ''),
                fill.get('startPosition', 0),
                fill.get('crossed', True)
            ))
        
        sql = '''
            INSERT IGNORE INTO hl_fills 
            (address, coin, sz, px, dir, closed_pnl, fee, fee_token, time, hash, tid, oid, twap_id, side, start_position, crossed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        
        # 分批插入（每批 500 条）
        batch_size = 500
        total_inserted = 0
        
        for i in range(0, len(values), batch_size):
            batch = values[i:i+batch_size]
            cursor.executemany(sql, batch)
            conn.commit()
            total_inserted += cursor.rowcount
            print(f"   进度: {min(i+batch_size, len(values))}/{len(values)} ({total_inserted} 条新增)")
        
        print(f"\n✅ 保存完成!")
        print(f"   ✓ 新增: {total_inserted} 条")
        print(f"   - 重复跳过: {len(fills) - total_inserted} 条")
        
        return total_inserted
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return 0
        
    finally:
        cursor.close()
        conn.close()


def update_address_last_updated(address: str):
    """更新地址的最后更新时间"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE hl_address_list 
            SET last_updated_at = NOW() 
            WHERE address = %s
        ''', (address,))
        conn.commit()
        
        # 获取更新后的时间
        cursor.execute('''
            SELECT last_updated_at FROM hl_address_list 
            WHERE address = %s
        ''', (address,))
        result = cursor.fetchone()
        if result:
            print(f"✅ 已更新地址最后更新时间: {result[0]}")
            
    except Exception as e:
        print(f"⚠️ 更新地址时间失败: {e}")
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872'
    
    print("=" * 70)
    print("Hyperliquid 地址交易数据获取（增量更新模式）")
    print("=" * 70)
    
    # 1. 获取数据库中最新的 fill 时间
    last_time = get_last_fill_time(address)
    
    # 2. 增量获取 fills
    fills = fetch_fills_incremental(address, start_time=last_time)
    
    if not fills:
        print("\n✅ 没有新数据")
        return
    
    # 3. 批量保存到数据库
    inserted = save_fills_batch(address, fills)
    
    # 4. 更新地址最后更新时间
    if inserted > 0:
        update_address_last_updated(address)
    
    print("\n" + "=" * 70)
    print(f"✅ 完成! 成功保存 {inserted} 条新数据")
    print("=" * 70)


if __name__ == '__main__':
    main()
