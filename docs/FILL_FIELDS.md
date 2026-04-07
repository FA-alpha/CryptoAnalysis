# Hyperliquid Fill 字段完整说明

## 📋 API 返回示例（真实数据）

```json
{
  "coin": "ETH",
  "px": "2096.8",
  "sz": "0.01",
  "side": "B",
  "time": 1775543005352,
  "startPosition": "9500.0",
  "dir": "Open Long",
  "closedPnl": "0.0",
  "hash": "0xc6e3ad541b820610c85d043894ed0a02019e0039b68524e26aac58a6da85dffb",
  "oid": 372793001458,
  "crossed": true,
  "fee": "0.00629",
  "tid": 1084573600026477,
  "feeToken": "USDC",
  "twapId": null
}
```

---

## 📖 字段详解

### **基本信息**

| 字段 | 类型 | 必需 | 说明 | 示例值 |
|------|------|------|------|--------|
| **coin** | string | ✅ | 交易币种 | `"ETH"`, `"BTC"`, `"SOL"`, `"HYPE"` |
| **px** | string | ✅ | 成交价格（字符串） | `"2096.8"` |
| **sz** | string | ✅ | 成交数量（字符串） | `"0.01"` |
| **time** | number | ✅ | 成交时间戳（**毫秒**） | `1775543005352` |

**注意**：
- `px` 和 `sz` 是字符串类型，存储到数据库时需要转换为 `DECIMAL`
- `time` 是毫秒时间戳，转换为日期：`datetime.fromtimestamp(time / 1000)`

---

### **订单相关**

| 字段 | 类型 | 必需 | 说明 | 示例值 |
|------|------|------|------|--------|
| **tid** | number | ✅ | **成交ID（唯一标识）** ⭐ | `1084573600026477` |
| **oid** | number | ✅ | 订单ID | `372793001458` |
| **hash** | string | ✅ | 订单哈希 | `"0xc6e3ad541b820610..."` |
| **twapId** | string/null | ❌ | TWAP订单ID | `null` |

**重要区别**：

```
订单 372793001458 被拆成 5 笔成交：
  ├─ tid: 28059324263109    (成交1)
  ├─ tid: 449746928007068   (成交2)
  ├─ tid: 648709636200215   (成交3)
  ├─ tid: 954770577116485   (成交4)
  └─ tid: 1084573600026477  (成交5)

共享相同的 oid 和 hash，但每笔有唯一的 tid
```

**数据库唯一键**：
- ❌ **不能用 hash**：会丢失同一订单的其他成交
- ✅ **必须用 tid**：每笔成交都有唯一 tid

---

### **方向与操作**

| 字段 | 类型 | 必需 | 说明 | 可能值 |
|------|------|------|------|--------|
| **dir** | string | ✅ | 操作方向 | `"Open Long"`, `"Close Long"`, `"Open Short"`, `"Close Short"`, `"Liquidation"` |
| **side** | string | ✅ | 主动方向 | `"B"` (买入主动), `"A"` (卖出主动) |
| **startPosition** | string | ✅ | 成交前持仓（字符串） | `"9500.0"` |

**dir 字段说明**：

| 值 | 含义 | 说明 |
|----|------|------|
| `Open Long` | 开仓做多 | 买入建仓 |
| `Close Long` | 平仓做多 | 卖出平仓（此时 closedPnl 有值） |
| `Open Short` | 开仓做空 | 卖出建仓 |
| `Close Short` | 平仓做空 | 买入平仓（此时 closedPnl 有值） |
| `Liquidation` | 清算/爆仓 | 强制平仓 |

**side 字段说明**：

| 值 | 含义 | 说明 |
|----|------|------|
| `B` | 买入主动 | 用户主动买入（吃卖单） |
| `A` | 卖出主动 | 用户主动卖出（吃买单） |

**startPosition 工作原理**：

```
场景：用户持有 100 ETH 多单

操作1: 开多 10 ETH
  startPosition = "100.0"    (成交前持仓)
  成交后持仓 = 110 ETH

操作2: 开多 5 ETH
  startPosition = "110.0"    (成交前持仓)
  成交后持仓 = 115 ETH

操作3: 平多 20 ETH
  startPosition = "115.0"    (成交前持仓)
  成交后持仓 = 95 ETH

操作4: 开空 50 ETH
  startPosition = "95.0"     (成交前持仓)
  成交后持仓 = 45 ETH (多空混合)
```

**用途**：
- 判断是首次开仓（startPosition ≈ 0）还是加仓
- 追踪持仓变化轨迹
- 计算成交后持仓：`成交后 = startPosition ± sz`

---

### **盈亏与费用**

| 字段 | 类型 | 必需 | 说明 | 示例值 |
|------|------|------|------|--------|
| **closedPnl** | string | ✅ | 已实现盈亏（字符串） | `"0.0"`, `"22.147968"`, `"-15.5"` |
| **fee** | string | ✅ | 手续费（字符串） | `"0.00629"` |
| **feeToken** | string | ✅ | 手续费币种 | `"USDC"` |

**closedPnl 说明**：

| 操作类型 | closedPnl 值 | 说明 |
|----------|-------------|------|
| 开仓 (Open) | `"0.0"` | 开仓时没有盈亏 |
| 平仓 (Close) - 盈利 | `> 0` | 如 `"22.147968"` |
| 平仓 (Close) - 亏损 | `< 0` | 如 `"-15.5"` |

**计算胜率**：
```sql
SELECT 
    COUNT(*) as total_closes,
    SUM(CASE WHEN CAST(closedPnl AS DECIMAL) > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN CAST(closedPnl AS DECIMAL) > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
FROM hl_fills 
WHERE dir LIKE 'Close%' AND address = '0x...';
```

**注意**：计算胜率时只统计平仓记录（`dir LIKE 'Close%'`），不包括开仓。

---

### **杠杆与保证金**

| 字段 | 类型 | 必需 | 说明 | 可能值 |
|------|------|------|------|--------|
| **crossed** | boolean | ✅ | 是否全仓模式 | `true`, `false` |

**crossed 字段详解**：

| 值 | 名称 | 说明 | 风险 | 优势 |
|----|------|------|------|------|
| `true` | **全仓模式** (Cross Margin) | 所有持仓共享账户余额作为保证金 | 一个币爆仓 → 全部清算 | 资金利用率高，不易爆仓 |
| `false` | **逐仓模式** (Isolated Margin) | 每个持仓独立分配保证金 | 单个币爆仓 → 只清算该仓位 | 风险隔离，其他仓位不受影响 |

**示例对比**：

### 全仓模式 (crossed = true)
```
账户总资金: 10,000 USDC
├─ BTC 持仓占用: 3,000 USDC
├─ ETH 持仓占用: 2,000 USDC
└─ 可用余额: 5,000 USDC

如果 BTC 亏损 3,500 USDC：
✅ 可以动用 ETH 的保证金补充
✅ 账户不会立即爆仓
```

### 逐仓模式 (crossed = false)
```
账户总资金: 10,000 USDC
├─ BTC 分配: 1,000 USDC (独立)
├─ ETH 分配: 500 USDC (独立)
└─ 未使用: 8,500 USDC

如果 BTC 亏损 1,100 USDC：
❌ 只能用分配的 1,000 USDC
✅ BTC 爆仓，但 ETH 和剩余资金不受影响
```

---

## 🗄️ 数据库存储建议

### **表结构**

```sql
CREATE TABLE hl_fills (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  address VARCHAR(66) NOT NULL,
  coin VARCHAR(20) NOT NULL,
  sz DECIMAL(20,8) NOT NULL,
  px DECIMAL(20,6) NOT NULL,
  dir VARCHAR(20) NOT NULL,
  closed_pnl DECIMAL(20,6) DEFAULT 0,
  fee DECIMAL(20,6) DEFAULT 0,
  fee_token VARCHAR(10) DEFAULT 'USDC',
  time BIGINT NOT NULL COMMENT '时间戳（毫秒）',
  hash VARCHAR(100) NOT NULL,
  tid BIGINT NOT NULL COMMENT '成交ID（唯一键）',
  oid BIGINT NOT NULL,
  twap_id VARCHAR(100),
  side VARCHAR(5),
  start_position DECIMAL(20,8),
  crossed BOOLEAN DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE KEY uk_tid (tid),                        -- ⭐ 唯一键
  INDEX idx_address_time (address, time DESC),
  INDEX idx_hash (hash),
  INDEX idx_oid (oid),
  INDEX idx_coin (coin),
  INDEX idx_dir (dir)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### **字段映射**

| API 字段 | 数据库字段 | 类型转换 | 示例 |
|----------|-----------|----------|------|
| coin | coin | 直接存储 | `"ETH"` |
| px | px | `DECIMAL(20,6)` | `"2096.8"` → `2096.800000` |
| sz | sz | `DECIMAL(20,8)` | `"0.01"` → `0.01000000` |
| dir | dir | 直接存储 | `"Open Long"` |
| closedPnl | closed_pnl | `DECIMAL(20,6)` | `"0.0"` → `0.000000` |
| fee | fee | `DECIMAL(20,6)` | `"0.00629"` → `0.006290` |
| feeToken | fee_token | 直接存储 | `"USDC"` |
| time | time | `BIGINT` | `1775543005352` |
| hash | hash | 直接存储 | `"0xc6e3ad..."` |
| **tid** | **tid** | `BIGINT` | `1084573600026477` |
| oid | oid | `BIGINT` | `372793001458` |
| twapId | twap_id | 直接存储（可为 NULL） | `null` |
| side | side | 直接存储 | `"B"` |
| startPosition | start_position | `DECIMAL(20,8)` | `"9500.0"` → `9500.00000000` |
| crossed | crossed | `BOOLEAN` | `true` → `1`, `false` → `0` |

### **Python 插入示例**

```python
from decimal import Decimal

def save_fill(fill: dict):
    sql = '''
        INSERT IGNORE INTO hl_fills 
        (address, coin, sz, px, dir, closed_pnl, fee, fee_token, 
         time, hash, tid, oid, twap_id, side, start_position, crossed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    '''
    
    values = (
        address,
        fill['coin'],
        Decimal(fill['sz']),                    # 字符串 → DECIMAL
        Decimal(fill['px']),                    # 字符串 → DECIMAL
        fill['dir'],
        Decimal(fill['closedPnl']),             # 字符串 → DECIMAL
        Decimal(fill['fee']),                   # 字符串 → DECIMAL
        fill['feeToken'],
        fill['time'],                           # 保持 BIGINT
        fill['hash'],
        fill['tid'],                            # 保持 BIGINT
        fill['oid'],                            # 保持 BIGINT
        fill.get('twapId'),                     # 可能为 null
        fill['side'],
        Decimal(fill['startPosition']),         # 字符串 → DECIMAL
        fill['crossed']                         # 保持 BOOLEAN
    )
    
    cursor.execute(sql, values)
```

---

## 📊 常用查询

### **1. 查询某个订单的所有成交**

```sql
SELECT tid, sz, px, fee, start_position
FROM hl_fills 
WHERE oid = 372793001458 
ORDER BY tid;
```

### **2. 计算订单总数量和总手续费**

```sql
SELECT 
    oid,
    COUNT(*) as fill_count,
    SUM(sz) as total_sz,
    SUM(fee) as total_fee
FROM hl_fills 
WHERE oid = 372793001458 
GROUP BY oid;
```

### **3. 统计地址的总盈亏**

```sql
SELECT 
    SUM(closed_pnl) - SUM(fee) as net_pnl
FROM hl_fills 
WHERE address = '0x020ca66c30bec2c4fe3861a94e4db4a498a35872';
```

### **4. 计算胜率**

```sql
SELECT 
    COUNT(*) as total_closes,
    SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_rate_pct
FROM hl_fills 
WHERE address = '0x...' AND dir LIKE 'Close%';
```

### **5. 查找被拆分最多的订单**

```sql
SELECT 
    oid,
    hash,
    coin,
    dir,
    COUNT(*) as fill_count,
    SUM(sz) as total_sz
FROM hl_fills 
GROUP BY oid, hash, coin, dir
HAVING fill_count > 10
ORDER BY fill_count DESC;
```

---

## ⚠️ 重要注意事项

### **1. tid 是唯一标识**
- 同一订单可能有多笔成交（多个 tid）
- **必须用 tid 作为唯一键**，不能用 hash
- 使用 `INSERT IGNORE` 防止重复插入

### **2. 字符串转数值**
- API 返回的 `px`, `sz`, `closedPnl`, `fee`, `startPosition` 都是字符串
- 存储到数据库时需要转换为 `DECIMAL` 类型

### **3. 时间戳单位是毫秒**
- `time` 字段是毫秒时间戳，不是秒
- 转换为日期：`datetime.fromtimestamp(time / 1000)`

### **4. closedPnl 只在平仓时有值**
- 开仓时 `closedPnl = "0.0"`
- 计算胜率时要过滤：`WHERE dir LIKE 'Close%'`

### **5. 全仓 vs 逐仓**
- `crossed = true`：全仓（风险集中，利用率高）
- `crossed = false`：逐仓（风险隔离，更安全）

---

## 📚 相关文档

- [数据库设计文档](./DATABASE.md)
- [API 接口文档](./HYPERLIQUID_API.md)
- [时区策略](./TIMEZONE_POLICY.md)

---

**最后更新**: 2026-04-07
