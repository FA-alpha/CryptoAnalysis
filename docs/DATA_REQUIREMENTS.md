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

## 七、数据缺口分析 ⚠️

以下数据 HyperBot **目前不提供**，需要自建或寻找替代方案：

| # | 缺失数据 | 现状 | 影响 | 替代方案 |
|---|---------|------|------|---------|
| 1 | **Hyperliquid OI (1m/5m)** | HyperBot 仅支持 15m 起 | 无法做精细 OI 分析 | 用 CoinGlass 的 Hyperliquid OI (1m) |
| 2 | **成交历史 (2025-11前)** | 仅 2025-11 起 | 长期回测数据不足 | 从现在开始自建存储 |
| 3 | **挂单分布历史快照** | 仅实时快照，无历史 | 挂单策略无法回测 | 自建定时快照存储 (建议每分钟) |
| 4 | **地址历史仓位快照** | 无 | 跟单策略无法精确回测 | 自建监控目标地址，存储仓位变化 |

### 自建数据建议

```python
# 需要自建的定时任务
1. 挂单分布快照 - 每分钟调用 /hl/orders/active-stats，存入时序库
2. 目标地址仓位 - 每分钟调用 /hl/traders/:address/addr-stat，存入时序库
3. 鲸鱼仓位快照 - 每分钟调用 /hl/whales/open-positions，存入时序库
```

---

## 八、数据存储方案

### 8.1 方案 A：纯 MySQL（当前采用）✅

**适用场景：** MVP 阶段、<10 币种、快速验证策略

| 数据类型 | 存储方案 | 说明 |
|---------|---------|------|
| 时序数据 (K线、OI、FR、清算等) | **MySQL** | 分表存储，按时间分区 |
| 地址画像 / 交易员统计 | **MySQL** | 结构化查询 |
| 实时缓存 | **应用层内存** | Python dict / LRU Cache |
| 回测结果 / 策略配置 | **MySQL** | 持久化存储 |

#### 纯 MySQL 架构图

```
┌─────────────────────────────────────────────────────────┐
│                      数据采集层                          │
│  CoinGlass API  |  HyperBot API  |  WebSocket 实时流    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   AWS RDS MySQL                          │
├─────────────────────────────────────────────────────────┤
│  时序数据表          │  业务数据表                        │
│  ─────────────       │  ─────────────                    │
│  • kline_1m_*       │  • trader_profile                 │
│  • open_interest_*  │  • follow_targets                 │
│  • funding_rate     │  • backtest_results               │
│  • liquidation_*    │  • strategy_config                │
│  • long_short_ratio │                                   │
│  • taker_volume_*   │                                   │
│  • whale_ratio      │                                   │
│  (* = 按月分表)      │                                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   应用服务器 (EC2)                       │
├─────────────────────────────────────────────────────────┤
│  • 数据采集服务                                          │
│  • 策略引擎                                              │
│  • 内存缓存 (最新价格、实时信号)                          │
└─────────────────────────────────────────────────────────┘
```

#### MySQL 时序数据表设计

```sql
-- ============================================
-- 时序数据表 (建议按月分表，如 kline_1m_202603)
-- ============================================

-- K线数据 (1分钟)
CREATE TABLE kline_1m (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    open_time DATETIME NOT NULL,
    open DECIMAL(20,8),
    high DECIMAL(20,8),
    low DECIMAL(20,8),
    close DECIMAL(20,8),
    volume DECIMAL(20,8),
    taker_buy_vol DECIMAL(20,8),
    taker_sell_vol DECIMAL(20,8),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_time (symbol, open_time),
    KEY idx_open_time (open_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE (TO_DAYS(open_time)) (
    PARTITION p202601 VALUES LESS THAN (TO_DAYS('2026-02-01')),
    PARTITION p202602 VALUES LESS THAN (TO_DAYS('2026-03-01')),
    PARTITION p202603 VALUES LESS THAN (TO_DAYS('2026-04-01')),
    PARTITION p202604 VALUES LESS THAN (TO_DAYS('2026-05-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- Open Interest
CREATE TABLE open_interest (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'all',
    record_time DATETIME NOT NULL,
    value DECIMAL(20,8),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_exchange_time (symbol, exchange, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Funding Rate
CREATE TABLE funding_rate (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'all',
    record_time DATETIME NOT NULL,
    rate DECIMAL(12,8),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_exchange_time (symbol, exchange, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 清算数据
CREATE TABLE liquidation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    record_time DATETIME NOT NULL,
    side ENUM('long', 'short') NOT NULL,
    amount DECIMAL(20,8),
    count INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_symbol_time (symbol, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Long/Short Ratio
CREATE TABLE long_short_ratio (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    record_time DATETIME NOT NULL,
    ratio DECIMAL(10,6),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_time (symbol, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Taker Buy/Sell Volume
CREATE TABLE taker_volume (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    record_time DATETIME NOT NULL,
    buy_vol DECIMAL(20,8),
    sell_vol DECIMAL(20,8),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_time (symbol, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 鲸鱼多空比
CREATE TABLE whale_ratio (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    record_time DATETIME NOT NULL,
    ratio DECIMAL(10,6),
    long_count INT,
    short_count INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_symbol_time (symbol, record_time),
    KEY idx_record_time (record_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 挂单分布快照 (自建)
CREATE TABLE order_book_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    snapshot_time DATETIME NOT NULL,
    bid_wall DECIMAL(20,8),
    ask_wall DECIMAL(20,8),
    bid_count INT,
    ask_count INT,
    whale_bid_ratio DECIMAL(5,4),
    whale_ask_ratio DECIMAL(5,4),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_symbol_time (symbol, snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- 业务数据表
-- ============================================

-- 地址画像
CREATE TABLE trader_profile (
    address VARCHAR(42) PRIMARY KEY,
    win_rate DECIMAL(5,4),
    total_pnl DECIMAL(20,8),
    max_drawdown DECIMAL(5,4),
    avg_holding_seconds INT,
    trade_count INT,
    last_trade_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 跟单目标
CREATE TABLE follow_targets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(42) NOT NULL,
    strategy_name VARCHAR(50),
    weight DECIMAL(3,2) DEFAULT 1.00,
    enabled TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_address (address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 回测结果
CREATE TABLE backtest_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    params JSON,
    start_date DATE,
    end_date DATE,
    total_return DECIMAL(10,4),
    sharpe_ratio DECIMAL(6,4),
    max_drawdown DECIMAL(5,4),
    win_rate DECIMAL(5,4),
    trade_count INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_strategy (strategy_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 策略配置
CREATE TABLE strategy_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL UNIQUE,
    config JSON,
    enabled TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### MySQL 性能优化建议

1. **分区表** - 时序数据按月分区，便于历史数据归档
2. **索引优化** - 时间字段 + symbol 联合索引
3. **批量写入** - 使用 `INSERT ... ON DUPLICATE KEY UPDATE` 批量插入
4. **读写分离** - 如有需要，RDS 支持只读副本
5. **定期归档** - 超过 6 个月的数据可以导出到 S3

---

### 8.2 方案 B：MySQL + InfluxDB + Redis（升级方案）

**适用场景：** 生产环境、多币种、高频数据、低延迟要求

> ⚠️ 此方案保留供后续升级使用，当数据量增大或性能不足时再部署。

| 数据类型 | 存储方案 | 说明 |
|---------|---------|------|
| 时序数据 (K线、OI、FR、清算等) | **InfluxDB** | 高效时间范围查询、聚合计算 |
| 地址画像 / 交易员统计 | **MySQL** | 结构化查询，团队熟悉 |
| 实时信号 / 缓存 | **Redis** | 低延迟读写 |
| 回测结果 / 策略配置 | **MySQL** | 持久化存储 |

#### 升级版架构图

```
┌─────────────────────────────────────────────────────────┐
│                      数据采集层                          │
│  CoinGlass API  |  HyperBot API  |  WebSocket 实时流    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      数据存储层                          │
├─────────────────┬─────────────────┬─────────────────────┤
│   InfluxDB      │     MySQL       │      Redis          │
│   (时序数据)     │   (业务数据)     │    (实时缓存)        │
├─────────────────┼─────────────────┼─────────────────────┤
│ • K线 (1m)      │ • 地址画像      │ • 最新价格          │
│ • OI (1m)       │ • 交易员统计    │ • 实时信号          │
│ • Funding Rate  │ • 策略配置      │ • 挂单分布快照      │
│ • 清算 (1m)     │ • 回测结果      │ • 鲸鱼仓位快照      │
│ • Long/Short    │ • 跟单目标列表  │                     │
│ • Taker Volume  │                 │                     │
│ • 鲸鱼多空比    │                 │                     │
└─────────────────┴─────────────────┴─────────────────────┘
```

#### InfluxDB 部署 (Docker)

```bash
# 在 EC2 上一键部署
docker run -d \
  --name influxdb \
  -p 8086:8086 \
  -v influxdb-data:/var/lib/influxdb2 \
  influxdb:2.7

# Redis 部署
docker run -d \
  --name redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine
```

#### InfluxDB Measurement 设计

```
Measurement: kline_1m
Tags: symbol
Fields: open, high, low, close, volume, taker_buy_vol, taker_sell_vol

Measurement: open_interest
Tags: symbol, exchange
Fields: value

Measurement: funding_rate
Tags: symbol, exchange  
Fields: rate

Measurement: liquidation
Tags: symbol, side (long/short)
Fields: amount, count

Measurement: long_short_ratio
Tags: symbol
Fields: ratio

Measurement: whale_long_short
Tags: symbol
Fields: ratio, long_count, short_count
```

#### 升级时机判断

| 指标 | 当前方案可支撑 | 需要升级 |
|------|--------------|---------|
| 币种数量 | < 20 | > 20 |
| 数据查询延迟 | < 500ms | > 500ms |
| 日数据量 | < 100万行 | > 100万行 |
| 实时信号延迟 | < 1s | < 100ms |

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
| v1.1 | 2026-03-30 | 确认 HyperBot 接口范围，明确数据缺口及自建方案 |
| v1.2 | 2026-03-30 | 存储方案改为 MySQL + InfluxDB，添加表结构设计 |
| v1.3 | 2026-03-30 | 采用纯 MySQL 方案 (方案A)，保留升级方案 (方案B) |

---

## 附录：HyperBot API 文档

- 企业级 API 介绍: https://hyperbot.network/data-api
- 接口文档: https://openapi-docs.hyperbot.network/apis/hyperliquid
