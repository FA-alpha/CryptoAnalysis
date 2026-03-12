# 策略三：亏损地址反向（韭菜反向）

## 📋 概述

| 属性 | 值 |
|------|-----|
| **策略名称** | Loser Address Reversal |
| **预估胜率** | 60-65% |
| **技术难度** | ⭐⭐⭐⭐ |
| **交易频率** | 中（每周 3-6 次）|
| **适合场景** | 震荡市场 |

## 🎯 核心逻辑

Hyperliquid 链上数据完全透明，可以：
1. 找出**历史亏损**的地址（韭菜）
2. 监控他们的**实时开仓方向**
3. **反向操作**

散户亏损率 90%+，反向操作理论上胜率可观。

## 📊 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| **地址历史 PnL** | Hyperliquid API | `clearinghouseState` |
| **地址实时持仓** | Hyperliquid API | 实时仓位 |
| **地址交易记录** | Hyperliquid API | `userFills` |
| **排行榜** | Hyperliquid Leaderboard | 筛选亏损地址 |

### Hyperliquid API

```python
# 获取地址状态
POST https://api.hyperliquid.xyz/info
{"type": "clearinghouseState", "user": "0x..."}

# 获取交易记录
POST https://api.hyperliquid.xyz/info
{"type": "userFills", "user": "0x..."}
```

## 🎯 韭菜筛选标准

### 核心指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| **历史 PnL** | < -$10K | 确认是亏损用户 |
| **胜率** | < 40% | 交易能力差 |
| **交易次数** | > 50 | 样本足够，排除偶然 |
| **最近活跃** | 7天内有交易 | 确保还在交易 |
| **平均杠杆** | > 5x | 高杠杆韭菜更有参考价值 |
| **单笔金额** | $1K - $50K | 排除机器人和巨鲸 |

### 筛选 SQL 逻辑

```python
韭菜池 = 地址 WHERE
    total_pnl < -10000 AND
    win_rate < 0.4 AND
    trade_count > 50 AND
    last_trade_time > NOW() - 7 days AND
    avg_leverage > 5 AND
    avg_position_size BETWEEN 1000 AND 50000
```

### 推荐池子大小

**100-500 个地址**

太少信号不稳定，太多数据采集压力大。

## 📈 交易规则

### 信号计算

```python
韭菜多头占比 = 做多韭菜数 / 有持仓韭菜总数

IF 韭菜多头占比 > 70%:
    信号 = 开空
ELIF 韭菜多头占比 < 30%:
    信号 = 开多
ELSE:
    信号 = 观望
```

### 入场条件

| 韭菜多头占比 | 操作 | 仓位 |
|--------------|------|------|
| **≥ 80%** | 开空 | 100% |
| **70% ~ 80%** | 开空 | 50% |
| **30% ~ 70%** | 观望 | - |
| **20% ~ 30%** | 开多 | 50% |
| **≤ 20%** | 开多 | 100% |

### 加强信号

| 条件 | 操作 |
|------|------|
| 韭菜平均杠杆 **> 10x** | 仓位 × 1.5 |
| 韭菜开仓量**飙升** > 平时 2 倍 | 仓位 × 1.5 |
| 同时触发清算密集区信号 | 仓位 × 2 |

### 出场规则

| 条件 | 动作 |
|------|------|
| 盈利 **≥ 4%** | 止盈平仓 |
| 亏损 **≥ 3%** | 止损平仓 |
| 韭菜占比回归 **40%-60%** | 平仓 |
| 持仓 **> 24小时** | 平仓 |

## ⚙️ 参数配置

```yaml
# config/strategies/loser_reverse.yaml

# ===== 韭菜池配置 =====
loser_pool:
  min_loss: -10000          # 最少亏 $10K
  max_win_rate: 0.40        # 胜率 <40%
  min_trades: 50            # 至少 50 笔交易
  min_avg_leverage: 5       # 平均杠杆 >5x
  min_position_size: 1000   # 最小仓位 $1K
  max_position_size: 50000  # 最大仓位 $50K
  pool_size: 200            # 韭菜池大小
  refresh_interval: 86400   # 每天刷新一次（秒）

# ===== 信号阈值 =====
signals:
  extreme_long: 0.80        # 韭菜多头占比 ≥80% → 开空（全仓）
  strong_long: 0.70         # 韭菜多头占比 ≥70% → 开空（半仓）
  strong_short: 0.30        # 韭菜多头占比 ≤30% → 开多（半仓）
  extreme_short: 0.20       # 韭菜多头占比 ≤20% → 开多（全仓）
  neutral_low: 0.40         # 回归区间下限
  neutral_high: 0.60        # 回归区间上限

# ===== 风控 =====
risk_management:
  stop_loss: 0.03           # 3%
  take_profit: 0.04         # 4%
  max_hold_hours: 24
  leverage: 1               # 不加杠杆
  max_position: 10000       # 单币最大仓位 $10K

# ===== 币种 =====
symbols:
  - BTC
  - ETH
  - SOL
```

## 💻 实现代码

### 韭菜池管理

```python
# src/strategies/loser_pool.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import aiohttp

@dataclass
class LoserProfile:
    address: str
    total_pnl: float
    win_rate: float
    trade_count: int
    avg_leverage: float
    last_trade_time: datetime
    current_position: Optional[Dict] = None  # {'side': 'long/short', 'size': float}

class LoserPoolManager:
    def __init__(self, config: dict):
        self.config = config
        self.pool: List[LoserProfile] = []
        self.last_refresh: Optional[datetime] = None
        
    async def refresh_pool(self):
        """刷新韭菜池"""
        print("开始刷新韭菜池...")
        
        # 1. 从排行榜获取亏损地址
        losers = await self._fetch_leaderboard_losers()
        
        # 2. 筛选符合条件的地址
        qualified = []
        for address in losers:
            profile = await self._analyze_address(address)
            if self._is_qualified(profile):
                qualified.append(profile)
            
            if len(qualified) >= self.config['loser_pool']['pool_size']:
                break
        
        self.pool = qualified
        self.last_refresh = datetime.utcnow()
        print(f"韭菜池刷新完成，共 {len(self.pool)} 个地址")
    
    async def _fetch_leaderboard_losers(self) -> List[str]:
        """从排行榜获取亏损地址"""
        # TODO: 实现 Hyperliquid 排行榜爬取
        # 按 PnL 升序排列，取亏损最多的
        pass
    
    async def _analyze_address(self, address: str) -> LoserProfile:
        """分析单个地址"""
        async with aiohttp.ClientSession() as session:
            # 获取账户状态
            url = 'https://api.hyperliquid.xyz/info'
            payload = {"type": "clearinghouseState", "user": address}
            
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
            
            # 获取交易记录
            payload = {"type": "userFills", "user": address}
            async with session.post(url, json=payload) as resp:
                fills = await resp.json()
            
            # 计算指标
            return self._calculate_profile(address, data, fills)
    
    def _calculate_profile(self, address: str, state: dict, fills: list) -> LoserProfile:
        """计算地址指标"""
        # 计算胜率
        trades = self._group_fills_to_trades(fills)
        wins = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = wins / len(trades) if trades else 0
        
        # 计算平均杠杆
        leverages = [f.get('leverage', 1) for f in fills]
        avg_leverage = sum(leverages) / len(leverages) if leverages else 1
        
        # 最后交易时间
        last_trade = max(fills, key=lambda x: x['time']) if fills else None
        last_trade_time = datetime.fromtimestamp(last_trade['time']/1000) if last_trade else datetime.min
        
        return LoserProfile(
            address=address,
            total_pnl=state.get('marginSummary', {}).get('totalRawPnl', 0),
            win_rate=win_rate,
            trade_count=len(trades),
            avg_leverage=avg_leverage,
            last_trade_time=last_trade_time
        )
    
    def _is_qualified(self, profile: LoserProfile) -> bool:
        """判断是否符合韭菜标准"""
        cfg = self.config['loser_pool']
        
        return (
            profile.total_pnl < cfg['min_loss'] and
            profile.win_rate < cfg['max_win_rate'] and
            profile.trade_count > cfg['min_trades'] and
            profile.avg_leverage > cfg['min_avg_leverage'] and
            profile.last_trade_time > datetime.utcnow() - timedelta(days=7)
        )
    
    async def update_positions(self):
        """更新所有韭菜的当前持仓"""
        tasks = [self._get_position(loser.address) for loser in self.pool]
        positions = await asyncio.gather(*tasks)
        
        for loser, pos in zip(self.pool, positions):
            loser.current_position = pos
    
    async def _get_position(self, address: str) -> Optional[Dict]:
        """获取地址当前持仓"""
        async with aiohttp.ClientSession() as session:
            url = 'https://api.hyperliquid.xyz/info'
            payload = {"type": "clearinghouseState", "user": address}
            
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
            
            positions = data.get('assetPositions', [])
            if not positions:
                return None
            
            # 简化：只取最大仓位
            largest = max(positions, key=lambda x: abs(float(x['position']['szi'])))
            size = float(largest['position']['szi'])
            
            return {
                'side': 'long' if size > 0 else 'short',
                'size': abs(size),
                'coin': largest['position']['coin']
            }
    
    def _group_fills_to_trades(self, fills: list) -> list:
        """将成交记录分组为交易"""
        # 简化实现
        return fills
```

### 策略主逻辑

```python
# src/strategies/loser_reverse.py

from dataclasses import dataclass
from typing import Literal, Optional
from .loser_pool import LoserPoolManager, LoserProfile

@dataclass
class Signal:
    direction: Literal['long', 'short', 'neutral']
    strength: float
    loser_long_ratio: float
    reason: str

class LoserReverseStrategy:
    def __init__(self, config: dict):
        self.config = config
        self.pool_manager = LoserPoolManager(config)
    
    async def initialize(self):
        """初始化策略"""
        await self.pool_manager.refresh_pool()
    
    def calculate_loser_ratio(self) -> tuple[float, int, int]:
        """计算韭菜多头占比"""
        pool = self.pool_manager.pool
        
        # 只统计有持仓的
        with_position = [l for l in pool if l.current_position]
        if not with_position:
            return 0.5, 0, 0
        
        long_count = sum(1 for l in with_position if l.current_position['side'] == 'long')
        total = len(with_position)
        
        return long_count / total, long_count, total
    
    def calculate_signal(self) -> Signal:
        """计算交易信号"""
        ratio, long_count, total = self.calculate_loser_ratio()
        thresholds = self.config['signals']
        
        if ratio >= thresholds['extreme_long']:
            return Signal(
                direction='short',
                strength=1.0,
                loser_long_ratio=ratio,
                reason=f'韭菜极端做多 {ratio:.1%} ({long_count}/{total})'
            )
        
        elif ratio >= thresholds['strong_long']:
            return Signal(
                direction='short',
                strength=0.5,
                loser_long_ratio=ratio,
                reason=f'韭菜偏多 {ratio:.1%} ({long_count}/{total})'
            )
        
        elif ratio <= thresholds['extreme_short']:
            return Signal(
                direction='long',
                strength=1.0,
                loser_long_ratio=ratio,
                reason=f'韭菜极端做空 {ratio:.1%} ({long_count}/{total})'
            )
        
        elif ratio <= thresholds['strong_short']:
            return Signal(
                direction='long',
                strength=0.5,
                loser_long_ratio=ratio,
                reason=f'韭菜偏空 {ratio:.1%} ({long_count}/{total})'
            )
        
        else:
            return Signal(
                direction='neutral',
                strength=0.0,
                loser_long_ratio=ratio,
                reason=f'韭菜中性 {ratio:.1%}'
            )
    
    def should_exit(
        self, 
        pnl_pct: float, 
        hold_hours: float,
        current_ratio: float
    ) -> tuple[bool, str]:
        """判断是否应该平仓"""
        
        rm = self.config['risk_management']
        thresholds = self.config['signals']
        
        # 止盈
        if pnl_pct >= rm['take_profit']:
            return True, f'止盈 {pnl_pct:.2%}'
        
        # 止损
        if pnl_pct <= -rm['stop_loss']:
            return True, f'止损 {pnl_pct:.2%}'
        
        # 超时
        if hold_hours >= rm['max_hold_hours']:
            return True, f'持仓超时 {hold_hours:.1f}h'
        
        # 韭菜占比回归中性
        if thresholds['neutral_low'] <= current_ratio <= thresholds['neutral_high']:
            return True, f'韭菜占比回归中性 {current_ratio:.1%}'
        
        return False, ''
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────┐
│              韭菜池管理                      │
│  - 每日更新韭菜列表                          │
│  - 剔除不活跃/翻身的地址                     │
│  - 补充新韭菜                               │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              实时监控                        │
│  - 定时拉取韭菜池持仓（每5分钟）             │
│  - 实时计算韭菜多头占比                      │
│  - 触发交易信号                             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              交易执行                        │
│  - 收到信号 → 开仓                          │
│  - 监控止盈止损                             │
│  - 记录交易日志                             │
└─────────────────────────────────────────────┘
```

## 📊 预期表现

| 指标 | 预估值 |
|------|--------|
| 年交易次数 | 60-120 次 |
| 胜率 | 60-65% |
| 平均盈利 | +3.5% |
| 平均亏损 | -2.5% |
| 年化收益 | 30-50% |
| 最大回撤 | < 18% |

## ⚠️ 实现难点

| 难点 | 解决方案 |
|------|----------|
| **初始化韭菜池耗时** | 分批爬取，存入数据库缓存 |
| **监控 200 地址性能** | 批量查询 + 本地缓存 |
| **地址翻身变聪明钱** | 每周重新计算指标，动态剔除 |
| **信号太少** | 可降低阈值到 65%/35% |
| **韭菜不活跃** | 只统计 24h 内有持仓的 |

## ✅ 优点

1. **Hyperliquid 独有** - CEX 无法实现
2. **逻辑直观** - 反着韭菜做
3. **数据真实** - 链上数据不可伪造

## ⚠️ 缺点

1. **技术复杂** - 需要维护韭菜池
2. **数据采集量大** - 需要监控大量地址
3. **韭菜会变** - 池子需要动态更新
4. **韭菜偶尔对** - 胜率不是 100%

## 📝 下一步

1. 实现排行榜爬虫
2. 建立韭菜池数据库
3. 实现实时持仓监控
4. 回测历史表现
