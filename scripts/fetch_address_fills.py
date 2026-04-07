"""
获取指定地址的交易历史 (fills) - 优化版
使用批量插入提高性能，自动使用北京时间
"""
import sys
import os
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info
from utils.db_utils import get_connection


def fetch_fills(address: str) -> List[Dict]:
    """获取地址的交易历史"""
    print(f"\n📥 正在获取地址交易数据...")
    print(f"   地址: {address}")
    
    try:
        info = Info(skip_ws=True)
        fills = info.user_fills(address)
        
        print(f"✅ 成功获取 {len(fills)} 条 fills")
        
        # 显示前 3 条
        if fills:
            print(f"\n=== 前 3 条数据示例 ===")
            for i, fill in enumerate(fills[:3], 1):
                print(f"[{i}] {fill.get('coin')} | {fill.get('dir')} | 数量:{fill.get('sz')} | 价格:{fill.get('px')} | PnL:{fill.get('closedPnl', 0)}")
        
        return fills
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []


def save_fills_batch(address: str, fills: List[Dict]) -> int:
    """
    批量保存 fills（使用 INSERT IGNORE 跳过重复）
    时间字段自动使用北京时间（数据库连接已设置时区为 Asia/Shanghai）
    """
    if not fills:
        print("\n⚠️ 没有数据需要保存")
        return 0
    
    print(f"\n💾 正在批量保存到数据库...")
    print(f"   总数: {len(fills)} 条")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 准备批量插入数据
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
                fill.get('time', 0),
                fill.get('hash', ''),
                fill.get('side', '')
            ))
        
        # 批量插入（使用 INSERT IGNORE 跳过重复的 hash）
        sql = '''
            INSERT IGNORE INTO hl_fills 
            (address, coin, sz, px, dir, closed_pnl, fee, time, hash, side)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    """更新地址的最后更新时间（使用北京时间）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # NOW() 会自动使用会话时区（已设置为 +08:00）
        cursor.execute('''
            UPDATE hl_address_list 
            SET last_updated_at = NOW() 
            WHERE address = %s
        ''', (address,))
        conn.commit()
        print(f"✅ 已更新地址最后更新时间（北京时间）")
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
    
    print("=" * 60)
    print("Hyperliquid 地址交易数据获取（优化版）")
    print("=" * 60)
    
    # 1. 获取 fills
    fills = fetch_fills(address)
    
    if not fills:
        print("\n❌ 未获取到任何数据")
        return
    
    # 2. 批量保存到数据库
    inserted = save_fills_batch(address, fills)
    
    # 3. 更新地址最后更新时间
    if inserted > 0:
        update_address_last_updated(address)
    
    print("\n" + "=" * 60)
    print(f"✅ 完成! 成功保存 {inserted} 条新数据")
    print("=" * 60)


if __name__ == '__main__':
    main()
