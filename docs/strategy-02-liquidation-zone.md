# 策略二：清算密集区反向

## 📋 概述

| 属性 | 值 |
|------|-----|
| **策略名称** | Liquidation Zone Reversal |
| **预估胜率** | 70-75% |
| **技术难度** | ⭐⭐⭐ |
| **交易频率** | 中（每周 2-5 次）|
| **适合场景** | 高波动市场 |

## 🎯 核心逻辑

当价格接近**大量仓位的清算价位**时：
1. 清算会引发**连锁反应**（价格加速移动）
2. 清算完成后，抛压/买压释放
3. 价格往往**快速反弹**

策略：在清算瀑布**结束后**反向开仓，吃反弹。

## 📊 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| **清算热力图** | Coinglass / Kingfisher | 各价位清算量分布 |
| **实时清算** | Hyperliquid WebSocket | 链上清算事件 |
| **历史清算** | Coinglass API | 回测用 |
| **持仓分布** | Hyperliquid API | 可推算清算价位 |

### Coinglass API 端点

```
# 历史清算数据
GET https://open-api-v4.coinglass.com/api/futures/liquidation/history

# 清算热力图
GET https://open-api-v4.coinglass.com/api/futures/liquidation-heatmap

# 聚合清算量
GET https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated
```

## 🔥 清算密集区识别

### 定义「密集区」

某价格区间内待清算金额超过阈值：

| 币种 | 阈值 | 说明 |
|------|------|------|
| BTC | > $50M | 大量多头/空头聚集 |
| ETH | > $20M | - |
| SOL | > $10M | - |

### 识别方法

```python
def find_liquidation_zones(heatmap_data: dict, threshold: float) -> list:
    """
    从清算热力图中找出密集区
    
    返回: [{'price': 65000, 'amount': 80000000, 'side': 'long'}, ...]
    """
    zones = []
    for price_level in heatmap_data['levels']:
        if price_level['liquidation_amount'] > threshold:
            zones.append({
                'price': price_level['price'],
                'amount': price_level['liquidation_amount'],
                'side': price_level['side']  # 'long' or 'short'
            })
    return sorted(zones, key=lambda x: x['amount'], reverse=True)
```

## 📈 交易规则

### 入场条件（做多）

| 步骤 | 条件 | 说明 |
|------|------|------|
| 1 | 价格**下穿**多头清算密集区 | 触发大量多头清算 |
| 2 | 清算量**飙升** > 平时 5 倍 | 确认清算正在发生 |
| 3 | 清算量**开始下降** > 50% | 抛压释放完毕 |
| 4 | RSI < 30 或 跌幅 > 5% | 超卖确认 |

→ **开多**

### 入场条件（做空）

| 步骤 | 条件 | 说明 |
|------|------|------|
| 1 | 价格**上穿**空头清算密集区 | 触发大量空头清算 |
| 2 | 清算量**飙升** > 平时 5 倍 | 确认逼空正在发生 |
| 3 | 清算量**开始下降** > 50% | 买压释放完毕 |
| 4 | RSI > 70 或 涨幅 > 5% | 超买确认 |

→ **开空**

### 入场时机图示

```
时间线：
─────●─────────●─────────●─────────●─────
    价格接近   清算开始    清算高峰   ← 入场点
    密集区     (观察)     (等待)      (清算量下降后)
```

### 出场规则

| 条件 | 动作 |
|------|------|
| 盈利 **≥ 3%** | 止盈 50% 仓位 |
| 盈利 **≥ 5%** | 全部止盈 |
| 亏损 **≥ 2%** | 止损平仓 |
| 持仓 **> 4小时** | 平仓（反弹窗口已过） |
| 再次出现同向清算潮 | 立即止损 |

## ⚙️ 参数配置

```yaml
# config/strategies/liquidation_zone.yaml

symbols:
  - BTC
  - ETH
  - SOL

liquidation_thresholds:
  BTC: 50000000    # $50M
  ETH: 20000000    # $20M
  SOL: 10000000    # $10M

signals:
  liquidation_spike: 5        # 清算量是平时的5倍
  liquidation_decline: 0.5    # 清算量下降50%时入场
  distance_warning: 0.03      # 距密集区3%预警
  distance_trigger: 0.01      # 距密集区1%准备

risk_management:
  stop_loss: 0.02             # 2% 止损
  take_profit_1: 0.03         # 3% 减半仓
  take_profit_2: 0.05         # 5% 全平
  max_hold_hours: 4           # 最长持仓4小时
  leverage: 1                 # 不加杠杆

rsi:
  oversold: 30                # RSI < 30 超卖
  overbought: 70              # RSI > 70 超买
```

## 💻 实现代码

```python
# src/strategies/liquidation_zone.py

from dataclasses import dataclass
from typing import Optional, List, Literal
from datetime import datetime, timedelta
import numpy as np

@dataclass
class LiquidationZone:
    price: float
    amount: float
    side: Literal['long', 'short']

@dataclass
class Signal:
    direction: Literal['long', 'short', 'neutral']
    strength: float
    reason: str
    zone: Optional[LiquidationZone] = None

class LiquidationZoneStrategy:
    def __init__(self, config: dict):
        self.config = config
        self.liquidation_history = []  # 存储历史清算量
        
    def update_liquidation_data(self, timestamp: datetime, amount: float):
        """更新清算数据"""
        self.liquidation_history.append({
            'timestamp': timestamp,
            'amount': amount
        })
        # 只保留24小时数据
        cutoff = timestamp - timedelta(hours=24)
        self.liquidation_history = [
            x for x in self.liquidation_history 
            if x['timestamp'] > cutoff
        ]
    
    def get_average_liquidation(self) -> float:
        """计算过去24小时平均清算量"""
        if not self.liquidation_history:
            return 0
        amounts = [x['amount'] for x in self.liquidation_history]
        return np.mean(amounts)
    
    def is_liquidation_spike(self, current_amount: float) -> bool:
        """判断是否出现清算飙升"""
        avg = self.get_average_liquidation()
        if avg == 0:
            return False
        return current_amount > avg * self.config['signals']['liquidation_spike']
    
    def is_liquidation_declining(self, recent_amounts: List[float]) -> bool:
        """判断清算量是否在下降"""
        if len(recent_amounts) < 3:
            return False
        peak = max(recent_amounts[:-1])
        current = recent_amounts[-1]
        decline_ratio = (peak - current) / peak
        return decline_ratio > self.config['signals']['liquidation_decline']
    
    def find_nearest_zone(
        self, 
        current_price: float, 
        zones: List[LiquidationZone],
        side: Literal['long', 'short']
    ) -> Optional[LiquidationZone]:
        """找到最近的清算密集区"""
        filtered = [z for z in zones if z.side == side]
        if not filtered:
            return None
        
        # 按距离排序
        filtered.sort(key=lambda z: abs(z.price - current_price))
        return filtered[0]
    
    def calculate_signal(
        self,
        current_price: float,
        zones: List[LiquidationZone],
        recent_liquidations: List[float],
        rsi: float
    ) -> Signal:
        """计算交易信号"""
        
        # 检查是否有清算飙升
        if not recent_liquidations:
            return Signal('neutral', 0, '无清算数据')
        
        current_liq = recent_liquidations[-1]
        is_spike = self.is_liquidation_spike(current_liq)
        is_declining = self.is_liquidation_declining(recent_liquidations)
        
        # 找最近的清算区
        long_zone = self.find_nearest_zone(current_price, zones, 'long')
        short_zone = self.find_nearest_zone(current_price, zones, 'short')
        
        # 做多信号：穿过多头清算区 + 清算飙升后下降 + 超卖
        if long_zone:
            distance = (current_price - long_zone.price) / long_zone.price
            if distance < 0 and is_spike and is_declining and rsi < self.config['rsi']['oversold']:
                return Signal(
                    direction='long',
                    strength=1.0,
                    reason=f'多头清算完成，RSI={rsi:.1f}',
                    zone=long_zone
                )
        
        # 做空信号：穿过空头清算区 + 清算飙升后下降 + 超买
        if short_zone:
            distance = (current_price - short_zone.price) / short_zone.price
            if distance > 0 and is_spike and is_declining and rsi > self.config['rsi']['overbought']:
                return Signal(
                    direction='short',
                    strength=1.0,
                    reason=f'空头清算完成，RSI={rsi:.1f}',
                    zone=short_zone
                )
        
        return Signal('neutral', 0, '无信号')
    
    def should_exit(
        self, 
        pnl_pct: float, 
        hold_hours: float,
        new_liquidation_spike: bool
    ) -> tuple[bool, str]:
        """判断是否应该平仓"""
        
        rm = self.config['risk_management']
        
        # 止损
        if pnl_pct <= -rm['stop_loss']:
            return True, f'止损 {pnl_pct:.2%}'
        
        # 全部止盈
        if pnl_pct >= rm['take_profit_2']:
            return True, f'止盈 {pnl_pct:.2%}'
        
        # 超时
        if hold_hours >= rm['max_hold_hours']:
            return True, f'持仓超时 {hold_hours:.1f}h'
        
        # 再次出现清算潮
        if new_liquidation_spike:
            return True, '再次出现清算潮，止损'
        
        return False, ''
    
    def should_reduce(self, pnl_pct: float) -> bool:
        """判断是否应该减仓"""
        return pnl_pct >= self.config['risk_management']['take_profit_1']
```

## 📊 数据采集

```python
# src/data/liquidation_collector.py

import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List

class LiquidationCollector:
    def __init__(self, coinglass_api_key: str):
        self.api_key = coinglass_api_key
        self.base_url = 'https://open-api-v4.coinglass.com/api'
        
    async def get_liquidation_history(
        self, 
        symbol: str, 
        interval: str = 'h1',
        limit: int = 100
    ) -> List[Dict]:
        """获取历史清算数据"""
        async with aiohttp.ClientSession() as session:
            url = f'{self.base_url}/futures/liquidation/history'
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            headers = {'coinglassSecret': self.api_key}
            
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get('data', [])
    
    async def get_liquidation_heatmap(self, symbol: str) -> Dict:
        """获取清算热力图"""
        async with aiohttp.ClientSession() as session:
            url = f'{self.base_url}/futures/liquidation-heatmap'
            params = {'symbol': symbol}
            headers = {'coinglassSecret': self.api_key}
            
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get('data', {})
    
    async def get_realtime_liquidations(self, symbol: str) -> List[Dict]:
        """获取实时清算数据"""
        async with aiohttp.ClientSession() as session:
            url = f'{self.base_url}/futures/liquidation/aggregated'
            params = {'symbol': symbol, 'interval': '5m'}
            headers = {'coinglassSecret': self.api_key}
            
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get('data', [])
```

## 📊 预期表现

| 指标 | 预估值 |
|------|--------|
| 年交易次数 | 50-100 次 |
| 胜率 | 70-75% |
| 平均盈利 | +3% |
| 平均亏损 | -1.8% |
| 年化收益 | 40-60% |
| 最大回撤 | < 12% |

## ⚠️ 风险点

| 风险 | 应对 |
|------|------|
| **假清算** - 只是试探没真清算 | 等清算量确认后再入场 |
| **连环清算** - 反弹后再跌 | 严格止损 2% |
| **插针** - 瞬间 V 型反转 | 挂限价单预埋 |
| **流动性不足** - 反弹力度弱 | 只做主流币 |

## ✅ 优点

1. **胜率高** - 清算后反弹是高概率事件
2. **入场精准** - 有明确的触发条件
3. **止损清晰** - 再次清算即止损

## ⚠️ 缺点

1. **需要实时数据** - 延迟会错过最佳入场
2. **技术要求高** - 需要处理多个数据源
3. **持仓时间短** - 需要频繁监控

## 📝 下一步

1. 获取 Coinglass 清算历史数据
2. 标注历史「清算潮」事件
3. 回测清算后反弹幅度
4. 确定最优参数
