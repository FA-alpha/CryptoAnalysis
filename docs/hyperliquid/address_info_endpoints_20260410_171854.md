# Hyperliquid 地址接口实测样本（精简版）

实测地址：`0x020ca66c30bec2c4fe3861a94e4db4a498a35872`  
请求时间：`2026-04-10`  
统一入口：`POST https://api.hyperliquid.xyz/info`

## 说明

- 仅展示“本次实测有返回数据”的 `type`。
- 列表型返回只展示第 1 条样本。
- 字段解释只保留关键字段，避免文档过长。

## 有数据的 type（样本 + 字段解释）

### `openOrders`
```json
{"coin":"ETH","side":"A","limitPx":"2200.0","sz":"25.0","oid":376457852172,"timestamp":1775805116055,"origSz":"25.0"}
```
- `coin`：交易标的
- `side`：方向（`A`=卖，`B`=买）
- `limitPx`：挂单价格
- `sz`：当前剩余数量
- `origSz`：初始下单数量
- `oid`：订单 ID
- `timestamp`：订单时间戳（毫秒）

### `frontendOpenOrders`
```json
{"coin":"ETH","side":"A","limitPx":"2200.0","sz":"25.0","oid":376457852172,"timestamp":1775805116055,"isTrigger":false,"triggerPx":"0.0","orderType":"Limit","reduceOnly":false,"tif":"Gtc","cloid":null}
```
- 在 `openOrders` 基础上增加了前端常用字段
- `isTrigger`/`triggerPx`：是否条件单、触发价
- `orderType`：订单类型
- `reduceOnly`：是否只减仓
- `tif`：有效期策略

### `userFills`
```json
{"coin":"ETH","px":"2195.0","sz":"25.0","side":"A","time":1775812770011,"dir":"Close Long","closedPnl":"742.75","oid":376527981866,"fee":"2.195","feeToken":"USDC","tid":913779204919689}
```
- `px`：成交价格
- `sz`：成交数量
- `dir`：成交方向语义（如平多）
- `closedPnl`：本笔已实现盈亏
- `fee`/`feeToken`：手续费及计价币种
- `tid`：成交 ID

### `userFillsByTime`
```json
{"coin":"HYPE","px":"24.786","sz":"12.27","side":"A","time":1767454391528,"dir":"Close Long","closedPnl":"2.455227","oid":285336711401,"fee":"0.091237","feeToken":"USDC"}
```
- 字段含义与 `userFills` 基本一致
- 差异点：由 `startTime/endTime` 进行时间窗口筛选

### `userRateLimit`
```json
{"cumVlm":"8449414115.6099996567","nRequestsUsed":36675,"nRequestsCap":8449424115,"nRequestsSurplus":0}
```
- `cumVlm`：累计交易量
- `nRequestsUsed`：已使用请求额度
- `nRequestsCap`：请求额度上限
- `nRequestsSurplus`：剩余额度缓冲

### `historicalOrders`
```json
{"order":{"coin":"ETH","side":"A","limitPx":"2195.0","oid":376527981866,"timestamp":1775810999699,"orderType":"Limit","tif":"Gtc"},"status":"filled","statusTimestamp":1775812770011}
```
- `order`：订单对象（下单参数快照）
- `status`：订单状态（如 `filled`）
- `statusTimestamp`：状态更新时间

### `userRole`
```json
{"role":"user"}
```
- `role`：地址角色（如 `user`/`agent`/`vault`/`subAccount`/`missing`）

### `portfolio`
```json
["day",{"accountValueHistory":[[1775725440014,"1723629.2189760001"]],"pnlHistory":[[1775725440014,"0.0"]],"vlm":"..."}]
```
- 返回为时间粒度数组，本样本是 `day`
- `accountValueHistory`：账户净值时间序列
- `pnlHistory`：PnL 时间序列
- `vlm`：该周期成交量

### `referral`
```json
{"referredBy":{"referrer":"0x4627...f813","code":"IMTOKEN"},"cumVlm":"8449415503.0799999237","unclaimedRewards":"0.0","claimedRewards":"0.0","builderRewards":"0.0"}
```
- `referredBy`：上级邀请信息
- `cumVlm`：累计交易量
- `unclaimedRewards`：未领取奖励
- `claimedRewards`：已领取奖励
- `builderRewards`：builder 奖励

### `userFees`
```json
{"dailyUserVlm":[{"date":"2026-03-27","userCross":"9900161.3200000003","userAdd":"325468.86"}],"userCrossRate":"...","userAddRate":"...","userSpotCrossRate":"...","userSpotAddRate":"...","activeReferralDiscount":"..."}
```
- `dailyUserVlm`：按日成交量拆分（吃单/挂单）
- `userCrossRate`/`userAddRate`：永续费率
- `userSpotCrossRate`/`userSpotAddRate`：现货费率
- `activeReferralDiscount`：当前邀请折扣

### `delegations`
```json
{"validator":"0x5ac9...b487","amount":"0.00000118","lockedUntilTimestamp":1757592892923}
```
- `validator`：验证者地址
- `amount`：委托数量
- `lockedUntilTimestamp`：锁定截止时间

### `delegatorSummary`
```json
{"delegated":"0.00000118","undelegated":"0.0","totalPendingWithdrawal":"0.0","nPendingWithdrawals":0}
```
- `delegated`：已委托总量
- `undelegated`：未委托余额
- `totalPendingWithdrawal`：待提取总量
- `nPendingWithdrawals`：待提取笔数

### `delegatorHistory`
```json
{"time":1759433247022,"hash":"0x0000...0000","delta":{"withdrawal":{"amount":"100079.07812","phase":"finalized"}}}
```
- `time`：事件时间
- `hash`：关联交易哈希
- `delta`：变化明细（如委托/解委托/提现阶段）

### `delegatorRewards`
```json
{"time":1758758400226,"source":"delegation","totalAmount":"6.01299679"}
```
- `source`：奖励来源
- `totalAmount`：奖励总额

### `userDexAbstraction`
```json
true
```
- 布尔值，表示是否启用对应抽象能力

### `userAbstraction`
```json
"dexAbstraction"
```
- 字符串枚举，表示账户抽象状态类型

### `borrowLendUserState`
```json
{"tokenToState":[],"health":"healthy","healthFactor":null}
```
- `tokenToState`：各 token 借贷状态映射
- `health`：健康状态
- `healthFactor`：健康因子（可能为空）

### `orderStatus`
```json
{"status":"unknownOid"}
```
- `status`：订单查询结果状态（这里是订单不存在）

### `maxBuilderFee`
```json
0
```
- 返回数值，表示该用户对指定 `builder` 的最大费率授权（十分之一 bp 单位）

### `userNonFundingLedgerUpdates`（官方支持：充值/提现等非资金费流水）
> 说明：该 type 在本次地址样本中未实测到返回，因此这里补充“官方接口定义 + 请求示例”。

**用途**
- 查询地址的非资金费（non-funding）账本更新流水，包含充值、提现、转账等事件。

**请求体示例**
```json
{
  "type": "userNonFundingLedgerUpdates",
  "user": "0x020ca66c30bec2c4fe3861a94e4db4a498a35872",
  "startTime": 1775600000000,
  "endTime": 1776200000000
}
```

**关键参数**
- `type`：固定为 `userNonFundingLedgerUpdates`
- `user`：地址（42 位十六进制）
- `startTime`：起始时间（毫秒，包含）
- `endTime`：结束时间（毫秒，可选；不传通常表示到当前）

**返回说明（按事件类型变化）**
- 返回列表按时间给出账本变更事件。
- 事件明细通常在 `delta` 内，常见会出现：
  - `deposit`（充值）
  - `withdraw` / `withdrawal`（提现）
  - 以及其它非资金费账本变动类型（如转账等）

## 本次为空的 type（不展开解释）

`userTwapSliceFills`、`subAccounts`、`userVaultEquities`、`approvedBuilders`、`vaultDetails`
