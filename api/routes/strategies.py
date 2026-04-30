"""
策略 API 路由

接口：
  POST /strategies/start   启动策略
  POST /strategies/stop    停止策略
  POST /strategies/addresses 查询策略监控地址
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.models.strategy import (
    FilterParams,
    StrategyAddressesResponse,
    StrategyAddressesRequest,
    StrategyStartRequest,
    StrategyStartResponse,
    StrategyStopResponse,
    StrategyStopRequest,
)
from api.services.strategy_service import (
    get_strategy_addresses,
    start_strategy,
    stop_strategy,
)
from utils.db_utils import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _expand_fragile_level(level: Optional[str]) -> Optional[List[str]]:
    """将 fragile_level 展开为“当前及以下”等级列表。"""
    if not level:
        return None
    level_upper = level.strip().upper()
    rank = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    if level_upper not in rank:
        raise HTTPException(status_code=422, detail=f"fragile_level 无效: {level}")
    target_rank = rank[level_upper]
    return [lv for lv, rv in rank.items() if rv <= target_rank]


def _build_effective_filter(body: StrategyStartRequest) -> FilterParams:
    """
    兼容两种传参方式：
    1) 历史 filter 参数
    2) 顶层简化参数（fragile_level / max_addresses / tracked_coins）
    顶层参数优先。
    """
    raw = body.filter.model_dump()
    levels = _expand_fragile_level(body.fragile_level)
    if levels is not None:
        raw["level"] = levels
    if body.max_addresses is not None:
        raw["max_addresses"] = body.max_addresses
    # tracked_coins: [{COIN: "COIN/USDT:USDT"}, ...] => coins=[COIN, ...]
    if body.tracked_coins:
        try:
            coin_symbol_map = {}
            for item in body.tracked_coins:
                if not isinstance(item, dict) or len(item) != 1:
                    raise ValueError("tracked_coins 每一项必须是单键 dict")
                (k, v), = item.items()
                coin_symbol_map[str(k)] = str(v)
            raw["coins"] = list(coin_symbol_map.keys())
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"tracked_coins 格式错误: {e}")
    return FilterParams(**raw)


@router.post(
    "/start",
    response_model=StrategyStartResponse,
    summary="启动策略",
    description="启动策略并按筛选参数关联监控地址。strategy_id 已存在时复用旧记录并更新参数。",
)
async def api_start_strategy(request: Request) -> StrategyStartResponse:
    """启动策略"""
    try:
        raw_body = await request.json()
    except Exception:
        raw_body = None
    logger.info("启动策略原始请求体: %s", raw_body)

    try:
        body = StrategyStartRequest.model_validate(raw_body or {})
    except ValidationError as e:
        logger.warning("启动策略参数校验失败: errors=%s raw_body=%s", e.errors(), raw_body)
        raise HTTPException(status_code=422, detail=e.errors())

    logger.info("启动策略请求: strategy_id=%s", body.strategy_id)
    try:
        logger.info("启动策略参数: tracked_coins=%s fragile_level=%s single_addr_limit_pct=%s max_addresses=%s",
                    body.tracked_coins, body.fragile_level, body.single_addr_limit_pct, body.max_addresses)
        effective_filter = _build_effective_filter(body)
        extra_params = {}
        if body.fragile_level is not None:
            extra_params["fragile_level"] = body.fragile_level
        if body.single_addr_limit_pct is not None:
            extra_params["single_addr_limit_pct"] = body.single_addr_limit_pct
        if body.max_addresses is not None:
            extra_params["max_addresses"] = body.max_addresses
        if body.tracked_coins is not None:
            # 存储为 dict，便于 monitor_strategy 直接按 coin 查 symbol
            coin_symbol_map = {}
            for item in body.tracked_coins or []:
                (k, v), = item.items()
                coin_symbol_map[str(k)] = str(v)
            logger.info("启动策略解析 tracked_coins: coins=%s coin_symbol_map=%s", list(coin_symbol_map.keys()), coin_symbol_map)
            extra_params["tracked_coins"] = coin_symbol_map
        with get_db() as conn:
            return start_strategy(
                conn=conn,
                strategy_id=body.strategy_id,
                name=body.name,
                description=body.description,
                filter_params=effective_filter,
                extra_params=extra_params or None,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("启动策略失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/stop",
    response_model=StrategyStopResponse,
    summary="停止策略",
)
def api_stop_strategy(body: StrategyStopRequest) -> StrategyStopResponse:
    """停止策略"""
    logger.info("停止策略请求: strategy_id=%s", body.strategy_id)
    try:
        with get_db() as conn:
            return stop_strategy(conn=conn, strategy_id=str(body.strategy_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("停止策略失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/addresses",
    response_model=StrategyAddressesResponse,
    summary="查询策略监控地址",
    description="查询策略当前有效的监控地址+币种对（excluded_at IS NULL）。",
)
def api_post_strategy_addresses(body: StrategyAddressesRequest) -> StrategyAddressesResponse:
    """查询策略监控地址（POST body 参数，无 page/page_size 入参）"""
    levels: Optional[List[str]] = None
    if body.level:
        levels = [lv.strip() for lv in body.level.split(",") if lv.strip()]

    # 保持服务端返回格式：固定第一页
    page = 1
    page_size = 50

    try:
        with get_db() as conn:
            return get_strategy_addresses(
                conn=conn,
                strategy_id=str(body.strategy_id),
                coin=body.coin,
                levels=levels,
                page=page,
                page_size=page_size,
            )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("查询策略地址失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
