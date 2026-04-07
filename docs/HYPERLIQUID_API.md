# Hyperliquid API 完整文档

## 基础信息

**接口地址**: `https://api.hyperliquid.xyz/info`  
**请求方法**: `POST`  
**Content-Type**: `application/json`  
**认证**: 无需 API Key（公开接口）

---

## 📋 目录

1. [用户交易历史 (userFills)](#1-用户交易历史-userfills)
2. [按时间获取交易 (userFillsByTime)](#2-按时间获取交易-userfillsbytime)
3. [用户账户状态 (clearinghouseState)](#3-用户账户状态-clearinghousestate)
4. [用户资金费率 (userFunding)](#4-用户资金费率-userfunding)
5. [市场数据 (metaAndAssetCtxs)](#5-市场数据-metaandassetctxs)
6. [其他接口](#6-其他接口)

---

## 1. 用户交易历史 (userFills)

### **用途**
获取用户的**最近交易历史**（默认最多 2000 条）

### **请求示例**

```bash
curl -X POST https://api.hyperliquid.xyz/info \
  -H "Content-Type: application/json" \
  -d '{
    "type": "userFills",
    "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872"
  }'
```

```json
{
  "type": "userFills",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872"
}
```

### **请求参数**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| type | string | ✅ | 固定值 `"userFills"` |
| user | string | ✅ | 钱包地址（42 字符，0x 开头） |

### **响应示例**

```json
[
  {
    "coin": "ETH",
    "px": "2096.8",
    "sz": "12.755",
    "side": "B",
    "time": 1775543005352,
    "startPosition": "9512.245",
    "dir": "Open Long",
    "closedPnl": "0.0",
    "hash": "0xc6e3ad541b820610c85d043894ed0a02019e0039b68524e26aac58a6da85dffb",
    "oid": 372793001458,
    "crossed": true,
    "fee": "8.023405",
    "tid": 449746928007068,
    "feeToken": "USDC",
    "twapId": null
  },
  ...
]
```

### **响应字段说明**

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| coin | string | 交易币种 | `"ETH"` |
| px | string | 成交价格 | `"2096.8"` |
| sz | string | 成交数量 | `"12.755"` |
| side | string | 主动方向：B=买入，A=卖出 | `"B"` |
| time | number | 时间戳（毫秒） | `1775543005352` |
| startPosition | string | 成交前持仓 | `"9512.245"` |
| dir | string | 操作方向 | `"Open Long"`, `"Close Long"`, `"Open Short"`, `"Close Short"`, `"Liquidation"` |
| closedPnl | string | 已实现盈亏（平仓时才有值） | `"22.147968"` |
| hash | string | 订单哈希 | `"0xc6e3ad..."` |
| oid | number | 订单 ID | `372793001458` |
| crossed | boolean | 是否全仓模式 | `true` |
| fee | string | 手续费 | `"8.023405"` |
| tid | number | **成交 ID（唯一标识）** | `449746928007068` |
| feeToken | string | 手续费币种 | `"USDC"` |
| twapId | string/null | TWAP 订单 ID | `null` |

### **特殊说明**

1. **一个订单可能有多笔成交**
   - 同一个 `oid` 和 `hash` 可能有多个 `tid`
   - 必须用 `tid` 作为唯一标识，避免数据丢失

2. **数据量限制**
   - 最多返回最近 2000 条成交
   - 如需更多历史数据，使用 `userFillsByTime`

---

## 2. 按时间获取交易 (userFillsByTime)

### **用途**
获取**指定时间范围**内的交易历史（支持增量更新）

### **请求示例**

```bash
curl -X POST https://api.hyperliquid.xyz/info \
  -H "Content-Type: application/json" \
  -d '{
    "type": "userFillsByTime",
    "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
    "startTime": 1770877800000
  }'
```

```json
{
  "type": "userFillsByTime",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
  "startTime": 1770877800000,
  "endTime": 1775543005352
}
```

### **请求参数**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| type | string | ✅ | 固定值 `"userFillsByTime"` |
| user | string | ✅ | 钱包地址 |
| startTime | number | ✅ | 起始时间戳（**毫秒**） |
| endTime | number | ❌ | 结束时间戳（可选，默认到当前） |

### **响应格式**
与 `userFills` 相同（见上文）

### **使用场景**

#### **场景 1：首次全量获取**
```json
{
  "type": "userFillsByTime",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
  "startTime": 1770000000000
}
```
获取从 2026-02-01 开始的所有交易

#### **场景 2：增量更新**
```python
# 1. 从数据库获取最新时间
last_time = db.query("SELECT MAX(time) FROM hl_fills WHERE address = ?")

# 2. 从上次时间 +1ms 开始获取
new_fills = api.request({
    "type": "userFillsByTime",
    "user": "0x...",
    "startTime": last_time + 1  # 避免重复
})
```

### **时间戳转换**

```python
from datetime import datetime

# 人类可读 → 毫秒时间戳
dt = datetime(2026, 2, 12, 16, 0, 0)
timestamp_ms = int(dt.timestamp() * 1000)
# 1770877800000

# 毫秒时间戳 → 人类可读
dt = datetime.fromtimestamp(1770877800000 / 1000)
# 2026-02-12 16:00:00
```

---

## 3. 用户账户状态 (clearinghouseState)

### **用途**
获取用户的**当前持仓、账户余额、保证金使用情况**

### **请求示例**

```json
{
  "type": "clearinghouseState",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872"
}
```

### **响应示例**

```json
{
  "assetPositions": [
    {
      "position": {
        "coin": "ETH",
        "entryPx": "2100.5",
        "szi": "10.5",
        "leverage": {
          "type": "cross",
          "value": 20
        },
        "liquidationPx": "1500.2",
        "marginUsed": "5000.0",
        "positionValue": "22050.25",
        "unrealizedPnl": "500.0",
        "returnOnEquity": "0.1"
      },
      "type": "oneWay"
    }
  ],
  "crossMarginSummary": {
    "accountValue": "50000.0",
    "totalMarginUsed": "10000.0",
    "totalNtlPos": "22050.25",
    "totalRawUsd": "50000.0"
  },
  "marginSummary": {
    "accountValue": "50000.0",
    "totalMarginUsed": "10000.0"
  },
  "withdrawable": "40000.0",
  "time": 1775543005352
}
```

### **响应字段说明**

#### **持仓信息 (assetPositions)**

| 字段 | 说明 |
|------|------|
| coin | 币种 |
| entryPx | 开仓均价 |
| szi | 持仓数量（正=多，负=空） |
| leverage.type | 杠杆类型：`cross`（全仓）/ `isolated`（逐仓） |
| leverage.value | 杠杆倍数 |
| liquidationPx | 清算价格 |
| marginUsed | 已用保证金 |
| positionValue | 仓位价值 |
| unrealizedPnl | 未实现盈亏 |
| returnOnEquity | 回报率 (ROE) |

#### **账户汇总 (crossMarginSummary)**

| 字段 | 说明 |
|------|------|
| accountValue | 账户总价值 |
| totalMarginUsed | 总已用保证金 |
| totalNtlPos | 总名义持仓价值 |
| withdrawable | 可提现金额 |

---

## 4. 用户资金费率 (userFunding)

### **用途**
获取用户的**资金费率支付/收取历史**

### **请求示例**

```json
{
  "type": "userFunding",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
  "startTime": 1770877800000
}
```

### **响应示例**

```json
[
  {
    "coin": "ETH",
    "fundingRate": "0.0001",
    "szi": "100.5",
    "usdc": "-21.05",
    "nSamples": 8,
    "time": 1775543005352
  }
]
```

### **字段说明**

| 字段 | 说明 |
|------|------|
| coin | 币种 |
| fundingRate | 资金费率 |
| szi | 持仓数量 |
| usdc | 支付/收取金额（负数=支付） |
| time | 时间戳（毫秒） |

---

## 5. 市场数据 (metaAndAssetCtxs)

### **用途**
获取**所有交易对的元数据和当前市场数据**

### **请求示例**

```json
{
  "type": "metaAndAssetCtxs"
}
```

### **响应示例**

```json
[
  {
    "name": "ETH",
    "szDecimals": 4,
    "maxLeverage": 50,
    "onlyIsolated": false,
    "ctx": {
      "funding": "0.0001",
      "openInterest": "1234567.89",
      "prevDayPx": "2050.0",
      "dayNtlVlm": "50000000.0",
      "premium": "0.5",
      "oraclePx": "2100.0",
      "markPx": "2100.5",
      "midPx": "2100.3"
    }
  }
]
```

---

## 6. 其他接口

### **6.1 获取用户挂单 (openOrders)**

```json
{
  "type": "openOrders",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872"
}
```

### **6.2 获取订单簿 (l2Book)**

```json
{
  "type": "l2Book",
  "coin": "ETH"
}
```

### **6.3 获取 K 线数据 (candleSnapshot)**

```json
{
  "type": "candleSnapshot",
  "coin": "ETH",
  "interval": "1h",
  "startTime": 1770877800000,
  "endTime": 1775543005352
}
```

---

## 📊 数据库存储建议

### **hl_fills 表结构**

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
  time BIGINT NOT NULL COMMENT '时间戳（毫秒）',
  hash VARCHAR(100) NOT NULL COMMENT '订单哈希',
  tid BIGINT NOT NULL COMMENT '成交ID（唯一）',
  oid BIGINT NOT NULL COMMENT '订单ID',
  side VARCHAR(5),
  start_position DECIMAL(20,8) COMMENT '成交前持仓',
  crossed BOOLEAN DEFAULT TRUE COMMENT '是否全仓',
  fee_token VARCHAR(10) DEFAULT 'USDC',
  created_at DATETIME NOT NULL COMMENT '入库时间（北京时间）',
  
  UNIQUE KEY uk_tid (tid),
  INDEX idx_address_time (address, time DESC),
  INDEX idx_hash (hash),
  INDEX idx_oid (oid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### **字段映射**

| API 字段 | 数据库字段 | 类型 | 说明 |
|----------|-----------|------|------|
| coin | coin | VARCHAR(20) | 直接存储 |
| px | px | DECIMAL(20,6) | 价格 |
| sz | sz | DECIMAL(20,8) | 数量 |
| dir | dir | VARCHAR(20) | 方向 |
| closedPnl | closed_pnl | DECIMAL(20,6) | 已实现盈亏 |
| fee | fee | DECIMAL(20,6) | 手续费 |
| time | time | BIGINT | 时间戳（毫秒） |
| hash | hash | VARCHAR(100) | 订单哈希 |
| **tid** | **tid** | **BIGINT** | **唯一键** ⭐ |
| oid | oid | BIGINT | 订单ID |
| side | side | VARCHAR(5) | B/A |
| startPosition | start_position | DECIMAL(20,8) | 成交前持仓 |
| crossed | crossed | BOOLEAN | 是否全仓 |
| feeToken | fee_token | VARCHAR(10) | 手续费币种 |

---

## 🔄 数据采集策略

### **首次采集（全量）**

```python
# 使用 userFills（快速，最多 2000 条）
response = requests.post(
    "https://api.hyperliquid.xyz/info",
    json={
        "type": "userFills",
        "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872"
    }
)
fills = response.json()
```

### **增量更新（推荐）**

```python
# 1. 获取数据库中最新时间
last_time = db.query("SELECT MAX(time) FROM hl_fills WHERE address = ?")

# 2. 从上次时间 +1ms 开始
response = requests.post(
    "https://api.hyperliquid.xyz/info",
    json={
        "type": "userFillsByTime",
        "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
        "startTime": last_time + 1  # 避免重复
    }
)
new_fills = response.json()

# 3. 批量插入（使用 INSERT IGNORE 去重）
db.executemany(
    "INSERT IGNORE INTO hl_fills (...) VALUES (...)",
    new_fills
)
```

---

## ⚠️ 注意事项

1. **tid 是唯一标识**
   - 同一订单可能有多笔成交（多个 tid）
   - 必须用 tid 作为唯一键，不能用 hash

2. **时间戳单位是毫秒**
   - 不是秒！需要除以 1000 转换

3. **closedPnl 只在平仓时有值**
   - 开仓时 closedPnl = 0
   - 计算胜率时要过滤开仓记录

4. **增量更新从 last_time + 1 开始**
   - 避免获取到重复的最后一条

5. **全仓 vs 逐仓**
   - crossed = true：全仓（风险高，利用率高）
   - crossed = false：逐仓（风险隔离）

---

## 📚 相关文档

- [Hyperliquid 官方文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- [字段详解](./FILL_FIELDS.md)
- [时区策略](./TIMEZONE_POLICY.md)

---

**最后更新**: 2026-04-07
