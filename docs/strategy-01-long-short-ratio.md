# 策略一：多空比极端反向

## 📋 概述

| 属性 | 值 |
|------|-----|
| **策略名称** | Long/Short Ratio Reversal |
| **预估胜率** | 65-70% |
| **技术难度** | ⭐ |
| **交易频率** | 低（每月 2-4 次）|
| **适合场景** | 所有市场环境 |

## 🎯 核心逻辑

散户在极端情绪下往往是错的：
- 当**绝大多数人做多**时，市场往往见顶
- 当**绝大多数人做空**时，市场往往见底

通过监控多空账户比，在极端值时反向操作。

## 📊 数据源

### 主要指标：Long/Short Account Ratio

| 指标 | 说明 | 推荐来源 |
|------|------|----------|
| **Account Ratio** | 做多账户数 / 做空账户数 | Coinglass API |
| **Position Ratio** | 多头持仓量 / 空头持仓量 | Coinglass API |

**推荐使用 Account Ratio**：更能反映散户情绪，Position Ratio 容易被大户扭曲。

### Coinglass API 端点

```
GET https://open-api-v4.coinglass.com/api/futures/global-long-short-account-ratio/history

参数：
- exchange: Hyperliquid / Binance / OKX
- symbol: BTC / ETH / SOL
- interval: h1 / h4 / h12 / h24
- limit: 返回数量
```

## 📈 交易规则

### 入场条件

| 多空比 | 操作 | 仓位 |
|--------|------|------|
| **≥ 4:1**（极端多） | 开空 | 100% |
| **3.5:1 ~ 4:1** | 开空 | 50% |
| **1:3.5 ~ 1:4**（极端空） | 开多 | 50% |
| **≤ 1:4** | 开多 | 100% |

### 出场条件

| 条件 | 动作 |
|------|------|
| 多空比回到 **1.5:1 ~ 1:1.5** | 止盈平仓 |
| 盈利 **≥ 5%** | 止盈平仓 |
| 亏损 **≥ 3%** | 止损平仓 |
| 持仓超过 **48小时** | 强制平仓 |

## ⚙️ 参数配置

```yaml
# config/strategies/long_short_ratio.yaml

symbols:
  - BTC
  - ETH
  - SOL

thresholds:
  extreme_long: 4.0      # 多空比 ≥4 开空
  strong_long: 3.5       # 多空比 ≥3.5 开空（半仓）
  extreme_short: 0.25    # 多空比 ≤0.25 (1:4) 开多
  strong_short: 0.29     # 多空比 ≤0.29 (1:3.5) 开多（半仓）
  neutral_high: 1.5      # 回归区间上限
  neutral_low: 0.67      # 回归区间下限 (1:1.5)

risk_management:
  stop_loss: 0.03        # 3% 止损
  take_profit: 0.05      # 5% 止盈
  max_hold_hours: 48     # 最长持仓时间
  leverage: 1            # 不加杠杆
  max_position: 10000    # 单币最大仓位 $10K
```

## 💻 实现代码

```python
# src/strategies/long_short_ratio.py

from dataclasses import dataclass
from typing import Optional, Literal
import pandas as pd

@dataclass
class Signal:
    direction: Literal['long', 'short', 'neutral']
    strength: float  # 0-1
    reason: str

class LongShortRatioStrategy:
    def __init__(self, config: dict):
        self.config = config
        self.thresholds = config['thresholds']
    
    def calculate_signal(self, ratio: float) -> Signal:
        """根据多空比计算交易信号"""
        
        if ratio >= self.thresholds['extreme_long']:
            return Signal(
                direction='short',
                strength=1.0,
                reason=f'极端多头 ratio={ratio:.2f}'
            )
        
        elif ratio >= self.thresholds['strong_long']:
            return Signal(
                direction='short',
                strength=0.5,
                reason=f'强多头 ratio={ratio:.2f}'
            )
        
        elif ratio <= self.thresholds['extreme_short']:
            return Signal(
                direction='long',
                strength=1.0,
                reason=f'极端空头 ratio={ratio:.2f}'
            )
        
        elif ratio <= self.thresholds['strong_short']:
            return Signal(
                direction='long',
                strength=0.5,
                reason=f'强空头 ratio={ratio:.2f}'
            )
        
        else:
            return Signal(
                direction='neutral',
                strength=0.0,
                reason=f'中性区间 ratio={ratio:.2f}'
            )
    
    def should_exit(self, ratio: float, pnl_pct: float, hold_hours: float) -> tuple[bool, str]:
        """判断是否应该平仓"""
        
        # 止盈
        if pnl_pct >= self.config['risk_management']['take_profit']:
            return True, f'止盈 {pnl_pct:.2%}'
        
        # 止损
        if pnl_pct <= -self.config['risk_management']['stop_loss']:
            return True, f'止损 {pnl_pct:.2%}'
        
        # 超时
        if hold_hours >= self.config['risk_management']['max_hold_hours']:
            return True, f'持仓超时 {hold_hours:.1f}h'
        
        # 多空比回归中性
        if self.thresholds['neutral_low'] <= ratio <= self.thresholds['neutral_high']:
            return True, f'多空比回归中性 ratio={ratio:.2f}'
        
        return False, ''
```

## 📉 回测框架

```python
# src/backtest/long_short_ratio_backtest.py

import pandas as pd
from datetime import datetime
from typing import List
from ..strategies.long_short_ratio import LongShortRatioStrategy, Signal

@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    exit_reason: str

class Backtester:
    def __init__(self, strategy: LongShortRatioStrategy):
        self.strategy = strategy
        self.trades: List[Trade] = []
    
    def run(self, data: pd.DataFrame) -> dict:
        """
        运行回测
        
        data columns:
        - timestamp: 时间戳
        - price: 价格
        - long_short_ratio: 多空比
        """
        position = None
        
        for idx, row in data.iterrows():
            if position is None:
                # 无仓位，检查入场信号
                signal = self.strategy.calculate_signal(row['long_short_ratio'])
                if signal.direction != 'neutral':
                    position = {
                        'entry_time': row['timestamp'],
                        'entry_price': row['price'],
                        'direction': signal.direction,
                    }
            else:
                # 有仓位，检查出场条件
                if position['direction'] == 'long':
                    pnl_pct = (row['price'] - position['entry_price']) / position['entry_price']
                else:
                    pnl_pct = (position['entry_price'] - row['price']) / position['entry_price']
                
                hold_hours = (row['timestamp'] - position['entry_time']).total_seconds() / 3600
                
                should_exit, reason = self.strategy.should_exit(
                    row['long_short_ratio'], pnl_pct, hold_hours
                )
                
                if should_exit:
                    self.trades.append(Trade(
                        entry_time=position['entry_time'],
                        exit_time=row['timestamp'],
                        direction=position['direction'],
                        entry_price=position['entry_price'],
                        exit_price=row['price'],
                        pnl_pct=pnl_pct,
                        exit_reason=reason
                    ))
                    position = None
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self) -> dict:
        if not self.trades:
            return {}
        
        pnls = [t.pnl_pct for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        return {
            'total_trades': len(self.trades),
            'win_rate': len(wins) / len(self.trades),
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'total_return': sum(pnls),
            'max_drawdown': min(pnls),
            'sharpe_ratio': self._calculate_sharpe(pnls),
        }
```

## 📊 预期表现

| 指标 | 预估值 |
|------|--------|
| 年交易次数 | 20-40 次 |
| 胜率 | 65-70% |
| 平均盈利 | +4% |
| 平均亏损 | -2.5% |
| 年化收益 | 25-40% |
| 最大回撤 | < 15% |

⚠️ **注意**：以上为预估值，需要回测验证。

## ✅ 优点

1. **简单易懂** - 逻辑清晰，参数少
2. **数据易获取** - Coinglass 直接提供
3. **维护成本低** - 不需要复杂的数据采集
4. **适用性广** - 所有市场环境都可用

## ⚠️ 缺点

1. **信号较少** - 极端情况不常见
2. **需要耐心** - 可能长时间无信号
3. **存在滞后** - 数据更新有延迟

## 📝 下一步

1. 获取 Coinglass 历史数据
2. 运行 2020-2025 回测
3. 优化阈值参数
4. 实盘小资金测试
