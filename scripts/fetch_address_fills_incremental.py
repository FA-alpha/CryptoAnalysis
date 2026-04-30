"""
获取地址交易历史 (fills) - 统一版
- 无历史数据：全量获取最近 2000 条（userFills）
- 有历史数据：增量获取（userFillsByTime，从上次最新时间开始）
- 支持单地址模式（传参）和批量模式（处理所有 active 地址）
使用 aggregateByTime=True，UPSERT 保存（按 tid 去重）
"""
import sys
import os
import time
import httpx
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from utils.db_utils import get_onchain_connection
from utils.db_utils import get_connection
# Hyperliquid API
HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz/info"


def get_last_fill_time(address: str) -> Optional[int]:
    """
    获取数据库中该地址最新的 fill 时间戳

    Returns:
        最新时间戳（毫秒），如果没有数据则返回 None
    """
    conn = get_onchain_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT MAX(time) FROM hl_fills
            WHERE address = %s
        ''', (address,))

        result = cursor.fetchone()
        last_time = result[0] if result else None

        if last_time:
            dt = datetime.fromtimestamp(last_time / 1000)
            print(f"📅 数据库中最新记录时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"📅 数据库中无该地址记录，将全量获取最近 2000 条")

        return last_time

    finally:
        cursor.close()
        conn.close()


# userFillsByTime 单次返回上限（raw fills），超过此数则需要分页
FILLS_PAGE_LIMIT = 2000


def fetch_fills_by_time_paged(address: str, start_time: int, end_time: Optional[int] = None) -> List[Dict]:
    """
    用 userFillsByTime 分页拉取，自动处理 2000 条上限。
    使用 aggregateByTime=True 减少条数，但仍以返回条数是否达到上限作为分页依据。

    Args:
        address: 钱包地址
        start_time: 起始时间戳（毫秒，包含）
        end_time: 结束时间戳（毫秒，可选）

    Returns:
        所有 fills 列表（已去重、按时间升序）
    """
    all_fills: List[Dict] = []
    seen_tids: set = set()
    current_start = start_time
    page = 0

    while True:
        page += 1
        payload: Dict = {
            'type': 'userFillsByTime',
            'user': address,
            'startTime': current_start,
            'aggregateByTime': True,
        }
        if end_time is not None:
            payload['endTime'] = end_time

        try:
            resp = httpx.post(
                HYPERLIQUID_API_URL,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30.0
            )
            resp.raise_for_status()
            batch: List[Dict] = resp.json()
        except Exception as e:
            print(f"❌ 第 {page} 页请求失败: {e}")
            break

        if not batch:
            break

        # 去重并收集
        new_count = 0
        for fill in batch:
            tid = fill.get('tid')
            if tid not in seen_tids:
                seen_tids.add(tid)
                all_fills.append(fill)
                new_count += 1

        print(f"   第 {page} 页: 返回 {len(batch)} 条，新增 {new_count} 条（累计 {len(all_fills)} 条）")

        # 返回条数未达上限 → 已拉完
        if len(batch) < FILLS_PAGE_LIMIT:
            break

        # 达到上限 → 以最后一条时间作为下一页起点（+1ms 避免重复）
        batch.sort(key=lambda x: x.get('time', 0))
        last_time = batch[-1].get('time', 0)
        if last_time <= current_start:
            # 防止死循环
            print(f"⚠️ 分页时间未推进（last_time={last_time}），停止分页")
            break
        current_start = last_time + 1
        time.sleep(0.5)  # 避免限流

    return all_fills


def fetch_fills_incremental(address: str, start_time: Optional[int] = None) -> List[Dict]:
    """
    获取 fills（聚合模式，支持分页）

    Args:
        address: 钱包地址
        start_time: 起始时间戳（毫秒）；None 则全量从头拉取所有历史
    """
    print(f"\n📥 正在获取地址交易数据（aggregateByTime=True）...")
    print(f"   地址: {address}")

    try:
        if start_time:
            # 增量模式：从上次最新时间开始，分页拉取
            print(f"   模式: 增量（起始时间: {datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}）")
            fills = fetch_fills_by_time_paged(address, start_time=start_time)
        else:
            # 全量模式：从 2020-01-01 开始分页拉取所有历史
            # 注意：不能用 userFills，它只返回最近 2000 条（raw），历史数据会被截断
            full_start = int(datetime(2020, 1, 1).timestamp() * 1000)
            print(f"   模式: 全量（从 2020-01-01 开始分页拉取所有历史）")
            fills = fetch_fills_by_time_paged(address, start_time=full_start)

        print(f"✅ 共获取 {len(fills)} 条 fills")

        if fills:
            fills.sort(key=lambda x: x.get('time', 0))
            print(f"\n=== 数据概览 ===")
            dt_first = datetime.fromtimestamp(fills[0].get('time', 0) / 1000)
            dt_last = datetime.fromtimestamp(fills[-1].get('time', 0) / 1000)
            print(f"   最早: {dt_first.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   最新: {dt_last.strftime('%Y-%m-%d %H:%M:%S')}")

        return fills

    except Exception as e:
        print(f"❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def upsert_fills_batch(address: str, fills: List[Dict]) -> Dict[str, int]:
    """
    批量保存 fills（UPSERT 模式）
    - 新记录：直接插入
    - 已存在记录（按 tid 判断）：更新字段（聚合后 sz/fee/closedPnl 等可能变化）

    Returns:
        {'inserted': int, 'updated': int}
    """
    if not fills:
        print("\n⚠️ 没有新数据需要保存")
        return {'inserted': 0, 'updated': 0}

    print(f"\n💾 正在批量保存到数据库（UPSERT 模式）...")
    print(f"   总数: {len(fills)} 条")

    conn = get_onchain_connection()
    cursor = conn.cursor()

    try:
        values = []
        for fill in fills:
            hash_val = fill.get('hash')
            if hash_val == '0x0000000000000000000000000000000000000000000000000000000000000000':
                hash_val = None

            values.append((
                address,
                fill.get('coin', ''),
                Decimal(str(fill.get('sz', 0))),
                Decimal(str(fill.get('px', 0))),
                fill.get('dir', ''),
                Decimal(str(fill.get('closedPnl', 0))),
                Decimal(str(fill.get('fee', 0))),
                fill.get('feeToken', 'USDC'),
                fill.get('time', 0),
                hash_val,
                fill.get('tid'),
                fill.get('oid'),
                fill.get('twapId'),
                fill.get('side', ''),
                Decimal(str(fill.get('startPosition', 0))),
                fill.get('crossed', True),
            ))

        sql = '''
            INSERT INTO hl_fills
            (address, coin, sz, px, dir, closed_pnl, fee, fee_token, time, hash, tid, oid, twap_id, side, start_position, crossed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                sz = VALUES(sz),
                px = VALUES(px),
                closed_pnl = VALUES(closed_pnl),
                fee = VALUES(fee),
                hash = VALUES(hash),
                start_position = VALUES(start_position),
                crossed = VALUES(crossed)
        '''

        batch_size = 500
        total_affected = 0

        for i in range(0, len(values), batch_size):
            batch = values[i:i+batch_size]
            cursor.executemany(sql, batch)
            conn.commit()
            total_affected += cursor.rowcount
            print(f"   进度: {min(i+batch_size, len(values))}/{len(values)}")

        print(f"\n✅ 保存完成! 总影响行数: {total_affected}（1=新插入, 2=更新）")
        return {'inserted': total_affected, 'updated': 0}

    except Exception as e:
        conn.rollback()
        print(f"❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return {'inserted': 0, 'updated': 0}

    finally:
        cursor.close()
        conn.close()


def update_address_last_updated(address: str) -> None:
    """更新地址的最后更新时间（北京时间）"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            UPDATE hl_address_list
            SET last_updated_at = NOW()
            WHERE address = %s
        ''', (address,))
        conn.commit()

        cursor.execute('SELECT last_updated_at FROM hl_address_list WHERE address = %s', (address,))
        result = cursor.fetchone()
        if result:
            print(f"✅ 已更新地址最后更新时间: {result[0]}")

    except Exception as e:
        print(f"⚠️ 更新地址时间失败: {e}")
    finally:
        cursor.close()
        conn.close()


def get_all_active_addresses() -> List[str]:
    """
    从 hl_address_list 获取所有 active 状态的地址

    Returns:
        地址列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT address FROM hl_address_list
            WHERE status = 'active'
            ORDER BY created_at ASC
        ''')
        rows = cursor.fetchall()
        addresses = [row[0] for row in rows]
        print(f"📋 共找到 {len(addresses)} 个活跃地址")
        return addresses

    except Exception as e:
        print(f"❌ 获取地址列表失败: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        cursor.close()
        conn.close()


def process_single_address(address: str) -> bool:
    """
    处理单个地址：自动判断全量 or 增量

    Args:
        address: 钱包地址

    Returns:
        是否处理成功
    """
    try:
        last_time = get_last_fill_time(address)
        fills = fetch_fills_incremental(address, start_time=last_time)

        if not fills:
            print("✅ 无新数据，跳过")
            return True

        result = upsert_fills_batch(address, fills)

        if result['inserted'] > 0:
            update_address_last_updated(address)

        return True

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_all_addresses(delay_seconds: float = 1.0) -> None:
    """
    批量处理所有 active 地址：
    - 无历史数据 → 全量获取最近 2000 条
    - 有历史数据 → 增量获取

    Args:
        delay_seconds: 地址之间的请求间隔（秒），避免 API 限流
    """
    addresses = get_all_active_addresses()

    if not addresses:
        print("⚠️ 未找到任何活跃地址")
        return

    total = len(addresses)
    success_count = 0
    failed_count = 0

    for idx, address in enumerate(addresses, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{total}] 处理地址: {address}")
        print('='*70)

        ok = process_single_address(address)
        if ok:
            success_count += 1
        else:
            failed_count += 1

        if idx < total:
            time.sleep(delay_seconds)

    print(f"\n{'='*70}")
    print(f"🎯 批量处理完成: 成功 {success_count} / 失败 {failed_count} / 总计 {total}")
    print('='*70)


def main() -> None:
    """
    主函数

    用法：
        python fetch_address_fills_incremental.py              # 批量处理所有 active 地址
        python fetch_address_fills_incremental.py <address>   # 处理单个地址
    """
    if len(sys.argv) > 1:
        address = sys.argv[1]
        print("=" * 70)
        print("Hyperliquid 地址交易数据获取（单地址模式）")
        print("=" * 70)
        process_single_address(address)
    else:
        print("=" * 70)
        print("Hyperliquid 地址交易数据获取（批量模式）")
        print("=" * 70)
        process_all_addresses(delay_seconds=1.0)


if __name__ == '__main__':
    main()
