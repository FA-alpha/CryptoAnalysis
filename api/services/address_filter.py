"""
地址筛选服务

根据策略 filter_params 从 hl_coin_fragile_scores + hl_coin_address_features
筛选符合条件的地址+币种对。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Tuple

import pymysql.cursors

from api.models.strategy import FilterParams

logger = logging.getLogger(__name__)


def filter_addresses(
    conn: pymysql.Connection,
    params: FilterParams,
) -> List[Tuple[str, str, float, str]]:
    """
    按筛选参数查询符合条件的地址+币种对。

    筛选来源：
      - hl_coin_fragile_scores（评分 + 等级）
      - hl_coin_address_features（胜率 + 杠杆 + 近7日交易次数）
      - hl_address_list（地址状态必须为 active）

    使用每个地址+币种最新一次评分记录（按 scored_at DESC）。

    Args:
        conn: 数据库连接
        params: 筛选参数

    Returns:
        List of (address, coin, score, level)，按 score 倒序
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # 子查询：每个 address+coin 最新评分
    sql = """
        SELECT
            s.address,
            s.coin,
            s.total_score  AS score,
            s.fragile_level AS level,
            f.win_rate,
            f.avg_leverage_min,
            f.recent_7d_trades
        FROM hl_coin_fragile_scores s
        JOIN (
            SELECT address, coin, MAX(scored_at) AS max_scored_at
            FROM hl_coin_fragile_scores
            GROUP BY address, coin
        ) latest ON s.address = latest.address
               AND s.coin    = latest.coin
               AND s.scored_at = latest.max_scored_at
        JOIN hl_coin_address_features f
            ON s.address = f.address AND s.coin = f.coin
        JOIN (
            SELECT address, coin, MAX(calculated_at) AS max_calc_at
            FROM hl_coin_address_features
            GROUP BY address, coin
        ) lf ON f.address = lf.address
             AND f.coin   = lf.coin
             AND f.calculated_at = lf.max_calc_at
        JOIN hl_address_list al ON s.address = al.address
        WHERE al.status = 'active'
          AND f.is_excluded = 0
          AND s.total_score >= %(score_min)s
          AND s.total_score <= %(score_max)s
    """

    bind: dict = {
        "score_min": params.score_min,
        "score_max": params.score_max,
    }

    # 等级过滤
    if params.level:
        placeholders = ", ".join([f"%(level_{i})s" for i in range(len(params.level))])
        sql += f" AND s.fragile_level IN ({placeholders})"
        for i, lv in enumerate(params.level):
            bind[f"level_{i}"] = lv

    # 币种过滤
    if params.coins:
        placeholders = ", ".join([f"%(coin_{i})s" for i in range(len(params.coins))])
        sql += f" AND s.coin IN ({placeholders})"
        for i, c in enumerate(params.coins):
            bind[f"coin_{i}"] = c

    # 胜率上限
    if params.win_rate_max is not None:
        sql += " AND (f.win_rate IS NULL OR f.win_rate <= %(win_rate_max)s)"
        bind["win_rate_max"] = params.win_rate_max

    # 平均杠杆下限（hl_coin_address_features 没有 avg_leverage，用 hl_address_features）
    # 注：hl_coin_address_features 暂无 avg_leverage 字段，跳过该过滤项并记录警告
    if params.avg_leverage_min is not None:
        logger.warning(
            "avg_leverage_min 筛选暂不支持（hl_coin_address_features 无 avg_leverage 字段），已跳过"
        )

    # 近7日交易次数
    if params.trades_7d_min is not None:
        sql += " AND f.recent_7d_trades >= %(trades_7d_min)s"
        bind["trades_7d_min"] = params.trades_7d_min

    if params.trades_7d_max is not None:
        sql += " AND f.recent_7d_trades <= %(trades_7d_max)s"
        bind["trades_7d_max"] = params.trades_7d_max

    sql += " ORDER BY s.total_score DESC"

    logger.debug("filter_addresses SQL: %s | bind: %s", sql, bind)

    try:
        cur.execute(sql, bind)
        rows = cur.fetchall()
    except Exception as e:
        logger.error("filter_addresses 查询失败: %s", e, exc_info=True)
        raise

    results: List[Tuple[str, str, float, str]] = [
        (r["address"], r["coin"], float(r["score"]), r["level"])
        for r in rows
    ]

    # max_addresses：超出时取 top N（已按 score 倒序，直接截断）
    if params.max_addresses and len(results) > params.max_addresses:
        logger.info(
            "筛选结果 %d 条超过 max_addresses=%d，截断为 top %d",
            len(results),
            params.max_addresses,
            params.max_addresses,
        )
        results = results[: params.max_addresses]

    logger.info("filter_addresses 筛选完成，共 %d 条 address+coin 对", len(results))
    return results
