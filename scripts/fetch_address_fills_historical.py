"""
回溯获取地址的历史交易数据（超过 2000 条）
分批获取并保存到数据库
"""
import sys
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info
from utils.db_utils import get_connection


def get_earliest_fill_time(address: str) -> int:
    """
    获取数据库中最早的 fill 时间
    
    Returns:
        时间戳（毫秒），如果没有数据返回当前时间
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT MIN(time) 
            FROM hl_fills 
            WHERE address = %s
        ''', (address,))
        
        result = cursor.fetchone()
        
        if result and result[0]:
            return result[0]
        else:
            # 如果没有数据，返回当前时间
            return int(time.time() * 1000)
            
    finally:
        cursor.close()
        conn.close()


def fetch_fills_batch(address: str, end_time: int, batch_size: int = 2000) -> List[Dict]:
    """
    获取一批历史 fills
    
    Args:
        address: 钱包地址
        end_time: 结束时间戳（毫秒）
        batch_size: 批次大小
        
    Returns:
        fills 列表
    """
    # 计算 start_time（往前推 30 天，确保能获取到数据）
    start_time = end_time - (30 * 24 * 60 * 60 * 1000)  # 30天前
    
    print(f"   查询时间范围:")
    print(f"      开始: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"      结束: {datetime.fromtimestamp(end_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        info = Info(skip_ws=True)
        fills = info.user_fills_by_time(address, start_time, end_time)
        
        print(f"   ✅ 获取到 {len(fills)} 条记录")
        return fills
        
    except Exception as e:
        print(f"   ❌ 获取失败: {e}")
        return []


def save_fills_batch(address: str, fills: List[Dict]) -> int:
    """
    批量保存 fills 到数据库
    
    Returns:
        实际插入的记录数
    """
    if not fills:
        return 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    inserted_count = 0
    
    try:
        for fill in fills:
            try:
                cursor.execute('''
                    INSERT IGNORE INTO hl_fills (
                        address, coin, px, sz, side, dir, closed_pnl, fee, fee_token,
                        hash, tid, oid, start_position, crossed, twap_id, time
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                ''', (
                    address,
                    fill.get('coin'),
                    Decimal(str(fill.get('px', 0))),
                    Decimal(str(fill.get('sz', 0))),
                    fill.get('side'),
                    fill.get('dir'),
                    Decimal(str(fill.get('closedPnl', 0))),
                    Decimal(str(fill.get('fee', 0))),
                    fill.get('feeToken', 'USDC'),
                    fill.get('hash'),
                    fill.get('tid'),
                    fill.get('oid'),
                    Decimal(str(fill.get('startPosition', 0))),
                    fill.get('crossed', True),
                    fill.get('twapId'),
                    fill.get('time')
                ))
                
                if cursor.rowcount > 0:
                    inserted_count += 1
                    
            except Exception as e:
                print(f"      ⚠️ 跳过一条记录: {e}")
                continue
        
        conn.commit()
        return inserted_count
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 批量保存失败: {e}")
        return 0
        
    finally:
        cursor.close()
        conn.close()


def backfill_historical_fills(address: str, target_days: int = 90):
    """
    回溯获取历史数据
    
    Args:
        address: 钱包地址
        target_days: 目标回溯天数（默认 90 天）
    """
    print(f"\n开始回溯历史数据...")
    print(f"目标: 获取最近 {target_days} 天的交易记录\n")
    
    # 1. 获取当前数据库中最早的时间
    earliest_db_time = get_earliest_fill_time(address)
    print(f"数据库中最早记录: {datetime.fromtimestamp(earliest_db_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 2. 计算目标时间（往前推 target_days 天）
    current_time = int(time.time() * 1000)
    target_time = current_time - (target_days * 24 * 60 * 60 * 1000)
    
    print(f"目标时间: {datetime.fromtimestamp(target_time/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 3. 如果已经达到目标，直接返回
    if earliest_db_time <= target_time:
        print(f"\n✅ 数据已充足（已有 {(current_time - earliest_db_time) / 86400000:.1f} 天数据）")
        return
    
    # 4. 开始回溯
    total_inserted = 0
    batch_count = 0
    end_time = earliest_db_time
    
    while end_time > target_time:
        batch_count += 1
        print(f"\n[批次 {batch_count}]")
        
        # 获取一批数据
        fills = fetch_fills_batch(address, end_time)
        
        if not fills:
            print("   ℹ️ 没有更多历史数据")
            break
        
        # 保存到数据库
        inserted = save_fills_batch(address, fills)
        total_inserted += inserted
        
        print(f"   💾 新增 {inserted} 条记录")
        
        # 更新 end_time 为本批最早的时间
        oldest_time = min(f['time'] for f in fills)
        
        # 如果这批数据的最早时间和 end_time 一样，说明没有更早的数据了
        if oldest_time >= end_time:
            print("   ℹ️ 已到达历史起点")
            break
        
        end_time = oldest_time - 1  # 往前推 1ms
        
        # 延迟 1 秒，避免 API 限流
        time.sleep(1)
    
    print(f"\n{'='*70}")
    print(f"回溯完成！")
    print(f"  批次数: {batch_count}")
    print(f"  新增记录: {total_inserted} 条")
    
    # 查询最终的数据范围
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            MIN(time) as earliest,
            MAX(time) as latest,
            COUNT(*) as total,
            FROM_UNIXTIME(MIN(time)/1000) as earliest_dt,
            FROM_UNIXTIME(MAX(time)/1000) as latest_dt,
            TIMESTAMPDIFF(DAY, FROM_UNIXTIME(MIN(time)/1000), FROM_UNIXTIME(MAX(time)/1000)) as days
        FROM hl_fills
        WHERE address = %s
    ''', (address,))
    
    row = cursor.fetchone()
    
    if row:
        print(f"\n最终数据范围:")
        print(f"  最早: {row[3]}")
        print(f"  最新: {row[4]}")
        print(f"  跨度: {row[5]} 天")
        print(f"  总数: {row[2]} 条")
    
    cursor.close()
    conn.close()
    
    print("="*70)


def main():
    """主函数"""
    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        # 默认地址
        address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872'
    
    if len(sys.argv) > 2:
        target_days = int(sys.argv[2])
    else:
        target_days = 90  # 默认回溯 90 天
    
    print("=" * 70)
    print("历史交易数据回溯")
    print(f"地址: {address}")
    print(f"目标: 最近 {target_days} 天")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    backfill_historical_fills(address, target_days)


if __name__ == '__main__':
    main()
