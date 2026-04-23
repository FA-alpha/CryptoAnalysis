"""
脆弱地址池管理脚本 - 每日评分计算后运行

功能：
  1. 扫描满足入池条件的地址+币种组合，写入 hl_fragile_pool
  2. 检查已在池中的记录，不满足条件时标记出池
  3. 所有变更写入 hl_pool_change_logs

入池条件（同时满足）：
  - hl_fragile_scores 最新评分 L1 或 L2
  - hl_position_snapshots 最新快照 pnl_all_time < 0（总亏损）
  - hl_position_snapshots 最新快照 pnl_month < 0（近30天亏损）
  - hl_coin_address_features 最新 recent_7d_trades > 10（单币近7天活跃）

出池条件（满足任一）：
  - 整体评分降至 L3/L4
  - 该币种 recent_7d_trades <= 10
  - hl_address_list.status = 'excluded'

运行方式：
  python scripts/update_fragile_pool.py
"""

import sys
import os
import logging
from datetime import date
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================
ELIGIBLE_LEVELS = ('L1', 'L2')
MIN_RECENT_7D_TRADES = 10


# ============================================================
# 数据查询
# ============================================================

def get_eligible_candidates() -> List[Tuple]:
    """
    查询满足入池条件的地址+币种组合。

    Returns:
        List of (address, coin, label, fragile_level, total_score,
                 pnl_all_time, pnl_month, recent_7d_trades)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT
                al.address,
                cf.coin,
                al.label,
                fs.fragile_level,
                fs.total_score,
                ps.pnl_all_time,
                ps.pnl_month,
                cf.recent_7d_trades
            FROM hl_address_list al

            -- 最新整体评分 L1/L2
            INNER JOIN (
                SELECT address, fragile_level, total_score,
                       ROW_NUMBER() OVER (PARTITION BY address ORDER BY scored_at DESC) AS rn
                FROM hl_fragile_scores
            ) fs ON fs.address = al.address AND fs.rn = 1
                 AND fs.fragile_level IN ('L1', 'L2')

            -- 最新持仓快照：总亏损 & 近30天亏损
            INNER JOIN (
                SELECT address, pnl_all_time, pnl_month,
                       ROW_NUMBER() OVER (PARTITION BY address ORDER BY snapshot_time DESC) AS rn
                FROM hl_position_snapshots
            ) ps ON ps.address = al.address AND ps.rn = 1
                 AND ps.pnl_all_time < 0
                 AND ps.pnl_month < 0

            -- 单币近7天活跃 > 10
            INNER JOIN (
                SELECT address, coin, recent_7d_trades,
                       ROW_NUMBER() OVER (PARTITION BY address, coin ORDER BY calculated_at DESC) AS rn
                FROM hl_coin_address_features
            ) cf ON cf.address = al.address AND cf.rn = 1
                 AND cf.recent_7d_trades > %s

            WHERE al.status = 'active'
        ''', (MIN_RECENT_7D_TRADES,))

        rows = cursor.fetchall()
        logger.info(f"满足入池条件的地址+币种组合: {len(rows)} 条")
        return rows

    finally:
        cursor.close()
        conn.close()


def get_active_pool_entries() -> List[Tuple]:
    """
    查询当前池中所有 monitor_status='active' 的记录。

    Returns:
        List of (id, address, coin)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, address, coin
            FROM hl_fragile_pool
            WHERE monitor_status = 'active' AND exit_date IS NULL
        ''')
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_exit_check_data(address: str, coin: str) -> Optional[Tuple]:
    """
    获取出池检查所需数据：评分等级、近7天交易数、地址状态。

    Returns:
        (fragile_level, recent_7d_trades, address_status) or None
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT
                fs.fragile_level,
                COALESCE(cf.recent_7d_trades, 0) AS recent_7d_trades,
                al.status
            FROM hl_address_list al
            LEFT JOIN (
                SELECT address, fragile_level,
                       ROW_NUMBER() OVER (PARTITION BY address ORDER BY scored_at DESC) AS rn
                FROM hl_fragile_scores
            ) fs ON fs.address = al.address AND fs.rn = 1
            LEFT JOIN (
                SELECT address, coin, recent_7d_trades,
                       ROW_NUMBER() OVER (PARTITION BY address, coin ORDER BY calculated_at DESC) AS rn
                FROM hl_coin_address_features
                WHERE coin = %s
            ) cf ON cf.address = al.address AND cf.rn = 1
            WHERE al.address = %s
        ''', (coin, address))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


# ============================================================
# 池子写入
# ============================================================

def enter_pool(address: str, coin: str, label: Optional[str],
               fragile_level: str, total_score: float,
               pnl_all_time: float, pnl_month: float,
               recent_7d_trades: int) -> bool:
    """
    将地址+币种写入池子，已存在则跳过（不重复入池）。

    Returns:
        True=新入池, False=已在池中跳过
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 检查是否已在池中（active）
        cursor.execute('''
            SELECT id FROM hl_fragile_pool
            WHERE address = %s AND coin = %s AND monitor_status = 'active' AND exit_date IS NULL
        ''', (address, coin))
        if cursor.fetchone():
            return False

        today = date.today()
        cursor.execute('''
            INSERT INTO hl_fragile_pool
              (address, coin, label, fragile_level, total_score, monitor_status,
               entry_date, entry_score)
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
            ON DUPLICATE KEY UPDATE
              fragile_level = VALUES(fragile_level),
              total_score   = VALUES(total_score),
              monitor_status = 'active',
              exit_date      = NULL,
              exit_reason    = NULL,
              entry_date     = VALUES(entry_date),
              entry_score    = VALUES(entry_score),
              updated_at     = NOW()
        ''', (address, coin, label, fragile_level, total_score, today, total_score))

        # 写入日志
        cursor.execute('''
            INSERT INTO hl_pool_change_logs
              (address, coin, action, fragile_level, total_score,
               pnl_all_time, pnl_month, recent_7d_trades, reason)
            VALUES (%s, %s, 'enter', %s, %s, %s, %s, %s, %s)
        ''', (address, coin, fragile_level, total_score,
              pnl_all_time, pnl_month, recent_7d_trades,
              f'评分{fragile_level}/{total_score:.1f}，近7d交易{recent_7d_trades}笔，月亏{pnl_month:.2f}'))

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"入池失败 {address}/{coin}: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def exit_pool(pool_id: int, address: str, coin: str,
              reason: str, fragile_level: Optional[str],
              total_score: Optional[float], recent_7d_trades: int) -> None:
    """
    将池中记录标记为出池。
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today = date.today()
        cursor.execute('''
            UPDATE hl_fragile_pool
            SET monitor_status = 'stopped',
                exit_date      = %s,
                exit_reason    = %s,
                updated_at     = NOW()
            WHERE id = %s
        ''', (today, reason, pool_id))

        cursor.execute('''
            INSERT INTO hl_pool_change_logs
              (address, coin, action, fragile_level, total_score,
               recent_7d_trades, reason)
            VALUES (%s, %s, 'exit', %s, %s, %s, %s)
        ''', (address, coin, fragile_level, total_score, recent_7d_trades, reason))

        conn.commit()
        logger.info(f"  ⬇️  出池: {address} / {coin} | {reason}")

    except Exception as e:
        conn.rollback()
        logger.error(f"出池失败 {address}/{coin}: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()


# ============================================================
# 主流程
# ============================================================

def main() -> None:
    logger.info("=" * 60)
    logger.info("脆弱地址池更新开始")
    logger.info("=" * 60)

    # --- Step 1: 处理入池 ---
    logger.info("\n📥 Step 1: 扫描入池候选...")
    candidates = get_eligible_candidates()
    entered = skipped = 0

    for address, coin, label, fragile_level, total_score, pnl_all_time, pnl_month, recent_7d in candidates:
        is_new = enter_pool(
            address=address,
            coin=coin,
            label=label,
            fragile_level=fragile_level,
            total_score=float(total_score or 0),
            pnl_all_time=float(pnl_all_time or 0),
            pnl_month=float(pnl_month or 0),
            recent_7d_trades=int(recent_7d or 0),
        )
        if is_new:
            entered += 1
            logger.info(f"  ⬆️  入池: {address} / {coin} | {fragile_level} {total_score:.1f}分 | 近7d={recent_7d}笔")
        else:
            skipped += 1

    logger.info(f"\n✅ 入池完成: 新增 {entered} 条，已在池中跳过 {skipped} 条")

    # --- Step 2: 处理出池 ---
    logger.info("\n📤 Step 2: 检查出池条件...")
    active_entries = get_active_pool_entries()
    exited = 0

    for pool_id, address, coin in active_entries:
        data = get_exit_check_data(address, coin)
        if data is None:
            exit_pool(pool_id, address, coin,
                      reason='地址已从 address_list 中移除',
                      fragile_level=None, total_score=None, recent_7d_trades=0)
            exited += 1
            continue

        fragile_level, recent_7d, addr_status = data
        recent_7d = int(recent_7d or 0)
        total_score = None  # 出池时仅记录等级

        if addr_status == 'excluded':
            exit_pool(pool_id, address, coin,
                      reason='地址已被 excluded',
                      fragile_level=fragile_level, total_score=total_score,
                      recent_7d_trades=recent_7d)
            exited += 1
        elif fragile_level not in ELIGIBLE_LEVELS:
            exit_pool(pool_id, address, coin,
                      reason=f'评分降至 {fragile_level}，不满足 L1/L2 要求',
                      fragile_level=fragile_level, total_score=total_score,
                      recent_7d_trades=recent_7d)
            exited += 1
        elif recent_7d <= MIN_RECENT_7D_TRADES:
            exit_pool(pool_id, address, coin,
                      reason=f'近7天交易 {recent_7d} 笔，低于阈值 {MIN_RECENT_7D_TRADES}',
                      fragile_level=fragile_level, total_score=total_score,
                      recent_7d_trades=recent_7d)
            exited += 1

    logger.info(f"\n✅ 出池完成: {exited} 条")

    # --- Step 3: 汇总 ---
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM hl_fragile_pool WHERE monitor_status = 'active' AND exit_date IS NULL")
        active_count = cursor.fetchone()[0]
        cursor.execute("SELECT fragile_level, COUNT(*) FROM hl_fragile_pool WHERE monitor_status = 'active' AND exit_date IS NULL GROUP BY fragile_level")
        level_dist = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    logger.info("\n" + "=" * 60)
    logger.info(f"📊 当前池子状态: {active_count} 个活跃监控组合")
    for level, cnt in level_dist:
        logger.info(f"   {level}: {cnt} 条")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
