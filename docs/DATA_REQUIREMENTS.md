# 反脆弱策略数据需求方案

> 版本: v1.0  
> 更新日期: 2026-03-30  
> 作者: Jason / 慧慧

---

## 一、数据源概览

| 数据源 | 覆盖范围 | 特点 | 状态 |
|--------|---------|------|------|
| **CoinGlass** | 30+ 交易所 (含 Hyperliquid) | 跨交易所聚合、宏观数据 | ✅ 已有会员 |
| **HyperBot** | 仅 Hyperliquid | 链上深度数据、地址级追踪 | 🔄 对接中 |
| **本地系统** | Hyperliquid | 1m K线 | ✅ 已有 |

---

## 二、已有数据

| 数据 | 颗粒度 | 历史深度 | 状态 |
|------|--------|---------|------|
| 价格 K线 (OHLCV) | 1m | - | ✅ 系统已有 |

---

## 三、需要获取的数据

### 3.1 CoinGlass 数据需求

| # | 数据类型 | 最小颗粒度 | 用途 | API Endpoint |
|---|---------|-----------|------|-------------|
| 1 | **Open Interest** | 1m | OI 变化、趋势强度、资金拥挤度 | `/api/futures/openInterest/ohlc-history` |
| 2 | **Funding Rate** | 实时 (8h结算) | 多空情绪、持仓成本、套利机会 | `/api/futures/fundingRate/ohlc-history` |
| 3 | **清算数据** | 1m | 级联清算风险、支撑阻力判断 | `/api/futures/liquidation/history` |
| 4 | **Long/Short Ratio** | 5m | 散户情绪反向指标 | `/api/futures/global-long-short-account-ratio/history` |
| 5 | **Taker Buy/Sell Volume** | 5m | 主动买卖力量判断 | `/api/futures/taker-buy-sell-volume/history` |

**CoinGlass Rate Limit:** 6000 次/分钟 (会员)

### 3.2 HyperBot 数据需求

| # | 数据类型 | 最小颗粒度 | 用途 | API Endpoint |
|---|---------|-----------|------|-------------|
| 1 | **K线 + Taker分离** | 1m | 主买/主卖量独立分析 | `/api/upgrade/v2/hl/klines-with-taker-vol/:coin/:interval` |
| 2 | **OI 历史** | 15m | Hyperliquid 专属 OI 数据 | `/api/upgrade/v2/hl/open-interest/history/:coin` |
| 3 | **清算历史** | 1m | HL 链上清算明细 | `/api/upgrade/v2/hl/liquidations/history` |
| 4 | **鲸鱼多空比** | 10m | 大户方向判断 | `/api/upgrade/v2/hl/whales/history-long-ratio` |
| 5 | **成交明细 (Fills)** | Tick (毫秒级) | 大单追踪、入场时机 | `/api/upgrade/v2/hl/fills/:address` |
| 6 | **挂单统计** | 实时快照 | 挂单墙分布、多空挂单比 | `/api/upgrade/v2/hl/orders/active-stats` |
| 7 | **地址交易统计** | 日级 | 聪明钱筛选、跟单对象评估 | `/api/upgrade/v2/hl/traders/:address/addr-stat` |
| 8 | **鲸鱼仓位** | 实时快照 | 大户持仓追踪 | `/api/upgrade/v2/hl/whales/open-positions` |
| 9 | **聪明钱发现** | 日级 | 高胜率地址筛选 | `/api/upgrade/v2/hl/smart/find` |
| 10 | **地址画像** | 日级 | 胜率、最大回撤、平均持仓时间 | `/api/upgrade/v2/hl/traders/:address/addr-stat` |

---

## 四、颗粒度采用方案

| 数据类型 | CoinGlass 颗粒度 | HyperBot 颗粒度 | 采用方案 |
|---------|-----------------|----------------|---------|
| 价格 K线 | - | - | **系统已有 (1m)** |
| Open Interest | **1m** ✅ | 15m | CoinGlass (更细) |
| Funding Rate | **实时** ✅ | - | CoinGlass |
| 清算数据 | **1m** | **1m** | 两边都拉 (对比验证) |
| Long/Short Ratio | **5m** ✅ | - | CoinGlass |
| Taker Volume | 5m | **1m (分离)** ✅ | HyperBot (更细+分离) |
| 鲸鱼多空比 | - | **10m** ✅ | HyperBot 独有 |
| 成交明细 | - | **Tick** ✅ | HyperBot 独有 |
| 挂单分布 | - | **实时** ✅ | HyperBot 独有 |
| 地址画像 | - | **日级** ✅ | HyperBot 独有 |

---

## 五、数据拉取策略

### 5.1 回测场景

一次性批量拉取历史数据，存入时序数据库。

| 数据 | 拉取方式 | 历史深度需求 |
|------|---------|-------------|
| OI (1m) | CoinGlass 批量拉取 | ≥6个月 |
| Funding Rate | CoinGlass 批量拉取 | ≥6个月 |
| 清算 (1m) | CoinGlass + HyperBot 批量拉取 | ≥3个月 |
| Long/Short (5m) | CoinGlass 批量拉取 | ≥6个月 |
| Taker Volume (1m) | HyperBot 批量拉取 | ≥3个月 |
| 鲸鱼多空比 (10m) | HyperBot 批量拉取 | ≥3个月 |
| 成交 Tick | HyperBot 批量拉取 | 2025-11 起 |
| 地址画像 | HyperBot 批量拉取 | 全量 |

### 5.2 实盘场景

定时拉取 + WebSocket 实时推送。

| 数据 | 更新方式 | 更新频率 |
|------|---------|---------|
| OI (1m) | 定时拉取 | 每分钟 |
| Funding Rate | 定时拉取 | 每小时 |
| 清算 | WebSocket 推送 | 实时 |
| Long/Short (5m) | 定时拉取 | 每5分钟 |
| Taker Volume (1m) | 定时拉取 | 每分钟 |
| 鲸鱼多空比 (10m) | 定时拉取 | 每10分钟 |
| 成交 Tick | WebSocket 推送 | 实时 |
| 挂单分布 | 定时拉取 | 每分钟 |
| 目标地址仓位 | WebSocket 推送 | 实时 (事件触发) |

---

## 六、衍生指标计算

基于原始数据自行计算的复合指标：

| # | 指标名称 | 计算公式 | 用途 |
|---|---------|---------|------|
| 1 | **OI/Volume 比率** | OI ÷ 24h Volume | 杠杆拥挤度判断 |
| 2 | **清算密度** | 清算量 ÷ OI | 市场脆弱度评估 |
| 3 | **Funding 极值偏离** | (当前FR - 均值) ÷ 标准差 | 情绪极端度 |
| 4 | **鲸鱼-散户背离** | 鲸鱼多空比 - 散户多空比 | 聪明钱信号 |
| 5 | **大单净流入** | Σ(大单买) - Σ(大单卖) | 资金流向判断 |
| 6 | **挂单倾斜度** | Bid墙 ÷ Ask墙 | 短期方向预判 |
| 7 | **地址胜率加权信号** | Σ(地址信号 × 胜率权重) | 跟单优先级排序 |
| 8 | **波动率调整仓位** | 基础仓位 × (目标波动率 ÷ 实际波动率) | 动态风控 |

---

## 七、待确认问题 ⚠️

需要与 HyperBot 团队确认：

| # | 问题 | 当前情况 | 期望 |
|---|------|---------|------|
| 1 | **OI 颗粒度** | 目前 15m 起 | 能否提供 1m 或 5m？ |
| 2 | **成交历史深度** | 目前 2025-11 起 | 能否更早？ |
| 3 | **挂单分布历史** | 仅实时快照 | 是否有历史快照？(回测需要) |
| 4 | **地址仓位历史** | 无 | 能否提供历史仓位快照？(跟单回测需要) |

---

## 八、数据存储方案

| 数据类型 | 存储方案 | 说明 |
|---------|---------|------|
| 时序数据 (K线、OI、FR等) | TimescaleDB / InfluxDB | 高效时间范围查询 |
| 地址画像 | PostgreSQL | 结构化查询 |
| 实时信号 | Redis | 低延迟读写 |
| 回测结果 | PostgreSQL | 持久化存储 |

---

## 九、接口详细参数

### 9.1 CoinGlass 接口

```python
# Open Interest 历史
GET /api/futures/openInterest/ohlc-history
Params: symbol, interval(1m/5m/15m/1h/4h/1d), limit

# Funding Rate 历史
GET /api/futures/fundingRate/ohlc-history
Params: symbol, interval, limit

# 清算历史
GET /api/futures/liquidation/history
Params: symbol, interval

# Long/Short Ratio
GET /api/futures/global-long-short-account-ratio/history
Params: symbol, interval

# Taker Volume
GET /api/futures/taker-buy-sell-volume/history
Params: symbol, interval

# WebSocket 清算订阅
wss://open-api-v4.coinglass.com/ws
Subscribe: liquidationOrders
```

### 9.2 HyperBot 接口

```python
# K线 + Taker 分离
GET /api/upgrade/v2/hl/klines-with-taker-vol/:coin/:interval
Params: startTime, endTime, limit(max 2000)

# OI 历史
GET /api/upgrade/v2/hl/open-interest/history/:coin
Params: interval(15m~180d)

# 清算历史
GET /api/upgrade/v2/hl/liquidations/history
Params: coin, interval(1m~60d), limit(max 100)

# 鲸鱼多空比历史
GET /api/upgrade/v2/hl/whales/history-long-ratio
Params: interval(10m/1h/4h/1d), limit(max 200)

# 鲸鱼仓位
GET /api/upgrade/v2/hl/whales/open-positions
Params: coin, dir(long/short), topBy, take(max 200)

# 聪明钱发现
POST /api/upgrade/v2/hl/smart/find
Body: pageNum, pageSize(max 25), period, sort, pnlList

# 地址统计
GET /api/upgrade/v2/hl/traders/:address/addr-stat
Params: period(1/7/30/0)

# 地址成交
GET /api/upgrade/v2/hl/fills/:address
Params: coin, limit(max 2000)

# 挂单统计
GET /api/upgrade/v2/hl/orders/active-stats
Params: coin, whaleThreshold

# WebSocket 订阅
WS /api/upgrade/v2/hl/ws
Subscribe: candle, l2Book, trades, userFills

# 地址成交订阅
WS /api/upgrade/v2/hl/ws/fills
Body: addresses[]
```

---

## 十、版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-03-30 | 初版，整理数据需求方案 |

---

## 附录：HyperBot API 文档

- 企业级 API 介绍: https://hyperbot.network/data-api
- 接口文档: https://openapi-docs.hyperbot.network/apis/hyperliquid
