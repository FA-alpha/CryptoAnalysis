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

### **响应示例（真实数据）**

```json
{
  "marginSummary": {
    "accountValue": "1.020216",
    "totalNtlPos": "0.722728",
    "totalRawUsd": "0.311248",
    "totalMarginUsed": "0.072272"
  },
  "crossMarginSummary": {
    "accountValue": "1.020216",
    "totalNtlPos": "0.722728",
    "totalRawUsd": "0.311248",
    "totalMarginUsed": "0.072272"
  },
  "crossMaintenanceMarginUsed": "0.036136",
  "withdrawable": "0.947944",
  "assetPositions": [
    {
      "type": "oneWay",
      "position": {
        "coin": "FARTCOIN",
        "szi": "4.2",
        "leverage": {
          "type": "cross",
          "value": 10
        },
        "entryPx": "0.17468",
        "positionValue": "0.715848",
        "unrealizedPnl": "-0.017808",
        "returnOnEquity": "-0.2427295626",
        "liquidationPx": null,
        "marginUsed": "0.071584",
        "maxLeverage": 10,
        "cumFunding": {
          "allTime": "-20239.799592",
          "sinceOpen": "0.001983",
          "sinceChange": "0.001983"
        }
      }
    },
    {
      "type": "oneWay",
      "position": {
        "coin": "PUMP",
        "szi": "-4.0",
        "leverage": {
          "type": "cross",
          "value": 10
        },
        "entryPx": "0.001866",
        "positionValue": "0.00688",
        "unrealizedPnl": "0.000585",
        "returnOnEquity": "0.7836570663",
        "liquidationPx": "0.2360247619",
        "marginUsed": "0.000688",
        "maxLeverage": 10,
        "cumFunding": {
          "allTime": "-2662.879366",
          "sinceOpen": "-2662.879366",
          "sinceChange": "0.0"
        }
      }
    }
  ],
  "time": 1775552898004
}
```

### **响应字段说明**

#### **持仓信息 (assetPositions)**

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| **coin** | string | 币种 | `"FARTCOIN"`, `"PUMP"` |
| **szi** | string | 持仓数量（正=多，负=空） | `"4.2"`, `"-4.0"` |
| **entryPx** | string | 开仓均价 | `"0.17468"` |
| **positionValue** | string | 仓位价值 | `"0.715848"` |
| **unrealizedPnl** | string | 未实现盈亏 | `"-0.017808"`, `"0.000585"` |
| **returnOnEquity** | string | 回报率 (ROE) | `"-0.2427295626"` |
| **liquidationPx** | string/null | 清算价格（null=无风险） | `"0.2360247619"`, `null` |
| **marginUsed** | string | 已用保证金 | `"0.071584"` |
| **maxLeverage** | number | 最大允许杠杆 | `10` |
| **leverage.type** | string | 杠杆类型 | `"cross"`（全仓）, `"isolated"`（逐仓） |
| **leverage.value** | number | 实际杠杆倍数 | `10` |
| **cumFunding.allTime** | string | 历史累计资金费 | `"-20239.799592"` |
| **cumFunding.sinceOpen** | string | 开仓后累计资金费 | `"0.001983"` |
| **cumFunding.sinceChange** | string | 上次调整后的资金费 | `"0.001983"` |

#### **账户汇总 (marginSummary / crossMarginSummary)**

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| **accountValue** | string | 账户总价值 | `"1.020216"` |
| **totalMarginUsed** | string | 总已用保证金 | `"0.072272"` |
| **totalRawUsd** | string | 钱包余额 / USD 净余额（可能为负）⚠️ | `"0.311248"`, `"-18153503.342439"` |
| **totalNtlPos** | string | 总名义持仓价值 | `"0.722728"` |
| **withdrawable** | string | 可提现金额 | `"0.947944"` |
| **time** | number | 快照时间戳（毫秒） | `1775552898004` |

### **关键字段解释**

#### **totalRawUsd（钱包余额 / USD 净余额）**

**官方定义**：
> The total raw USD value in the user's account. This represents the user's **wallet balance**, which can be negative if they have realized losses exceeding their initial deposits.

**中文翻译**：
> 用户账户中的 USD 总余额。这代表用户的**钱包余额**，如果已实现的亏损超过初始存款，该值可能为负。

**计算公式**：
```
totalRawUsd = 所有存入
            - 所有提现
            + 所有已平仓盈利
            - 所有已平仓亏损
            - 所有手续费
            - 所有资金费率支出
            + 所有资金费率收入

本质：
totalRawUsd = 钱包当前余额（不含未平仓持仓）
```

**为什么会是负数？**

当账户的**历史累计亏损超过初始本金**时，`totalRawUsd` 就会为负数。

**真实案例**：
```
account_value = 1,342,454.16 USDC       -- 当前账户总价值
total_raw_usd = -18,153,503.34 USDC     -- 钱包余额（负数！）
total_ntl_pos = 19,495,957.50 USDC      -- 总名义持仓价值

计算关系：
account_value = total_raw_usd + unrealized_pnl
1,342,454.16 = -18,153,503.34 + 19,495,957.50 ✅
```

**这意味着**：
- 用户**历史累计亏损 1815 万 USDC**（超过初始本金）
- 但通过**当前持仓的未实现盈亏 +1949 万**，账户仍有净值 134 万
- 这是一个**高杠杆、高风险、高收益**的账户

**风险分级**：

| totalRawUsd | 风险等级 | 说明 |
|-------------|----------|------|
| > 0 | 🟢 低风险 | 历史盈利 |
| 0 到 -50% 初始本金 | 🟡 中风险 | 历史小幅亏损 |
| < -50% 初始本金 | 🔴 高风险 | 历史严重亏损，依赖未实现盈亏 |
| **< -1000% 初始本金** | 💀 **极高风险** | **历史亏损超过本金 10 倍以上** |

**建议**：
- ✅ 保留此字段（反映账户真实历史表现）
- ✅ 用于计算**历史累计盈亏**
- ✅ 识别**高风险账户**（反脆弱策略的重要指标）

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

### **6.4 非资金费账本流水 (userNonFundingLedgerUpdates)**

用于获取地址的非资金费账本变动（充值、提现、地址间转账、账户类别划转等）。

```json
{
  "type": "userNonFundingLedgerUpdates",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
  "startTime": 1775600000000,
  "endTime": 1776200000000
}
```

#### 关键字段语义（重点）

- `delta.type`
  - `deposit`：外部 -> Hyper 账户（外部充值）
  - `withdraw`：Hyper 账户 -> 外部（外部提现）
  - `send`：Hyper 内部地址间转账（不是外部充提）
  - `accountClassTransfer`：同地址内 `spot <-> perp` 划转
  - `spotTransfer`：地址间/账户间现货资产划转（内部资金流）
  - `vaultCreate`：创建 vault（结构性事件，可伴随初始投入）
  - `vaultDeposit`：地址 -> vault 申购/存入（内部流出）
  - `vaultWithdraw`：vault -> 地址 赎回/取回（内部流入）
  - `vaultDistribution`：vault 向地址分配收益（内部流入）
  - `vaultLeaderCommission`：vault leader 佣金（费用/分润类事件）
  - `borrowLend`：借贷相关资金变动（内部资金事件）
  - `cStakingTransfer`：cStaking 相关划转（内部资金事件）
  - `accountActivationGas`：账户激活 gas 扣费（费用事件）
- `sourceDex`
  - 资金从哪个账户类型扣出（如 `spot` / `perp`）
- `destinationDex`
  - 资金转入哪个账户类型（可能为空字符串，表示未显式标注）

#### Vault 相关字段（重点）

- `delta.vault`：vault 地址/标识
- `delta.operation`：vault 操作语义（不同事件会有不同取值）
- `delta.requestedUsd`：请求赎回金额（常见于 `vaultWithdraw`）
- `delta.netWithdrawnUsd`：实际净到账金额（常见于 `vaultWithdraw`）
- `delta.commission`：佣金金额（常见于 `vaultLeaderCommission`）
- `delta.closingCost` / `delta.basis`：结算成本/基准相关字段（按事件出现）

> 实务建议：`vaultWithdraw` 优先使用 `netWithdrawnUsd` 作为实际到账金额，`requestedUsd` 作为请求值留存用于对账。

#### 入金/出金判定口径（建议）

1. 外部净流（推荐做主口径）
   - 入金：`type = 'deposit'`
   - 出金：`type = 'withdraw'`
2. 全口径净流（包含内部转账）
   - 外部入/出：同上
   - 内部转入：`type = 'send' AND destination == 被监控地址`
   - 内部转出：`type = 'send' AND user == 被监控地址`

> 建议同时维护两套指标：`external_net_flow`（仅 deposit/withdraw）和 `total_net_flow`（包含 send in/out），避免把平台内部转账与外部真实充提混淆。

#### 数据库 type 分析字典（hl_ledger_updates）

| `type` | 归类 | 对地址资金方向 | 是否计入外部净流 |
|---|---|---|---|
| `deposit` | 外部充提 | 流入 | 是 |
| `withdraw` | 外部充提 | 流出 | 是 |
| `send` | 内部转账 | 取决于 sender/destination | 否 |
| `accountClassTransfer` | 内部划转 | 同地址内部重分配 | 否 |
| `spotTransfer` | 内部划转 | 取决于对手方 | 否 |
| `vaultCreate` | vault 结构事件 | 通常视字段判断 | 否 |
| `vaultDeposit` | vault 申购 | 流出 | 否 |
| `vaultWithdraw` | vault 赎回 | 流入 | 否 |
| `vaultDistribution` | vault 分润 | 流入 | 否 |
| `vaultLeaderCommission` | vault 佣金 | leader 通常流入 | 否 |
| `borrowLend` | 借贷 | 视语义和 token 而定 | 否 |
| `cStakingTransfer` | staking 划转 | 视语义和 token 而定 | 否 |
| `accountActivationGas` | 费用 | 流出 | 否 |

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

6. **账本流水里的 send 不等于外部充值/提现**
   - `send` 是 Hyper 内部地址间转账
   - 外部资金进出以 `deposit/withdraw` 为准
   - 资金分析建议区分外部口径与全口径

---

## 📈 账本净流 SQL 示例（按天）

> 说明：以下 SQL 基于 `hl_ledger_updates`（对应 `scripts/fetch_ledger_updates.py` 的入库表）示例。  
> 如果你的表名不同，请替换为实际表名。

```sql
-- 按天统计：外部入金、外部出金、内部转入、内部转出、外部净流、全口径净流
SELECT
    lu.address,
    DATE(FROM_UNIXTIME(lu.time / 1000)) AS stat_date,

    -- 外部口径（当前表结构：usdc_amount）
    SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_in_usdc,
    SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_out_usdc,

    -- 内部转账口径（send）
    SUM(
        CASE
            WHEN lu.type = 'send' AND LOWER(lu.destination_address) = LOWER(lu.address)
                THEN COALESCE(lu.usdc_value, 0)
            ELSE 0
        END
    ) AS internal_in_usdc,
    SUM(
        CASE
            WHEN lu.type = 'send' AND LOWER(lu.sender_address) = LOWER(lu.address)
                THEN COALESCE(lu.usdc_value, 0)
            ELSE 0
        END
    ) AS internal_out_usdc,

    -- 外部净流（推荐主口径）
    SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
    - SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_net_flow_usdc,

    -- 全口径净流（外部 + 内部）
    (
        SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        + SUM(CASE WHEN lu.type = 'send' AND LOWER(lu.destination_address) = LOWER(lu.address) THEN COALESCE(lu.usdc_value, 0) ELSE 0 END)
    ) - (
        SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        + SUM(CASE WHEN lu.type = 'send' AND LOWER(lu.sender_address) = LOWER(lu.address) THEN COALESCE(lu.usdc_value, 0) ELSE 0 END)
    ) AS total_net_flow_usdc
FROM hl_ledger_updates lu
GROUP BY lu.address, DATE(FROM_UNIXTIME(lu.time / 1000))
ORDER BY stat_date DESC, lu.address;
```

### Vault 资金流 SQL 示例（按天）

> 说明：用于拆分 vault 申购/赎回/分润/佣金四类事件，避免与外部充提混淆。  
> 口径基于 `hl_ledger_updates.type + usdc_amount`，其中 `vaultWithdraw` 建议优先入库净到账金额（`net_withdrawn_usd`）。

```sql
-- 按天统计 vault 四项 + 净额
SELECT
    lu.address,
    DATE(FROM_UNIXTIME(lu.time / 1000)) AS stat_date,

    -- 地址 -> vault（申购/存入）
    SUM(
        CASE
            WHEN lu.type = 'vaultDeposit' THEN COALESCE(lu.usdc_amount, 0)
            ELSE 0
        END
    ) AS vault_deposit_usdc,

    -- vault -> 地址（赎回/取回）
    SUM(
        CASE
            WHEN lu.type = 'vaultWithdraw' THEN COALESCE(lu.usdc_amount, 0)
            ELSE 0
        END
    ) AS vault_withdraw_usdc,

    -- vault 分润（收益分配）
    SUM(
        CASE
            WHEN lu.type = 'vaultDistribution' THEN COALESCE(lu.usdc_amount, 0)
            ELSE 0
        END
    ) AS vault_distribution_usdc,

    -- leader 佣金（费用/分润类）
    SUM(
        CASE
            WHEN lu.type = 'vaultLeaderCommission' THEN COALESCE(lu.usdc_amount, 0)
            ELSE 0
        END
    ) AS vault_leader_commission_usdc,

    -- vault 净流（地址视角）
    -- 正值：地址从 vault 体系净流入；负值：地址净投入 vault
    (
        SUM(CASE WHEN lu.type IN ('vaultWithdraw', 'vaultDistribution') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        - SUM(CASE WHEN lu.type IN ('vaultDeposit', 'vaultLeaderCommission') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
    ) AS vault_net_flow_usdc
FROM hl_ledger_updates lu
GROUP BY lu.address, DATE(FROM_UNIXTIME(lu.time / 1000))
ORDER BY stat_date DESC, lu.address;
```

```sql
-- 可选：按 vault 维度统计（需要表中有 vault_address 列）
SELECT
    lu.address,
    lu.vault_address,
    DATE(FROM_UNIXTIME(lu.time / 1000)) AS stat_date,
    SUM(CASE WHEN lu.type = 'vaultDeposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_deposit_usdc,
    SUM(CASE WHEN lu.type = 'vaultWithdraw' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_withdraw_usdc,
    SUM(CASE WHEN lu.type = 'vaultDistribution' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_distribution_usdc,
    SUM(CASE WHEN lu.type = 'vaultLeaderCommission' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_leader_commission_usdc
FROM hl_ledger_updates lu
WHERE lu.vault_address IS NOT NULL
GROUP BY lu.address, lu.vault_address, DATE(FROM_UNIXTIME(lu.time / 1000))
ORDER BY stat_date DESC, lu.address, lu.vault_address;
```

### 三口径合并报表 SQL（按天）

> 说明：一张报表同时输出 `external_net_flow`、`vault_net_flow`、`total_net_flow`，便于策略层直接消费。  
> 口径约定：  
> - `external_net_flow` = `deposit - withdraw`  
> - `vault_net_flow` = (`vaultWithdraw` + `vaultDistribution`) - (`vaultDeposit` + `vaultLeaderCommission`)  
> - `total_net_flow` = `external_net_flow + internal_net_flow + vault_net_flow`  
> 其中 `internal_net_flow` 来自 `send`（内部转账净流）。

```sql
SELECT
    lu.address,
    DATE(FROM_UNIXTIME(lu.time / 1000)) AS stat_date,

    -- 外部口径
    SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_in_usdc,
    SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_out_usdc,
    SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
    - SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS external_net_flow_usdc,

    -- 内部转账口径（send）
    SUM(
        CASE
            WHEN lu.type = 'send' AND LOWER(lu.destination_address) = LOWER(lu.address)
                THEN COALESCE(lu.usdc_value, 0)
            ELSE 0
        END
    ) AS internal_in_usdc,
    SUM(
        CASE
            WHEN lu.type = 'send' AND LOWER(lu.sender_address) = LOWER(lu.address)
                THEN COALESCE(lu.usdc_value, 0)
            ELSE 0
        END
    ) AS internal_out_usdc,
    SUM(
        CASE
            WHEN lu.type = 'send' AND LOWER(lu.destination_address) = LOWER(lu.address)
                THEN COALESCE(lu.usdc_value, 0)
            WHEN lu.type = 'send' AND LOWER(lu.sender_address) = LOWER(lu.address)
                THEN -COALESCE(lu.usdc_value, 0)
            ELSE 0
        END
    ) AS internal_net_flow_usdc,

    -- vault 口径
    SUM(CASE WHEN lu.type = 'vaultDeposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_deposit_usdc,
    SUM(CASE WHEN lu.type = 'vaultWithdraw' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_withdraw_usdc,
    SUM(CASE WHEN lu.type = 'vaultDistribution' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_distribution_usdc,
    SUM(CASE WHEN lu.type = 'vaultLeaderCommission' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END) AS vault_leader_commission_usdc,
    (
        SUM(CASE WHEN lu.type IN ('vaultWithdraw', 'vaultDistribution') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        - SUM(CASE WHEN lu.type IN ('vaultDeposit', 'vaultLeaderCommission') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
    ) AS vault_net_flow_usdc,

    -- 全口径净流（外部 + 内部 + vault）
    (
        -- external
        SUM(CASE WHEN lu.type = 'deposit' THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        - SUM(CASE WHEN lu.type IN ('withdraw', 'withdrawal') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        -- internal
        + SUM(
            CASE
                WHEN lu.type = 'send' AND LOWER(lu.destination_address) = LOWER(lu.address)
                    THEN COALESCE(lu.usdc_value, 0)
                WHEN lu.type = 'send' AND LOWER(lu.sender_address) = LOWER(lu.address)
                    THEN -COALESCE(lu.usdc_value, 0)
                ELSE 0
            END
        )
        -- vault
        + (
            SUM(CASE WHEN lu.type IN ('vaultWithdraw', 'vaultDistribution') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
            - SUM(CASE WHEN lu.type IN ('vaultDeposit', 'vaultLeaderCommission') THEN COALESCE(lu.usdc_amount, 0) ELSE 0 END)
        )
    ) AS total_net_flow_usdc
FROM hl_ledger_updates lu
GROUP BY lu.address, DATE(FROM_UNIXTIME(lu.time / 1000))
ORDER BY stat_date DESC, lu.address;
```

---

## 💾 clearinghouseState 数据库存储

### **表 1：hl_position_snapshots（账户级别快照）**

```sql
CREATE TABLE hl_position_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL,
    snapshot_time BIGINT NOT NULL,              -- time
    account_value DECIMAL(20,6) NOT NULL,       -- marginSummary.accountValue
    total_margin_used DECIMAL(20,6) NOT NULL,   -- marginSummary.totalMarginUsed
    total_raw_usd DECIMAL(20,6),                -- marginSummary.totalRawUsd
    total_ntl_pos DECIMAL(20,6),                -- marginSummary.totalNtlPos
    withdrawable DECIMAL(20,6),                 -- withdrawable
    created_at DATETIME NOT NULL,
    
    UNIQUE KEY uk_address_time (address, snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### **表 2：hl_position_details（持仓明细）**

```sql
CREATE TABLE hl_position_details (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL,                -- 外键关联 hl_position_snapshots.id
    coin VARCHAR(20) NOT NULL,                  -- position.coin
    szi DECIMAL(20,8) NOT NULL,                 -- position.szi
    entry_px DECIMAL(20,6) NOT NULL,            -- position.entryPx
    position_value DECIMAL(20,6),               -- position.positionValue
    unrealized_pnl DECIMAL(20,6),               -- position.unrealizedPnl
    return_on_equity DECIMAL(10,6),             -- position.returnOnEquity
    liquidation_px DECIMAL(20,6),               -- position.liquidationPx
    margin_used DECIMAL(20,6),                  -- position.marginUsed
    leverage_type VARCHAR(20),                  -- position.leverage.type
    leverage_value INT,                         -- position.leverage.value
    max_leverage INT,                           -- position.maxLeverage
    cum_funding_all_time DECIMAL(20,6),         -- position.cumFunding.allTime
    cum_funding_since_open DECIMAL(20,6),       -- position.cumFunding.sinceOpen
    
    FOREIGN KEY (snapshot_id) REFERENCES hl_position_snapshots(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### **字段映射**

#### **hl_position_snapshots**

| API 字段 | 数据库字段 | 类型转换 |
|----------|-----------|----------|
| time | snapshot_time | BIGINT（保持毫秒） |
| marginSummary.accountValue | account_value | DECIMAL(20,6) |
| marginSummary.totalMarginUsed | total_margin_used | DECIMAL(20,6) |
| marginSummary.totalRawUsd | total_raw_usd | DECIMAL(20,6) |
| marginSummary.totalNtlPos | total_ntl_pos | DECIMAL(20,6) |
| withdrawable | withdrawable | DECIMAL(20,6) |

#### **hl_position_details**

| API 字段 | 数据库字段 | 类型转换 |
|----------|-----------|----------|
| position.coin | coin | VARCHAR(20) |
| position.szi | szi | DECIMAL(20,8) |
| position.entryPx | entry_px | DECIMAL(20,6) |
| position.positionValue | position_value | DECIMAL(20,6) |
| position.unrealizedPnl | unrealized_pnl | DECIMAL(20,6) |
| position.returnOnEquity | return_on_equity | DECIMAL(10,6) |
| position.liquidationPx | liquidation_px | DECIMAL(20,6) (null 允许) |
| position.marginUsed | margin_used | DECIMAL(20,6) |
| position.leverage.type | leverage_type | VARCHAR(20) |
| position.leverage.value | leverage_value | INT |
| position.maxLeverage | max_leverage | INT |
| position.cumFunding.allTime | cum_funding_all_time | DECIMAL(20,6) |
| position.cumFunding.sinceOpen | cum_funding_since_open | DECIMAL(20,6) |

### **数据采集策略**

#### **时间序列快照**
- 每次调用 API 插入**一条新快照**
- 用于追踪账户价值变化、保证金使用率趋势
- 唯一约束 `uk_address_time` 防止同一时刻重复

#### **关联关系**
```
hl_position_snapshots (1) ←→ (N) hl_position_details
一个快照包含多个持仓明细（N = 持仓币种数量）
```

#### **使用场景**

**实时监控**：
```bash
# 每 5 分钟采集一次
*/5 * * * * python scripts/fetch_all_position_snapshots.py
```

**历史分析**：
```sql
-- 查看最近 24 小时的账户价值变化
SELECT 
    FROM_UNIXTIME(snapshot_time/1000) as time,
    account_value,
    total_margin_used,
    (total_margin_used / account_value * 100) as margin_ratio
FROM hl_position_snapshots 
WHERE address = '0x...'
  AND snapshot_time > UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 24 HOUR)) * 1000
ORDER BY snapshot_time ASC;
```

---

## 📚 相关文档

- [Hyperliquid 官方文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- [数据库设计](./DATABASE.md)
- [字段详解](./FILL_FIELDS.md)
- [时区策略](./TIMEZONE_POLICY.md)
- [脚本使用](./SCRIPTS.md)

---

**最后更新**: 2026-04-07
