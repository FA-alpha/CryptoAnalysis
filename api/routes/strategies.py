"""
策略 API 路由

接口：
  POST /strategies/start           启动策略
  POST /strategies/{id}/stop       停止策略
  GET  /strategies/{id}/addresses  查询策略监控地址
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.models.strategy import (
    StrategyAddressesResponse,
    StrategyStartRequest,
    StrategyStartResponse,
    StrategyStopResponse,
)
from api.services.strategy_service import (
    get_strategy_addresses,
    start_strategy,
    stop_strategy,
)
from utils.db_utils import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post(
    "/start",
    response_model=StrategyStartResponse,
    summary="启动策略",
    description="启动策略并按筛选参数关联监控地址。strategy_id 已存在时复用旧记录并更新参数。",
)
def api_start_strategy(body: StrategyStartRequest) -> StrategyStartResponse:
    """启动策略"""
    logger.info("启动策略请求: strategy_id=%s", body.strategy_id)
    try:
        with get_db() as conn:
            return start_strategy(
                conn=conn,
                strategy_id=body.strategy_id,
                name=body.name,
                description=body.description,
                filter_params=body.filter,
            )
    except Exception as e:
        logger.error("启动策略失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{strategy_id}/stop",
    response_model=StrategyStopResponse,
    summary="停止策略",
)
def api_stop_strategy(strategy_id: str) -> StrategyStopResponse:
    """停止策略"""
    logger.info("停止策略请求: strategy_id=%s", strategy_id)
    try:
        with get_db() as conn:
            return stop_strategy(conn=conn, strategy_id=strategy_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("停止策略失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{strategy_id}/addresses",
    response_model=StrategyAddressesResponse,
    summary="查询策略监控地址",
    description="分页查询策略当前有效的监控地址+币种对（excluded_at IS NULL）。",
)
def api_get_strategy_addresses(
    strategy_id: str,
    coin: Optional[str] = Query(default=None, description="按币种过滤，如 BTC"),
    level: Optional[str] = Query(
        default=None,
        description="按等级过滤，多个用逗号分隔，如 L1,L2",
    ),
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数，最大200"),
) -> StrategyAddressesResponse:
    """查询策略监控地址"""
    levels: Optional[List[str]] = None
    if level:
        levels = [lv.strip() for lv in level.split(",") if lv.strip()]

    try:
        with get_db() as conn:
            return get_strategy_addresses(
                conn=conn,
                strategy_id=strategy_id,
                coin=coin,
                levels=levels,
                page=page,
                page_size=page_size,
            )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("查询策略地址失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
