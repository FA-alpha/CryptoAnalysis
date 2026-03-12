# 策略四：聪明钱跟单

## 📋 概述

| 属性 | 值 |
|------|-----|
| **策略名称** | Smart Money Following |
| **预估胜率** | 60-70% |
| **技术难度** | ⭐⭐⭐⭐ |
| **交易频率** | 中（每周 3-6 次）|
| **适合场景** | 趋势市场 |

## 🎯 核心逻辑

找出 Hyperliquid 上**持续盈利**的地址（聪明钱），跟随他们的方向开仓。

与「韭菜反向」相反：
- 韭菜反向 = 找亏钱的，反着做
- 聪明钱跟单 = 找赚钱的，跟着做

## 📊 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| **排行榜** | Hyperliquid Leaderboard | 按 PnL 排序 |
| **地址 PnL** | Hyperliquid API | `clearinghouseState` |
| **地址持仓** | Hyperliquid API | 实时仓位 |
| **历史成交** | Hyperliquid API | `userFills` |

### Hyperliquid API

```python
# 获取地址状态
POST https://api.hyperliquid.xyz/info
{"type": "clearinghouseState", "user": "0x..."}

# 获取交易记录
POST https://api.hyperliquid.xyz/info
{"type": "userFills", "user": "0x..."}
```

## 🎯 聪明钱筛选标准

### 核心指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| **历史 PnL** | > +$100K | 确认是盈利用户 |
| **胜率** | > 55% | 不需要太高，稳定就行 |
| **交易次数** | > 100 | 样本足够 |
| **最大回撤** | < 30% | 风控能力强 |
| **活跃度** | 7天内有交易 | 还在玩 |
| **近期盈利** | 近30天 PnL > 0 | 不是靠一把梭哈 |
| **持仓时间** | 平均 > 1小时 | 排除高频机器人 |

### 筛选逻辑

```python
聪明钱池 = 地址 WHERE
    total_pnl > 100000 AND
    win_rate > 0.55 AND
    trade_count > 100 AND
    max_drawdown < 0.30 AND
    last_trade_time > NOW() - 7 days AND
    pnl_last_30d > 0 AND
    avg_hold_time > 1 hour
```

## 📊 聪明钱分级

不是所有盈利地址都值得跟：

| 等级 | 条件 | 跟单权重 |
|------|------|----------|
| **S 级** | PnL > $1M，胜率 > 60%，回撤 < 20% | 100% |
| **A 级** | PnL > $500K，胜率 > 55%，回撤 < 25% | 70% |
| **B 级** | PnL > $100K，胜率 > 55%，回撤 < 30% | 40% |

### 推荐池子规模

| 等级 | 数量 |
|------|------|
| S 级 | 10-20 个 |
| A 级 | 30-50 个 |
| B 级 | 50-100 个 |

## 📈 交易规则

### 信号计算方式

#### 方式一：单地址跟单

| 条件 | 操作 |
|------|------|
| S 级地址开仓 | 立即跟单 |
| A 级地址开仓 | 等确认后跟单 |
| B 级地址开仓 | 不单独跟 |

#### 方式二：共识跟单（推荐）

```python
# 简单版
聪明钱多头占比 = 做多聪明钱数 / 有持仓聪明钱总数

# 加权版本（推荐）
加权多头占比 = Σ(做多地址权重) / Σ(所有持仓地址权重)

# S级权重=100, A级=70, B级=40

IF 加权多头占比 > 65%:
    信号 = 开多
ELIF 加权多头占比 < 35%:
    信号 = 开空
ELSE:
    信号 = 观望
```

#### 方式三：仓位变化跟单

| 信号 | 条件 |
|------|------|
| **强烈看多** | ≥3 个 S 级同时加多仓 |
| **看多** | 聪明钱整体多头仓位增加 > 20% |
| **强烈看空** | ≥3 个 S 级同时加空仓 |
| **看空** | 聪明钱整体空头仓位增加 > 20% |

### 入场条件

| 信号强度 | 条件 | 仓位 |
|----------|------|------|
| **强** | ≥3 个 S 级同向 + 共识 >70% | 100% |
| **中** | 共识 >65% 或 2 个 S 级同向 | 50% |
| **弱** | 共识 60-65% | 观望或 25% |

### 出场规则

| 条件 | 动作 |
|------|------|
| 盈利 **≥ 5%** | 止盈 50% |
| 盈利 **≥ 8%** | 全部止盈 |
| 亏损 **≥ 3%** | 止损 |
| 跟单的 S 级地址平仓 | 跟随平仓 |
| 共识回归 40%-60% | 减仓或平仓 |
| 持仓 **> 48小时** | 评估是否平仓 |

## 🔄 跟单方式

### A. 镜像跟单（激进）⚠️

```
聪明钱开 10x 多 BTC
→ 你开 10x 多 BTC（同杠杆）
```

❌ 风险高，不推荐

### B. 方向跟单（推荐）✅

```
聪明钱开 10x 多 BTC
→ 你开 1-2x 多 BTC（降杠杆）
```

只跟方向，自己控制杠杆

### C. 延迟跟单（保守）✅

```
聪明钱开多 BTC
→ 等 5-15 分钟确认没撤单
→ 再跟单
```

避免被假动作骗

## ⚙️ 参数配置

```yaml
# config/strategies/smart_money.yaml

# ===== 聪明钱池配置 =====
smart_money_pool:
  # S 级
  s_tier:
    min_pnl: 1000000        # $1M+
    min_win_rate: 0.60      # 60%+
    max_drawdown: 0.20      # <20%
    weight: 100
    pool_size: 20
  # A 级  
  a_tier:
    min_pnl: 500000         # $500K+
    min_win_rate: 0.55      # 55%+
    max_drawdown: 0.25      # <25%
    weight: 70
    pool_size: 50
  # B 级
  b_tier:
    min_pnl: 100000         # $100K+
    min_win_rate: 0.55      # 55%+
    max_drawdown: 0.30      # <30%
    weight: 40
    pool_size: 100
  
  # 通用
  min_trades: 100           # 至少 100 笔
  active_days: 7            # 7天内活跃
  refresh_interval: 86400   # 每天刷新

# ===== 信号阈值 =====
signals:
  consensus_long: 0.65      # 共识 >65% → 开多
  consensus_short: 0.35     # 共识 <35% → 开空
  strong_consensus_long: 0.70
  strong_consensus_short: 0.30
  s_tier_trigger: 3         # ≥3个 S 级同向触发强信号
  neutral_low: 0.40
  neutral_high: 0.60

# ===== 风控 =====
risk_management:
  stop_loss: 0.03           # 3%
  take_profit_1: 0.05       # 5% 减仓
  take_profit_2: 0.08       # 8% 全平
  max_hold_hours: 48
  leverage: 2               # 最高 2x
  follow_delay: 300         # 延迟 5 分钟跟单

# ===== 币种 =====
symbols:
  - BTC
  - ETH
  - SOL
```

## 💻 实现代码

### 聪明钱池管理

```python
# src/strategies/smart_money_pool.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from datetime import datetime, timedelta
from enum import Enum

class Tier(Enum):
    S = 's_tier'
    A = 'a_tier'
    B = 'b_tier'

@dataclass
class SmartMoneyProfile:
    address: str
    tier: Tier
    total_pnl: float
    win_rate: float
    max_drawdown: float
    trade_count: int
    last_trade_time: datetime
    weight: int
    current_position: Optional[Dict] = None

class SmartMoneyPoolManager:
    def __init__(self, config: dict):
        self.config = config
        self.pool: List[SmartMoneyProfile] = []
        self.last_refresh: Optional[datetime] = None
    
    async def refresh_pool(self):
        """刷新聪明钱池"""
        print("开始刷新聪明钱池...")
        
        # 从排行榜获取盈利地址（按 PnL 降序）
        winners = await self._fetch_leaderboard_winners()
        
        # 按等级筛选
        s_tier = []
        a_tier = []
        b_tier = []
        
        for address in winners:
            profile = await self._analyze_address(address)
            
            tier = self._classify_tier(profile)
            if tier == Tier.S and len(s_tier) < self.config['smart_money_pool']['s_tier']['pool_size']:
                profile.tier = Tier.S
                profile.weight = self.config['smart_money_pool']['s_tier']['weight']
                s_tier.append(profile)
            elif tier == Tier.A and len(a_tier) < self.config['smart_money_pool']['a_tier']['pool_size']:
                profile.tier = Tier.A
                profile.weight = self.config['smart_money_pool']['a_tier']['weight']
                a_tier.append(profile)
            elif tier == Tier.B and len(b_tier) < self.config['smart_money_pool']['b_tier']['pool_size']:
                profile.tier = Tier.B
                profile.weight = self.config['smart_money_pool']['b_tier']['weight']
                b_tier.append(profile)
        
        self.pool = s_tier + a_tier + b_tier
        self.last_refresh = datetime.utcnow()
        
        print(f"聪明钱池刷新完成: S={len(s_tier)}, A={len(a_tier)}, B={len(b_tier)}")
    
    def _classify_tier(self, profile) -> Optional[Tier]:
        """对地址进行分级"""
        cfg = self.config['smart_money_pool']
        
        # S 级
        s = cfg['s_tier']
        if (profile.total_pnl >= s['min_pnl'] and 
            profile.win_rate >= s['min_win_rate'] and
            profile.max_drawdown <= s['max_drawdown']):
            return Tier.S
        
        # A 级
        a = cfg['a_tier']
        if (profile.total_pnl >= a['min_pnl'] and 
            profile.win_rate >= a['min_win_rate'] and
            profile.max_drawdown <= a['max_drawdown']):
            return Tier.A
        
        # B 级
        b = cfg['b_tier']
        if (profile.total_pnl >= b['min_pnl'] and 
            profile.win_rate >= b['min_win_rate'] and
            profile.max_drawdown <= b['max_drawdown']):
            return Tier.B
        
        return None
    
    def get_by_tier(self, tier: Tier) -> List[SmartMoneyProfile]:
        """获取指定等级的聪明钱"""
        return [p for p in self.pool if p.tier == tier]
    
    async def update_positions(self):
        """更新所有聪明钱的当前持仓"""
        # 与 loser_pool 类似
        pass
```

### 策略主逻辑

```python
# src/strategies/smart_money.py

from dataclasses import dataclass
from typing import Literal, List
from .smart_money_pool import SmartMoneyPoolManager, SmartMoneyProfile, Tier

@dataclass
class Signal:
    direction: Literal['long', 'short', 'neutral']
    strength: float
    weighted_ratio: float
    s_tier_consensus: int  # S级同向数量
    reason: str

class SmartMoneyStrategy:
    def __init__(self, config: dict):
        self.config = config
        self.pool_manager = SmartMoneyPoolManager(config)
    
    async def initialize(self):
        """初始化策略"""
        await self.pool_manager.refresh_pool()
    
    def calculate_weighted_ratio(self) -> tuple[float, int, int]:
        """计算加权多头占比"""
        pool = self.pool_manager.pool
        
        with_position = [p for p in pool if p.current_position]
        if not with_position:
            return 0.5, 0, 0
        
        long_weight = sum(
            p.weight for p in with_position 
            if p.current_position['side'] == 'long'
        )
        total_weight = sum(p.weight for p in with_position)
        
        long_count = sum(
            1 for p in with_position 
            if p.current_position['side'] == 'long'
        )
        
        return long_weight / total_weight, long_count, len(with_position)
    
    def count_s_tier_consensus(self) -> tuple[int, int]:
        """统计 S 级共识"""
        s_tier = self.pool_manager.get_by_tier(Tier.S)
        with_position = [p for p in s_tier if p.current_position]
        
        if not with_position:
            return 0, 0
        
        long_count = sum(1 for p in with_position if p.current_position['side'] == 'long')
        short_count = len(with_position) - long_count
        
        return long_count, short_count
    
    def calculate_signal(self) -> Signal:
        """计算交易信号"""
        ratio, long_count, total = self.calculate_weighted_ratio()
        s_long, s_short = self.count_s_tier_consensus()
        thresholds = self.config['signals']
        
        # 强信号：S级共识 + 整体共识
        if s_long >= thresholds['s_tier_trigger'] and ratio >= thresholds['strong_consensus_long']:
            return Signal(
                direction='long',
                strength=1.0,
                weighted_ratio=ratio,
                s_tier_consensus=s_long,
                reason=f'强多头信号: S级{s_long}个做多, 共识{ratio:.1%}'
            )
        
        if s_short >= thresholds['s_tier_trigger'] and ratio <= thresholds['strong_consensus_short']:
            return Signal(
                direction='short',
                strength=1.0,
                weighted_ratio=ratio,
                s_tier_consensus=s_short,
                reason=f'强空头信号: S级{s_short}个做空, 共识{ratio:.1%}'
            )
        
        # 中等信号
        if ratio >= thresholds['consensus_long']:
            return Signal(
                direction='long',
                strength=0.5,
                weighted_ratio=ratio,
                s_tier_consensus=s_long,
                reason=f'多头信号: 共识{ratio:.1%}'
            )
        
        if ratio <= thresholds['consensus_short']:
            return Signal(
                direction='short',
                strength=0.5,
                weighted_ratio=ratio,
                s_tier_consensus=s_short,
                reason=f'空头信号: 共识{ratio:.1%}'
            )
        
        return Signal(
            direction='neutral',
            strength=0.0,
            weighted_ratio=ratio,
            s_tier_consensus=0,
            reason=f'中性: 共识{ratio:.1%}'
        )
    
    def should_exit(
        self, 
        pnl_pct: float, 
        hold_hours: float,
        current_ratio: float,
        followed_s_tier_closed: bool
    ) -> tuple[bool, str]:
        """判断是否应该平仓"""
        
        rm = self.config['risk_management']
        thresholds = self.config['signals']
        
        # 止损
        if pnl_pct <= -rm['stop_loss']:
            return True, f'止损 {pnl_pct:.2%}'
        
        # 全部止盈
        if pnl_pct >= rm['take_profit_2']:
            return True, f'止盈 {pnl_pct:.2%}'
        
        # 超时
        if hold_hours >= rm['max_hold_hours']:
            return True, f'持仓超时 {hold_hours:.1f}h'
        
        # 跟单的 S 级平仓了
        if followed_s_tier_closed:
            return True, 'S级目标平仓，跟随退出'
        
        # 共识回归中性
        if thresholds['neutral_low'] <= current_ratio <= thresholds['neutral_high']:
            return True, f'共识回归中性 {current_ratio:.1%}'
        
        return False, ''
    
    def should_reduce(self, pnl_pct: float) -> bool:
        """判断是否应该减仓"""
        return pnl_pct >= self.config['risk_management']['take_profit_1']
```

## 📊 预期表现

| 指标 | 预估值 |
|------|--------|
| 年交易次数 | 50-100 次 |
| 胜率 | 60-70% |
| 平均盈利 | +5% |
| 平均亏损 | -2.5% |
| 年化收益 | 35-60% |
| 最大回撤 | < 15% |

## 📊 聪明钱 vs 韭菜反向

| 维度 | 聪明钱跟单 | 韭菜反向 |
|------|------------|----------|
| **逻辑** | 跟赢家 | 反输家 |
| **筛选难度** | 较难（要稳定盈利） | 较易（亏钱的多） |
| **信号频率** | 中 | 中 |
| **胜率** | 60-70% | 60-65% |
| **风险** | 聪明钱也会错 | 韭菜偶尔对 |
| **优势** | 可能抓到大趋势 | 更适合震荡市 |
| **适合场景** | 趋势市 | 震荡市 |

## ✅ 优点

1. **跟随成功者** - 站在巨人肩膀上
2. **可能抓大行情** - 聪明钱更擅长趋势
3. **Hyperliquid 独有** - CEX 无法实现

## ⚠️ 缺点

1. **聪明钱也会错** - 胜率不是 100%
2. **可能滞后** - 入场比聪明钱晚
3. **维护成本高** - 需要持续监控
4. **聪明钱会变** - 曾经的大神可能翻车

## 📝 下一步

1. 实现排行榜盈利地址爬虫
2. 建立聪明钱分级系统
3. 实现延迟跟单逻辑
4. 回测历史表现
