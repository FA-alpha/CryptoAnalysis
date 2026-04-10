"""
批量获取 hl_address_list 中所有地址的持仓快照
轮询所有活跃地址并获取持仓状态
"""
import sys
import os
import time
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from hyperliquid.info import Info
from utils.db_utils import get_connection

HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz/info"

# 定时任务执行时间窗口（北京时间 00:00 - 00:59），用于判断 snapshot_date
SCHEDULED_HOUR = 0


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
            ORDER BY id ASC
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


def fetch_portfolio_pnl(address: str) -> Dict[str, Optional[float]]:
    """
    从 portfolio 接口获取各时间维度的最新 PnL

    Args:
        address: 钱包地址

    Returns:
        {'pnl_day': float, 'pnl_week': float, 'pnl_month': float, 'pnl_all_time': float}
        获取失败时对应值为 None
    """
    result: Dict[str, Optional[float]] = {
        'pnl_day': None,
        'pnl_week': None,
        'pnl_month': None,
        'pnl_all_time': None,
    }

    period_map = {
        'perpDay': 'pnl_day',
        'perpWeek': 'pnl_week',
        'perpMonth': 'pnl_month',
        'perpAllTime': 'pnl_all_time',
    }

    try:
        resp = httpx.post(
            HYPERLIQUID_API_URL,
            json={'type': 'portfolio', 'user': address},
            headers={'Content-Type': 'application/json'},
            timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data:
            period = item[0]
            if period not in period_map:
                continue
            pnl_history = item[1].get('pnlHistory', [])
            if pnl_history:
                # 取最后一条（最新值）
                latest_pnl = float(pnl_history[-1][1])
                result[period_map[period]] = latest_pnl

    except Exception as e:
        print(f"   ⚠️ 获取 portfolio PnL 失败: {e}")

    return result


def resolve_snapshot_date(now: Optional[datetime] = None) -> date:
    """
    根据当前时间判断 snapshot_date：
    - 北京时间 00:xx（定时窗口）→ 前一天（代表昨日收盘数据）
    - 其他时间（手动执行）→ 当天

    Args:
        now: 当前时间，None 则取系统时间

    Returns:
        snapshot_date
    """
    if now is None:
        now = datetime.now()

    if now.hour == SCHEDULED_HOUR:
        return (now - timedelta(days=1)).date()
    return now.date()


def save_snapshot(address: str, state: Dict, pnl: Dict, snapshot_date: date) -> bool:
    """
    保存持仓快照到数据库

    Args:
        address: 钱包地址
        state: clearinghouseState 数据
        pnl: portfolio PnL 数据 {'pnl_day', 'pnl_week', 'pnl_month', 'pnl_all_time'}
        snapshot_date: 快照代表的日期

    Returns:
        是否保存成功
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 提取账户汇总数据
        margin = state.get('marginSummary', {})
        snapshot_time = state.get('time')

        pnl_day_val = Decimal(str(pnl['pnl_day'])) if pnl['pnl_day'] is not None else None
        pnl_week_val = Decimal(str(pnl['pnl_week'])) if pnl['pnl_week'] is not None else None
        pnl_month_val = Decimal(str(pnl['pnl_month'])) if pnl['pnl_month'] is not None else None
        pnl_all_time_val = Decimal(str(pnl['pnl_all_time'])) if pnl['pnl_all_time'] is not None else None
        account_value_val = Decimal(str(margin.get('accountValue', 0)))
        total_margin_used_val = Decimal(str(margin.get('totalMarginUsed', 0)))
        total_raw_usd_val = Decimal(str(margin.get('totalRawUsd', 0)))
        total_ntl_pos_val = Decimal(str(margin.get('totalNtlPos', 0)))
        withdrawable_val = Decimal(str(state.get('withdrawable', 0)))

        # 检查该地址当天是否已有 snapshot_date 记录（定时任务 UPDATE，手动 INSERT IGNORE）
        cursor.execute('''
            SELECT id FROM hl_position_snapshots
            WHERE address = %s AND snapshot_date = %s
        ''', (address, snapshot_date))
        existing = cursor.fetchone()

        if existing:
            # 定时任务重跑或同日二次执行 → UPDATE 最新数据
            snapshot_id = existing[0]
            cursor.execute('''
                UPDATE hl_position_snapshots
                SET snapshot_time = %s,
                    account_value = %s, total_margin_used = %s,
                    total_raw_usd = %s, total_ntl_pos = %s, withdrawable = %s,
                    pnl_day = %s, pnl_week = %s, pnl_month = %s, pnl_all_time = %s
                WHERE id = %s
            ''', (
                snapshot_time,
                account_value_val, total_margin_used_val,
                total_raw_usd_val, total_ntl_pos_val, withdrawable_val,
                pnl_day_val, pnl_week_val, pnl_month_val, pnl_all_time_val,
                snapshot_id
            ))
            print(f"   🔄 已更新当日快照（snapshot_date={snapshot_date}, id={snapshot_id})")
        else:
            # 新日期 → INSERT
            cursor.execute('''
                INSERT INTO hl_position_snapshots
                (address, snapshot_time, snapshot_date, account_value, total_margin_used,
                 total_raw_usd, total_ntl_pos, withdrawable,
                 pnl_day, pnl_week, pnl_month, pnl_all_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                address, snapshot_time, snapshot_date,
                account_value_val, total_margin_used_val,
                total_raw_usd_val, total_ntl_pos_val, withdrawable_val,
                pnl_day_val, pnl_week_val, pnl_month_val, pnl_all_time_val,
            ))
            snapshot_id = cursor.lastrowid
            print(f"   ✓ 新增快照（snapshot_date={snapshot_date}, id={snapshot_id})")
        
        # 更新持仓明细：先删除旧明细，再重新插入（保持与快照数据一致）
        cursor.execute('DELETE FROM hl_position_details WHERE snapshot_id = %s', (snapshot_id,))

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
        # 无需额外 sleep，API 请求本身已有 ~1s 延迟，不会触发限流
        
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

        # 获取 PnL
        pnl = fetch_portfolio_pnl(address)
        print(f"   📈 今日/周/月/历史 PnL: {pnl['pnl_day']} / {pnl['pnl_week']} / {pnl['pnl_month']} / {pnl['pnl_all_time']}")

        # 判断 snapshot_date
        snapshot_date = resolve_snapshot_date()
        print(f"   📅 snapshot_date: {snapshot_date}")

        # 保存到数据库
        if save_snapshot(address, state, pnl, snapshot_date):
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
