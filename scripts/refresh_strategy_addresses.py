"""
策略地址池每日刷新脚本

功能：
  每天评分计算完成后（00:30 北京时间），对所有 status='active' 的策略
  重新按 filter_params 筛选地址，增量更新 hl_strategy_addresses。

逻辑：
  1. 读取所有 active 策略
  2. 逐策略重新筛选 address+coin 对
  3. 对比现有有效地址集合：
     - 新增的 → INSERT（或 ON DUPLICATE KEY UPDATE excluded_at=NULL）
     - 不再符合的 → 软删除（excluded_at=now, reason='score_drop'）
  4. 更新 hl_strategies.address_count

运行方式：
  python scripts/refresh_strategy_addresses.py              # 刷新所有活跃策略
  python scripts/refresh_strategy_addresses.py strategy_001 # 只刷新指定策略
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql.cursors

from api.models.strategy import FilterParams
from api.services.address_filter import filter_addresses
from utils.db_utils import get_db

# ── 日志 ────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/refresh_strategy_addresses.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def refresh_strategy(conn: pymysql.Connection, strategy_id: str) -> dict:
    """
    刷新单个策略的地址池。

    Args:
        conn: 数据库连接
        strategy_id: 策略ID

    Returns:
        {added, removed, total} 刷新统计
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)
    now = datetime.now()

    # 读取策略配置
    cur.execute(
        "SELECT filter_params FROM hl_strategies WHERE strategy_id = %s AND status = 'active'",
        (strategy_id,),
    )
    row = cur.fetchone()
    if not row:
        logger.warning("策略 %s 不存在或已停止，跳过", strategy_id)
        return {"added": 0, "removed": 0, "total": 0}

    filter_params = FilterParams(**json.loads(row["filter_params"]))

    # 重新筛选
    new_pairs: List[Tuple[str, str, float, str]] = filter_addresses(conn, filter_params)
    new_set: Set[Tuple[str, str]] = {(addr, coin) for addr, coin, _, _ in new_pairs}

    # 读取现有有效地址集合
    cur.execute(
        """
        SELECT address, coin
        FROM hl_strategy_addresses
        WHERE strategy_id = %s AND excluded_at IS NULL
        """,
        (strategy_id,),
    )
    old_set: Set[Tuple[str, str]] = {(r["address"], r["coin"]) for r in cur.fetchall()}

    to_add = new_set - old_set
    to_remove = old_set - new_set

    # 软删除不再符合条件的地址
    removed = 0
    if to_remove:
        for addr, coin in to_remove:
            cur.execute(
                """
                UPDATE hl_strategy_addresses
                SET excluded_at = %s, exclude_reason = 'score_drop'
                WHERE strategy_id = %s AND address = %s AND coin = %s AND excluded_at IS NULL
                """,
                (now, strategy_id, addr, coin),
            )
        removed = len(to_remove)
        logger.info("策略 %s 移除 %d 条地址关联（score_drop）", strategy_id, removed)

    # 新增地址
    added = 0
    if to_add:
        # 构建 score/level 映射
        score_map = {(addr, coin): (score, level) for addr, coin, score, level in new_pairs}
        values = [
            (strategy_id, addr, coin, score_map[(addr, coin)][0], score_map[(addr, coin)][1], now)
            for addr, coin in to_add
        ]
        cur.executemany(
            """
            INSERT INTO hl_strategy_addresses
              (strategy_id, address, coin, score, level, included_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              score          = VALUES(score),
              level          = VALUES(level),
              included_at    = VALUES(included_at),
              excluded_at    = NULL,
              exclude_reason = NULL
            """,
            values,
        )
        added = len(to_add)
        logger.info("策略 %s 新增 %d 条地址关联", strategy_id, added)

    # 更新 address_count
    total = len(new_set)
    cur.execute(
        "UPDATE hl_strategies SET address_count = %s WHERE strategy_id = %s",
        (total, strategy_id),
    )

    conn.commit()
    logger.info(
        "策略 %s 刷新完成: 新增=%d, 移除=%d, 当前总数=%d",
        strategy_id,
        added,
        removed,
        total,
    )
    return {"added": added, "removed": removed, "total": total}


def refresh_all_active_strategies(target_strategy_id: Optional[str] = None) -> None:
    """
    刷新所有活跃策略（或指定策略）的地址池。

    Args:
        target_strategy_id: 指定策略ID，None 则刷新所有活跃策略
    """
    with get_db() as conn:
        cur = conn.cursor(pymysql.cursors.DictCursor)

        if target_strategy_id:
            strategy_ids = [target_strategy_id]
        else:
            cur.execute(
                "SELECT strategy_id FROM hl_strategies WHERE status = 'active'"
            )
            strategy_ids = [r["strategy_id"] for r in cur.fetchall()]

    if not strategy_ids:
        logger.info("没有活跃策略，退出")
        return

    logger.info("开始刷新 %d 个策略的地址池: %s", len(strategy_ids), strategy_ids)

    total_added = total_removed = 0
    for sid in strategy_ids:
        try:
            with get_db() as conn:
                result = refresh_strategy(conn, sid)
                total_added += result["added"]
                total_removed += result["removed"]
        except Exception as e:
            logger.error("策略 %s 刷新失败: %s", sid, e, exc_info=True)

    logger.info(
        "所有策略刷新完成，合计新增=%d, 移除=%d",
        total_added,
        total_removed,
    )


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    refresh_all_active_strategies(target)
