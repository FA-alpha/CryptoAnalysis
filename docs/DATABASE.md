# 数据库设计文档

## 📊 数据库概览

**数据库名称**: `fourieralpha_hl`  
**字符集**: `utf8mb4`  
**引擎**: `InnoDB`  
**时区策略**: 所有 `DATETIME` 字段使用北京时间（Asia/Shanghai, UTC+8）

---

## 📋 表清单

| 表名 | 说明 | 状态 |
|------|------|------|
| [hl_address_list](#1-hl_address_list) | 地址列表 | ✅ 使用中 |
| [hl_fills](#2-hl_fills) | 交易历史（原始成交数据） | ✅ 使用中 |
| [hl_position_snapshots](#3-hl_position_snapshots) | 持仓快照（汇总） | 🚧 待开发 |
| [hl_position_details](#4-hl_position_details) | 持仓明细 | 🚧 待开发 |
| [hl_address_features](#5-hl_address_features) | 地址特征（计算结果） | 🚧 待开发 |
| [hl_fragile_scores](#6-hl_fragile_scores) | 脆弱地址评分 | 🚧 待开发 |
| [hl_fragile_pool](#7-hl_fragile_pool) | 脆弱地址池（实时监控） | 🚧 待开发 |
| [hl_reverse_signals](#8-hl_reverse_signals) | 反向跟单信号 | 🚧 待开发 |
| [hl_follow_trades](#9-hl_follow_trades) | 跟单交易记录 | 🚧 待开发 |
| [hl_monitor_logs](#10-hl_monitor_logs) | 实时监控日志 | 🚧 待开发 |
| [hl_backtest_results](#11-hl_backtest_results) | 回测结果 | 🚧 待开发 |

---

## 📑 视图清单

| 视图名称 | 说明 | 状态 |
|----------|------|------|
| [v_order_summary](#v_order_summary-订单汇总视图) | 订单级别的成交汇总 | ✅ 使用中 |

---

## 1. hl_address_list

### **表说明**
存储需要监控的地址列表。

### **表结构**

```sql
CREATE TABLE hl_address_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL UNIQUE COMMENT '钱包地址',
    label VARCHAR(100) COMMENT '地址标签/别名',
    source VARCHAR(50) DEFAULT 'manual' COMMENT '来源:hyperbot/manual',
    first_seen_at DATETIME NOT NULL COMMENT '首次发现时间',
    last_updated_at DATETIME NOT NULL COMMENT '最后更新时间',
    status ENUM('active', 'inactive', 'excluded') DEFAULT 'active' COMMENT '状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_last_updated (last_updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址列表';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| id | BIGINT | ✅ | 主键 | 1 |
| address | VARCHAR(66) | ✅ | 钱包地址（唯一） | `0x020ca66c...` |
| label | VARCHAR(100) | ❌ | 地址标签 | `麻吉大哥` |
| source | VARCHAR(50) | ❌ | 来源 | `manual`, `hyperbot` |
| first_seen_at | DATETIME | ✅ | 首次发现时间 | `2026-04-07 13:59:38` |
| last_updated_at | DATETIME | ✅ | 最后更新时间 | `2026-04-07 15:03:38` |
| status | ENUM | ❌ | 状态 | `active`, `inactive`, `excluded` |
| created_at | DATETIME | ✅ | 创建时间 | `2026-04-07 13:59:38` |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | 主键 |
| UNIQUE | address | 唯一 | 防重复 |
| idx_status | status | 普通 | 状态筛选 |
| idx_last_updated | last_updated_at | 普通 | 按更新时间排序 |

### **使用示例**

```sql
-- 插入新地址
INSERT INTO hl_address_list 
(address, label, source, first_seen_at, last_updated_at, status)
VALUES 
('0x020ca66c30bec2c4fe3861a94e4db4a498a35872', '麻吉大哥', 'manual', NOW(), NOW(), 'active');

-- 查询活跃地址
SELECT * FROM hl_address_list WHERE status = 'active';

-- 更新最后更新时间
UPDATE hl_address_list SET last_updated_at = NOW() WHERE address = '0x...';
```

---

## 2. hl_fills

### **表说明**
存储用户的**每笔成交记录**（最细粒度的原始数据）。

### **表结构**

```sql
CREATE TABLE hl_fills (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    sz DECIMAL(20,8) NOT NULL COMMENT '成交数量',
    px DECIMAL(20,6) NOT NULL COMMENT '成交价格',
    dir VARCHAR(20) NOT NULL COMMENT '方向',
    closed_pnl DECIMAL(20,6) DEFAULT 0 COMMENT '已实现盈亏',
    fee DECIMAL(20,6) DEFAULT 0 COMMENT '手续费',
    fee_token VARCHAR(10) DEFAULT 'USDC' COMMENT '手续费币种',
    time BIGINT NOT NULL COMMENT '成交时间戳(毫秒)',
    hash VARCHAR(100) NOT NULL COMMENT '订单哈希',
    tid BIGINT NOT NULL COMMENT '成交ID（唯一标识）',
    oid BIGINT NOT NULL COMMENT '订单ID',
    twap_id VARCHAR(100) COMMENT 'TWAP订单ID',
    side VARCHAR(5) COMMENT '主动方向:A/B',
    start_position DECIMAL(20,8) COMMENT '成交前持仓',
    crossed BOOLEAN DEFAULT TRUE COMMENT '是否全仓模式',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',

    UNIQUE KEY uk_tid (tid),
    INDEX idx_address_time (address, time DESC),
    INDEX idx_hash (hash),
    INDEX idx_oid (oid),
    INDEX idx_coin (coin),
    INDEX idx_dir (dir),
    INDEX idx_time (time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易历史(原始成交数据)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| **tid** | BIGINT | ✅ | **成交ID（唯一键）** | `449746928007068` |
| oid | BIGINT | ✅ | 订单ID（同一订单共享） | `372793001458` |
| hash | VARCHAR(100) | ✅ | 订单哈希（同一订单共享） | `0xc6e3ad...` |
| address | VARCHAR(66) | ✅ | 钱包地址 | `0x020ca66c...` |
| coin | VARCHAR(20) | ✅ | 币种 | `ETH`, `BTC`, `SOL` |
| sz | DECIMAL(20,8) | ✅ | 成交数量 | `12.755` |
| px | DECIMAL(20,6) | ✅ | 成交价格 | `2096.8` |
| dir | VARCHAR(20) | ✅ | 方向 | `Open Long`, `Close Long`, `Open Short`, `Close Short`, `Liquidation` |
| closed_pnl | DECIMAL(20,6) | ❌ | 已实现盈亏（平仓时才有值） | `22.147968` |
| fee | DECIMAL(20,6) | ❌ | 手续费 | `8.023405` |
| fee_token | VARCHAR(10) | ❌ | 手续费币种 | `USDC` |
| time | BIGINT | ✅ | 时间戳（毫秒） | `1775543005352` |
| side | VARCHAR(5) | ❌ | 主动方向 | `B`（买入主动），`A`（卖出主动） |
| start_position | DECIMAL(20,8) | ❌ | 成交前持仓 | `9512.245` |
| crossed | BOOLEAN | ❌ | 是否全仓 | `true`（全仓），`false`（逐仓） |
| twap_id | VARCHAR(100) | ❌ | TWAP订单ID | `null` |
| created_at | DATETIME | ✅ | 入库时间（北京时间） | `2026-04-07 15:03:38` |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| uk_tid | tid | **唯一** | **防重复（主要去重键）** |
| idx_address_time | address, time | 普通 | 按地址和时间查询 |
| idx_hash | hash | 普通 | 查询同一订单的多笔成交 |
| idx_oid | oid | 普通 | 按订单ID查询 |
| idx_coin | coin | 普通 | 按币种统计 |
| idx_dir | dir | 普通 | 按方向统计 |

### **重要说明**

#### **1. 一个订单可能有多笔成交**
```
订单 372793001458（25 ETH）被拆成 5 笔成交：
  - tid: 28059324263109  → 0.9116 ETH
  - tid: 449746928007068 → 12.7550 ETH
  - tid: 648709636200215 → 2.7733 ETH
  - tid: 954770577116485 → 8.5501 ETH
  - tid: 1084573600026477 → 0.0100 ETH

共享相同的 oid 和 hash，但每笔有唯一的 tid
```

#### **2. 唯一键必须用 tid**
- ❌ **不能用 hash**：同一订单多笔成交会丢失数据
- ✅ **必须用 tid**：每笔成交都有唯一 tid

#### **3. start_position 的作用**
记录每笔成交前的持仓，可以追踪持仓变化轨迹。

#### **4. closedPnl 只在平仓时有值**
- 开仓：`closedPnl = 0`
- 平仓：`closedPnl > 0`（盈利）或 `closedPnl < 0`（亏损）

### **使用示例**

```sql
-- 查询某个地址的最近 10 笔成交
SELECT * FROM hl_fills 
WHERE address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872' 
ORDER BY time DESC 
LIMIT 10;

-- 查询某个订单的所有成交
SELECT * FROM hl_fills 
WHERE oid = 372793001458 
ORDER BY tid;

-- 计算某个地址的总盈亏
SELECT SUM(closed_pnl) as total_pnl, SUM(fee) as total_fee
FROM hl_fills 
WHERE address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872';

-- 统计胜率（只看平仓订单）
SELECT 
    COUNT(*) as total_closes,
    SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
FROM hl_fills 
WHERE address = '0x...' AND dir LIKE 'Close%';
```

---

## v_order_summary（订单汇总视图）

### **视图说明**
将 `hl_fills` 表按订单（oid）聚合，提供**订单级别的汇总信息**。

### **视图定义**

```sql
CREATE OR REPLACE VIEW v_order_summary AS
SELECT 
    address,
    oid,
    hash,
    coin,
    dir,
    COUNT(*) as fill_count,                         -- 成交笔数
    SUM(sz) as total_sz,                            -- 总数量
    AVG(px) as avg_px,                              -- 平均价格
    SUM(fee) as total_fee,                          -- 总手续费
    SUM(closed_pnl) as total_pnl,                   -- 总盈亏
    MIN(time) as first_fill_time,                   -- 首次成交时间
    MAX(time) as last_fill_time,                    -- 最后成交时间
    MIN(start_position) as start_position,          -- 订单前持仓
    MIN(start_position) + (CASE 
        WHEN dir LIKE '%Long' THEN SUM(sz)
        WHEN dir LIKE '%Short' THEN -SUM(sz)
        ELSE 0
    END) as end_position,                           -- 订单后持仓
    MAX(crossed) as is_crossed                      -- 是否全仓
FROM hl_fills
GROUP BY address, oid, hash, coin, dir;
```

### **字段说明**

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| address | VARCHAR(66) | 钱包地址 | `0x020ca66c...` |
| oid | BIGINT | 订单ID | `371504673897` |
| hash | VARCHAR(100) | 订单哈希 | `0x7a6267f2...` |
| coin | VARCHAR(20) | 币种 | `ETH` |
| dir | VARCHAR(20) | 方向 | `Open Long` |
| **fill_count** | INT | **成交笔数** | `10`（订单被拆成10笔） |
| **total_sz** | DECIMAL | **总数量** | `25.0000` ETH |
| **avg_px** | DECIMAL | **平均成交价** | `2119.60` |
| **total_fee** | DECIMAL | **总手续费** | `15.896996` USDC |
| **total_pnl** | DECIMAL | **总盈亏** | `0.0`（开仓订单） |
| first_fill_time | BIGINT | 首次成交时间（毫秒） | `1775434788310` |
| last_fill_time | BIGINT | 最后成交时间（毫秒） | `1775434788310` |
| **start_position** | DECIMAL | **订单前持仓** | `7000.0000` |
| **end_position** | DECIMAL | **订单后持仓** | `7025.0000` |
| is_crossed | BOOLEAN | 是否全仓 | `1` (true) |

### **计算逻辑**

#### **end_position（订单后持仓）**
```sql
end_position = start_position + (CASE 
    WHEN dir = 'Open Long'  THEN +total_sz
    WHEN dir = 'Close Long' THEN -total_sz
    WHEN dir = 'Open Short' THEN -total_sz
    WHEN dir = 'Close Short' THEN +total_sz
END)
```

**示例**：
```
订单前持仓: 7000.0000 ETH
订单操作: Open Long 25 ETH
订单后持仓: 7000 + 25 = 7025.0000 ETH ✅
```

### **使用示例**

```sql
-- 查找被拆分最多的订单（流动性差）
SELECT * FROM v_order_summary 
WHERE fill_count > 50 
ORDER BY fill_count DESC;

-- 查找高手续费订单
SELECT oid, coin, total_sz, total_fee, total_fee / total_sz as fee_per_unit
FROM v_order_summary 
ORDER BY total_fee DESC 
LIMIT 10;

-- 查找大额订单
SELECT * FROM v_order_summary 
WHERE total_sz > 100 
ORDER BY total_sz DESC;

-- 统计某地址的订单数量
SELECT 
    address,
    COUNT(*) as order_count,
    AVG(fill_count) as avg_fills_per_order,
    SUM(total_fee) as total_fees_paid
FROM v_order_summary
WHERE address = '0x...'
GROUP BY address;
```

---

## 3. hl_position_snapshots

### **表说明**
存储用户的**账户级别持仓快照**（时间序列数据）。

### **表结构**

```sql
CREATE TABLE hl_position_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    snapshot_time BIGINT NOT NULL COMMENT '快照时间戳(毫秒)',
    account_value DECIMAL(20, 6) NOT NULL COMMENT '账户总价值',
    total_margin_used DECIMAL(20, 6) NOT NULL COMMENT '已用保证金',
    total_raw_usd DECIMAL(20, 6) COMMENT '钱包余额/USD净余额(可为负)',
    total_ntl_pos DECIMAL(20, 6) COMMENT '总名义持仓价值',
    withdrawable DECIMAL(20, 6) COMMENT '可提现金额',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（北京时间）',

    UNIQUE KEY uk_address_time (address, snapshot_time),
    INDEX idx_snapshot_time (snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持仓快照(账户级别)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 | API 来源 |
|------|------|------|------|----------|
| id | BIGINT | ✅ | 主键 | - |
| address | VARCHAR(66) | ✅ | 钱包地址 | 请求参数 |
| snapshot_time | BIGINT | ✅ | 快照时间戳（毫秒） | `time` |
| account_value | DECIMAL(20,6) | ✅ | 账户总价值 | `marginSummary.accountValue` |
| total_margin_used | DECIMAL(20,6) | ✅ | 已用保证金 | `marginSummary.totalMarginUsed` |
| total_raw_usd | DECIMAL(20,6) | ❌ | 钱包余额 / USD 净余额（可能为负）⚠️ | `marginSummary.totalRawUsd` |
| total_ntl_pos | DECIMAL(20,6) | ❌ | 总名义持仓价值 | `marginSummary.totalNtlPos` |
| withdrawable | DECIMAL(20,6) | ❌ | 可提现金额 | `withdrawable` |
| created_at | DATETIME | ✅ | 入库时间 | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | 主键 |
| uk_address_time | address, snapshot_time | **唯一** | **防止同一时刻重复** |
| idx_snapshot_time | snapshot_time | 普通 | 按时间查询 |

### **重要说明**

#### **时间序列数据**
- 每次采集插入**一条新快照**（不是覆盖）
- 用于追踪账户价值变化、保证金使用率趋势
- 唯一约束防止同一时刻重复采集

#### **total_raw_usd 为负数的情况**

**定义**：
```
total_raw_usd = 初始存入 + 所有已平仓盈亏 - 手续费 - 资金费 - 提现 + 追加存入
```

当 `total_raw_usd < 0` 时，表明账户的**历史累计亏损（含提现）超过初始本金**。

**示例**：
```sql
account_value = 1,342,454.16 USDC       -- 当前账户总价值
total_raw_usd = -18,153,503.34 USDC     -- 钱包余额（负数）
total_ntl_pos = 19,495,957.50 USDC      -- 总名义持仓价值

计算：
account_value = total_raw_usd + unrealized_pnl
1,342,454 ≈ -18,153,503 + 19,495,957 ✅
```

**这意味着**：
- 用户历史累计亏损 1815 万 USDC
- 但当前持仓未实现盈亏 +1949 万 USDC
- 账户仍有净值 134 万 USDC
- **高杠杆、高风险账户特征** 💀

### **使用示例**

```sql
-- 查询某地址的最近 10 次快照
SELECT * FROM hl_position_snapshots 
WHERE address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872' 
ORDER BY snapshot_time DESC 
LIMIT 10;

-- 查看账户价值变化趋势
SELECT 
    FROM_UNIXTIME(snapshot_time/1000) as time,
    account_value,
    total_margin_used,
    ROUND(total_margin_used / account_value * 100, 2) as margin_ratio_pct
FROM hl_position_snapshots 
WHERE address = '0x...'
ORDER BY snapshot_time ASC;

-- 计算最大回撤
SELECT 
    MAX(account_value) as peak_value,
    MIN(account_value) as trough_value,
    ROUND((MAX(account_value) - MIN(account_value)) / MAX(account_value) * 100, 2) as max_drawdown_pct
FROM hl_position_snapshots 
WHERE address = '0x...';
```

---

## 4. hl_position_details

### **表说明**
存储每个快照中的**持仓明细**（每个币种的持仓信息）。

### **表结构**

```sql
CREATE TABLE hl_position_details (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL COMMENT '关联 hl_position_snapshots.id',
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    szi DECIMAL(20, 8) NOT NULL COMMENT '持仓数量(正=多,负=空)',
    entry_px DECIMAL(20, 6) NOT NULL COMMENT '开仓均价',
    position_value DECIMAL(20, 6) NOT NULL COMMENT '仓位价值',
    unrealized_pnl DECIMAL(20, 6) DEFAULT 0 COMMENT '未实现盈亏',
    return_on_equity DECIMAL(10, 6) DEFAULT 0 COMMENT 'ROE(回报率)',
    liquidation_px DECIMAL(20, 6) COMMENT '清算价(null=无风险)',
    margin_used DECIMAL(20, 6) COMMENT '占用保证金',
    leverage_type VARCHAR(20) COMMENT '杠杆类型:cross/isolated',
    leverage_value INT COMMENT '实际杠杆倍数',
    max_leverage INT COMMENT '最大允许杠杆',
    cum_funding_all_time DECIMAL(20, 6) COMMENT '历史累计资金费',
    cum_funding_since_open DECIMAL(20, 6) COMMENT '开仓后累计资金费',

    FOREIGN KEY (snapshot_id) REFERENCES hl_position_snapshots(id) ON DELETE CASCADE,
    INDEX idx_snapshot_coin (snapshot_id, coin),
    INDEX idx_coin (coin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持仓明细(每个快照的持仓列表)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 | API 来源 |
|------|------|------|------|----------|
| id | BIGINT | ✅ | 主键 | - |
| snapshot_id | BIGINT | ✅ | 关联快照ID | 外键 |
| coin | VARCHAR(20) | ✅ | 币种 | `position.coin` |
| szi | DECIMAL(20,8) | ✅ | 持仓数量（正=多，负=空） | `position.szi` |
| entry_px | DECIMAL(20,6) | ✅ | 开仓均价 | `position.entryPx` |
| position_value | DECIMAL(20,6) | ❌ | 仓位价值 | `position.positionValue` |
| unrealized_pnl | DECIMAL(20,6) | ❌ | 未实现盈亏 | `position.unrealizedPnl` |
| return_on_equity | DECIMAL(10,6) | ❌ | 回报率 (ROE) | `position.returnOnEquity` |
| liquidation_px | DECIMAL(20,6) | ❌ | 清算价（null=无风险） | `position.liquidationPx` |
| margin_used | DECIMAL(20,6) | ❌ | 占用保证金 | `position.marginUsed` |
| leverage_type | VARCHAR(20) | ❌ | 杠杆类型 | `position.leverage.type` |
| leverage_value | INT | ❌ | 实际杠杆倍数 | `position.leverage.value` |
| max_leverage | INT | ❌ | 最大允许杠杆 | `position.maxLeverage` |
| cum_funding_all_time | DECIMAL(20,6) | ❌ | 历史累计资金费 | `position.cumFunding.allTime` |
| cum_funding_since_open | DECIMAL(20,6) | ❌ | 开仓后累计资金费 | `position.cumFunding.sinceOpen` |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | 主键 |
| FOREIGN KEY | snapshot_id | 外键 | 关联快照表 |
| idx_snapshot_coin | snapshot_id, coin | 普通 | 按快照+币种查询 |
| idx_coin | coin | 普通 | 按币种统计 |

### **关联关系**

```
hl_position_snapshots (1) ←→ (N) hl_position_details
一个快照包含多个持仓明细（N = 持仓币种数量）
```

### **使用示例**

```sql
-- 查看最新快照的所有持仓
SELECT 
    d.coin,
    d.szi,
    d.entry_px,
    d.unrealized_pnl,
    d.leverage_type,
    d.leverage_value
FROM hl_position_details d
JOIN hl_position_snapshots s ON d.snapshot_id = s.id
WHERE s.address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872'
  AND s.snapshot_time = (
      SELECT MAX(snapshot_time) 
      FROM hl_position_snapshots 
      WHERE address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872'
  );

-- 查看某币种的持仓历史
SELECT 
    FROM_UNIXTIME(s.snapshot_time/1000) as time,
    d.szi,
    d.unrealized_pnl,
    d.leverage_value
FROM hl_position_details d
JOIN hl_position_snapshots s ON d.snapshot_id = s.id
WHERE s.address = '0x...'
  AND d.coin = 'ETH'
ORDER BY s.snapshot_time ASC;

-- 统计各币种的平均盈亏
SELECT 
    d.coin,
    COUNT(DISTINCT s.id) as snapshot_count,
    AVG(d.unrealized_pnl) as avg_pnl,
    MIN(d.unrealized_pnl) as min_pnl,
    MAX(d.unrealized_pnl) as max_pnl
FROM hl_position_details d
JOIN hl_position_snapshots s ON d.snapshot_id = s.id
WHERE s.address = '0x...'
GROUP BY d.coin;
```

---

## 🔄 数据流

```
API 采集
   │
   ├── userFills / userFillsByTime
   │      ↓
   │   hl_fills（原始成交数据）
   │      ↓
   │   v_order_summary（订单汇总视图）
   │
   └── clearinghouseState (user_state)
          ↓
       hl_position_snapshots（账户快照）
          ↓
       hl_position_details（持仓明细）
          ↓
       特征计算 & 分析
```

---

## 📝 维护日志

### 2026-04-07
- ✅ 创建 `hl_address_list` 表
- ✅ 创建 `hl_fills` 表（含完整字段）
- ✅ 添加 `tid`, `oid`, `start_position`, `crossed`, `fee_token`, `twap_id` 字段
- ✅ 创建 `v_order_summary` 视图
- ✅ 修复 `end_position` 计算逻辑

---

## 📚 相关文档

- [API 文档](./HYPERLIQUID_API.md)
- [字段详解](./FILL_FIELDS.md)
- [时区策略](./TIMEZONE_POLICY.md)

---

**最后更新**: 2026-04-07
