"""
策略业务逻辑服务

负责：
  - 启动策略（写 hl_strategies + hl_strategy_addresses）
  - 停止策略（更新状态 + 软删除地址关联）
  - 查询策略监控地址
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pymysql
import pymysql.cursors

from api.models.strategy import (
    AddressItem,
    FilterParams,
    StrategyAddressesResponse,
    StrategyStartResponse,
    StrategyStopResponse,
)
from api.services.address_filter import filter_addresses

logger = logging.getLogger(__name__)


# ── 启动策略 ────────────────────────────────────────────────

def start_strategy(
    conn: pymysql.Connection,
    strategy_id: str,
    name: str,
    description: Optional[str],
    filter_params: FilterParams,
) -> StrategyStartResponse:
    """
    启动策略。

    逻辑：
      1. 若 strategy_id 已存在且为 active → 先停止旧地址集合，更新参数重新启动
      2. 若 strategy_id 已存在且为 stopped → 复用记录，更新参数重新启动
      3. 若不存在 → 新建

    Args:
        conn: 数据库连接
        strategy_id: 策略唯一ID
        name: 策略名称
        description: 策略描述
        filter_params: 筛选参数

    Returns:
        StrategyStartResponse

    Raises:
        Exception: 数据库操作失败
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)
    now = datetime.now()
    filter_json = filter_params.model_dump(exclude_none=False)

    # ── Step 1: 筛选地址 ──────────────────────────────────
    new_pairs: List[Tuple[str, str, float, str]] = filter_addresses(conn, filter_params)
    address_count = len(new_pairs)

    logger.info(
        "策略 %s 筛选到 %d 条 address+coin 对",
        strategy_id,
        address_count,
    )

    # ── Step 2: upsert hl_strategies ─────────────────────
    cur.execute(
        "SELECT id, status, created_at FROM hl_strategies WHERE strategy_id = %s",
        (strategy_id,),
    )
    existing = cur.fetchone()

    if existing:
        # 复用旧记录：更新参数 + 状态
        cur.execute(
            """
            UPDATE hl_strategies
            SET name = %s,
                description = %s,
                status = 'active',
                filter_params = %s,
                address_count = %s,
                started_at = %s,
                stopped_at = NULL
            WHERE strategy_id = %s
            """,
            (
                name,
                description,
                json.dumps(filter_json, ensure_ascii=False),
                address_count,
                now,
                strategy_id,
            ),
        )
        created_at = existing["created_at"]
        logger.info("策略 %s 复用旧记录，重新启动", strategy_id)
    else:
        # 新建
        cur.execute(
            """
            INSERT INTO hl_strategies
              (strategy_id, name, description, status, filter_params, address_count, started_at)
            VALUES (%s, %s, %s, 'active', %s, %s, %s)
            """,
            (
                strategy_id,
                name,
                description,
                json.dumps(filter_json, ensure_ascii=False),
                address_count,
                now,
            ),
        )
        created_at = now
        logger.info("策略 %s 新建", strategy_id)

    # ── Step 3: 软删除旧地址关联（标记 excluded_at） ──────
    cur.execute(
        """
        UPDATE hl_strategy_addresses
        SET excluded_at = %s, exclude_reason = 'filter_change'
        WHERE strategy_id = %s AND excluded_at IS NULL
        """,
        (now, strategy_id),
    )
    removed = cur.rowcount
    if removed:
        logger.info("策略 %s 旧地址关联软删除 %d 条", strategy_id, removed)

    # ── Step 4: 批量插入新地址关联 ────────────────────────
    if new_pairs:
        values = [
            (strategy_id, addr, coin, score, level, now)
            for addr, coin, score, level in new_pairs
        ]
        cur.executemany(
            """
            INSERT INTO hl_strategy_addresses
              (strategy_id, address, coin, score, level, included_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              score       = VALUES(score),
              level       = VALUES(level),
              included_at = VALUES(included_at),
              excluded_at = NULL,
              exclude_reason = NULL
            """,
            values,
        )
        logger.info("策略 %s 插入/更新 %d 条地址关联", strategy_id, len(values))

    conn.commit()

    return StrategyStartResponse(
        strategy_id=strategy_id,
        status="active",
        address_count=address_count,
        created_at=created_at,
        started_at=now,
    )


# ── 停止策略 ────────────────────────────────────────────────

def stop_strategy(
    conn: pymysql.Connection,
    strategy_id: str,
) -> StrategyStopResponse:
    """
    停止策略。

    Args:
        conn: 数据库连接
        strategy_id: 策略唯一ID

    Returns:
        StrategyStopResponse

    Raises:
        KeyError: 策略不存在
        ValueError: 策略已经是 stopped 状态
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)
    now = datetime.now()

    cur.execute(
        "SELECT status FROM hl_strategies WHERE strategy_id = %s",
        (strategy_id,),
    )
    row = cur.fetchone()

    if not row:
        raise KeyError(f"策略 {strategy_id} 不存在")

    if row["status"] == "stopped":
        raise ValueError(f"策略 {strategy_id} 已经是 stopped 状态")

    # 更新策略状态
    cur.execute(
        """
        UPDATE hl_strategies
        SET status = 'stopped', stopped_at = %s
        WHERE strategy_id = %s
        """,
        (now, strategy_id),
    )

    # 软删除所有地址关联
    cur.execute(
        """
        UPDATE hl_strategy_addresses
        SET excluded_at = %s, exclude_reason = 'strategy_stopped'
        WHERE strategy_id = %s AND excluded_at IS NULL
        """,
        (now, strategy_id),
    )
    removed = cur.rowcount
    conn.commit()

    logger.info("策略 %s 已停止，软删除地址关联 %d 条", strategy_id, removed)

    return StrategyStopResponse(
        strategy_id=strategy_id,
        status="stopped",
        stopped_at=now,
    )


# ── 查询策略监控地址 ─────────────────────────────────────────

def get_strategy_addresses(
    conn: pymysql.Connection,
    strategy_id: str,
    coin: Optional[str] = None,
    levels: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 50,
) -> StrategyAddressesResponse:
    """
    分页查询策略当前监控的地址+币种对（excluded_at IS NULL）。

    Args:
        conn: 数据库连接
        strategy_id: 策略唯一ID
        coin: 按币种过滤（可选）
        levels: 按等级过滤（可选）
        page: 页码，从1开始
        page_size: 每页条数，最大200

    Returns:
        StrategyAddressesResponse

    Raises:
        KeyError: 策略不存在
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # 确认策略存在
    cur.execute(
        "SELECT status FROM hl_strategies WHERE strategy_id = %s",
        (strategy_id,),
    )
    row = cur.fetchone()
    if not row:
        raise KeyError(f"策略 {strategy_id} 不存在")

    strategy_status = row["status"]

    # 构建过滤条件
    where = "WHERE strategy_id = %s AND excluded_at IS NULL"
    bind: List = [strategy_id]

    if coin:
        where += " AND coin = %s"
        bind.append(coin)

    if levels:
        placeholders = ", ".join(["%s"] * len(levels))
        where += f" AND level IN ({placeholders})"
        bind.extend(levels)

    # 总数
    cur.execute(
        f"SELECT COUNT(*) AS cnt FROM hl_strategy_addresses {where}",
        bind,
    )
    total = cur.fetchone()["cnt"]

    # 分页数据
    offset = (page - 1) * page_size
    cur.execute(
        f"""
        SELECT address, coin, score, level, included_at, excluded_at
        FROM hl_strategy_addresses
        {where}
        ORDER BY score DESC, included_at DESC
        LIMIT %s OFFSET %s
        """,
        bind + [page_size, offset],
    )
    rows = cur.fetchall()

    addresses = [
        AddressItem(
            address=r["address"],
            coin=r["coin"],
            score=float(r["score"]) if r["score"] is not None else None,
            level=r["level"],
            included_at=r["included_at"],
            excluded_at=r["excluded_at"],
        )
        for r in rows
    ]

    return StrategyAddressesResponse(
        strategy_id=strategy_id,
        status=strategy_status,
        total=total,
        page=page,
        page_size=page_size,
        addresses=addresses,
    )
