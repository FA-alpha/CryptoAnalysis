"""
策略相关 Pydantic 模型
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── 筛选参数 ────────────────────────────────────────────────

class FilterParams(BaseModel):
    """地址筛选参数，所有字段均为可选"""

    coins: Optional[List[str]] = Field(
        default=None,
        description="限定币种列表，空或不传=不限",
        examples=[["BTC", "ETH"]],
    )
    score_min: float = Field(
        default=60.0,
        ge=0,
        le=100,
        description="最低评分，默认60",
    )
    score_max: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="最高评分，默认100",
    )
    level: Optional[List[str]] = Field(
        default=None,
        description="地址等级，空或不传=不限，可选值: L1/L2/L3/L4",
        examples=[["L1", "L2"]],
    )
    win_rate_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="胜率上限（0-1），不传=不限",
    )
    avg_leverage_min: Optional[float] = Field(
        default=None,
        ge=0,
        description="最低平均杠杆，不传=不限",
    )
    trades_7d_min: Optional[int] = Field(
        default=None,
        ge=0,
        description="近7天最少交易次数，不传=不限",
    )
    trades_7d_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="近7天最多交易次数，不传=不限",
    )
    max_addresses: Optional[int] = Field(
        default=None,
        ge=1,
        description="最大监控地址+币种对数量，超出时按score倒序取top N，不传=不限",
    )


# ── 请求体 ──────────────────────────────────────────────────

class StrategyStartRequest(BaseModel):
    """启动策略请求"""

    strategy_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="策略ID，唯一标识，stop后可复用同一ID重新start",
        examples=["strategy_001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="策略名称",
        examples=["高杠杆割肉侠反向策略"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="策略描述，可选",
    )
    filter: FilterParams = Field(
        default_factory=FilterParams,
        description="地址筛选参数",
    )


# ── 响应体 ──────────────────────────────────────────────────

class StrategyStartResponse(BaseModel):
    """启动策略响应"""

    strategy_id: str
    status: str
    address_count: int = Field(description="本次筛选到的地址+币种对数量")
    created_at: datetime
    started_at: datetime


class StrategyStopResponse(BaseModel):
    """停止策略响应"""

    strategy_id: str
    status: str
    stopped_at: datetime


class AddressItem(BaseModel):
    """单条地址+币种记录"""

    address: str
    coin: str
    score: Optional[float]
    level: Optional[str]
    included_at: datetime
    excluded_at: Optional[datetime]


class StrategyAddressesResponse(BaseModel):
    """查询策略监控地址响应"""

    strategy_id: str
    status: str
    total: int
    page: int
    page_size: int
    addresses: List[AddressItem]
