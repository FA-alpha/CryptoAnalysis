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

## 🔄 数据流

```
API 采集
   ↓
hl_fills（原始成交数据）
   ↓
v_order_summary（订单汇总视图）
   ↓
分析 & 统计
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
