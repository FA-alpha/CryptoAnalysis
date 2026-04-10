# Hyperbot Hyperliquid API 整理（A 方案）

- 来源：`docs/hyperbot/Hyperliquid API - Hyperbot 开放API_20260410.html`
- 接口总数：`77`
- 阅读方式：每个接口一个小节（路径、参数、返回字段）

## WebSocket（5）

### 1. `WS /api/upgrade/v2/hl/ws`
- 接口名：WebSocket 订阅
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：文档未提供可解析样例

### 2. `WS /api/upgrade/v2/hl/ws`
- 接口名：WebSocket：官方订阅兼容入口
- 参数：文档未明确列出（或无额外参数）
- 返回字段示例：`method`、`subscription`、`type`、`coin`、`interval`

### 3. `WS /api/upgrade/v2/hl/ws/fills`
- 接口名：WebSocket：订阅用户成交
- 参数：文档未明确列出（或无额外参数）
- 返回字段示例：`type`、`address`

### 4. `WS /api/upgrade/v2/hl/ws/filled-orders`
- 接口名：WebSocket：订阅用户成交订单
- 参数：文档未明确列出（或无额外参数）
- 返回字段示例：`type`、`data`、`ts`、`address`、`hash`、`builder`、`builderF`、`status`、`coin`、`side`

### 5. `WS /api/upgrade/v2/hl/ws/clearinghouse-state`
- 接口名：WebSocket：订阅用户账户状态
- 参数：
  - `dex` (string)：可选，指定 dex，默认为主 dex（空串）。一个连接支持一个 dex，多个 dex 使用多个连接（ ?dex=xyz ）
- 返回字段示例：`type`、`address`

## HTTP 接口（非 info）（51）

### 1. `GET /api/upgrade/v2/hl/tickers`
- 接口名：获取所有 Ticker 数据
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：Ticker 数据数组
- 返回字段示例：`code`、`msg`、`data`、`coin`、`price`

### 2. `GET /api/upgrade/v2/hl/tickers/coin/:coin`
- 接口名：获取指定币种 Ticker 数据
- 参数：
  - `coin` (string)：币种名称，如 ETH 、 BTC
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：指定币种的 Ticker 数据
- 返回字段示例：`code`、`msg`、`data`、`coin`、`price`

### 3. `GET /api/upgrade/v2/hl/fills/:address`
- 接口名：获取用户成交数据
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `coin` (string)：可选，筛选指定币种的成交记录
  - `limit` (integer)：可选，返回记录数量限制，默认 1000，最大 2000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：成交记录数组
- 返回字段示例：`code`、`msg`、`data`、`coin`、`side`、`price`、`size`、`time`、`oid`

### 4. `GET /api/upgrade/v2/hl/fills/oid/:oid`
- 接口名：根据订单ID获取成交数据
- 参数：
  - `oid` (string)：订单 ID，如 2361000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：成交记录数组
- 返回字段示例：`code`、`msg`、`data`、`coin`、`side`、`price`、`size`、`time`、`oid`

### 5. `GET /api/upgrade/v2/hl/fills/twapid/:twapid`
- 接口名：根据TWAP ID获取成交数据
- 参数：
  - `twapid` (string)：TWAP ID，如 1509340
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：成交记录数组
- 返回字段示例：`code`、`msg`、`data`、`coin`、`side`、`px`、`sz`、`time`、`twapId`

### 6. `GET /api/upgrade/v2/hl/fills/builder/:builder/latest`
- 接口名：获取Builder最新成交
- 参数：
  - `builder` (string)：Builder 钱包地址，如 0xb84168cf3be63c6b8dad05ff5d755e97432ff80b
  - `coin` (string)：可选，筛选指定币种的成交记录，如 BTC
  - `limit` (integer)：可选，返回记录数量限制，默认 1000，最大 2000
  - `minVal` (integer)：可选，最小成交额过滤（USD）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`builderFee`、`closedPnl`、`coin`、`crossed`、`dir`、`fee`、`feeToken`

### 7. `GET /api/upgrade/v2/hl/fills/top-trades`
- 接口名：获取Top成交
- 参数：
  - `interval` (string)：必传 ，时间周期，取值范围 1s ~ 7d
  - `coin` (string)：必传 ，筛选指定币种，如 BTC 、 ETH
  - `limit` (integer)：必传 ，返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：Top 成交记录数组
- 返回字段示例：`code`、`msg`、`data`、`time`、`address`、`coin`、`side`、`oid`、`isTaker`、`px`

### 8. `GET /api/upgrade/v2/hl/filled-orders/:address/latest`
- 接口名：获取成交订单数据
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `coin` (string)：可选，筛选指定币种的成交订单
  - `limit` (integer)：可选，返回记录数量限制，默认 1000，最大 1000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：成交订单数组
- 返回字段示例：`code`、`msg`、`data`、`oid`、`coin`、`side`、`price`、`size`、`filledSize`、`status`

### 9. `GET /api/upgrade/v2/hl/filled-orders/oid/:oid`
- 接口名：根据订单ID获取成交订单
- 参数：
  - `oid` (string)：订单 ID，如 23671238460
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：成交订单详情，如不存在返回 null
- 返回字段示例：`code`、`msg`、`data`、`oid`、`coin`、`side`、`price`、`size`、`filledSize`、`status`

### 10. `GET /api/upgrade/v2/hl/orders/:address/latest`
- 接口名：获取最新订单数据
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `coin` (string)：可选，筛选指定币种的订单
  - `limit` (integer)：可选，返回记录数量限制，默认 2000，最大 2000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：订单数组
- 返回字段示例：`code`、`msg`、`data`、`oid`、`coin`、`side`、`price`、`size`、`filledSize`、`status`

### 11. `GET /api/upgrade/v2/hl/orders/oid/:oid`
- 接口名：根据订单ID获取订单
- 参数：
  - `oid` (string)：订单 ID，如 23671238460
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：订单详情，如不存在返回 null
- 返回字段示例：`code`、`msg`、`data`、`oid`、`coin`、`side`、`price`、`size`、`filledSize`、`status`

### 12. `GET /api/upgrade/v2/hl/orders/top-open-orders`
- 接口名：获取Top挂单
- 参数：
  - `minVal` (string)：可选，最小订单价值筛选
  - `coin` (string)：可选，筛选指定币种，如 BTC 、 ETH
  - `limit` (integer)：可选，返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：Top 挂单数组， distPct 为与最新交易价的距离百分比
- 返回字段示例：`code`、`msg`、`data`、`time`、`address`、`oid`、`coin`、`side`、`sz`、`origSz`

### 13. `GET /api/upgrade/v2/hl/orders/active-stats`
- 接口名：获取挂单统计
- 参数：
  - `whaleThreshold` (string)：可选，鲸鱼标准（订单价值 limitPx × sz）
  - `coin` (string)：可选，筛选指定币种，如 BTC 、 ETH
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：挂单统计数据， bidValueRatio 为买单价值占总量之比
- 返回字段示例：`code`、`msg`、`data`、`totalCount`、`bidCount`、`askCount`、`bidValue`、`askValue`、`bidValueRatio`、`whaleBidCount`

### 14. `GET /api/upgrade/v2/hl/portfolio/:address/:window`
- 接口名：获取账户价值曲线和PNL曲线
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `window` (string)：时间窗口，可选值： day 、 week 、 month 、 allTime
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：包含账户价值曲线和 PNL 曲线的数据
- 返回字段示例：`code`、`msg`、`data`、`accountValue`、`time`、`value`、`pnl`

### 15. `GET /api/upgrade/v2/hl/pnls/:address`
- 接口名：获取PNL曲线
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `period` (integer)：周期天数，默认 0。可选值： 0 （allTime）、 1 、 7 、 30
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：PNL 曲线数据数组
- 返回字段示例：`code`、`msg`、`data`、`time`、`pnl`

### 16. `GET /api/upgrade/v2/hl/traders/:address/best-trades`
- 接口名：获取收益最高的交易
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `period` (integer)：周期天数，如 1 、 7 、 30 等
  - `limit` (integer)：返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：收益最高的交易列表
- 返回字段示例：`code`、`msg`、`data`、`coin`、`side`、`entryPrice`、`exitPrice`、`pnl`、`pnlPercent`、`openTime`

### 17. `GET /api/upgrade/v2/hl/traders/:address/performance-by-coin`
- 接口名：获取分币种交易统计
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `period` (integer)：周期天数，如 1 、 7 、 30 等， 0 表示 All Time
  - `limit` (integer)：返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：分币种的交易统计数据
- 返回字段示例：`code`、`msg`、`data`、`coin`、`tradeCount`、`winCount`、`lossCount`、`winRate`、`totalPnl`、`avgPnl`

### 18. `GET /api/upgrade/v2/hl/traders/:address/addr-stat`
- 接口名：获取交易统计
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `period` (integer)：周期天数，如 1 、 7 、 30 等，默认 7
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：交易统计数据
- 返回字段示例：`code`、`msg`、`data`、`avgPosDuration`、`closePosCount`、`maxDrawdown`、`orderCount`、`totalPnl`、`winRate`

### 19. `POST /api/upgrade/v2/hl/traders/batch-addr-stat`
- 接口名：批量获取交易统计
- 参数：
  - `addresses` (array[string])：地址列表，最多 50 个地址
  - `period` (integer)：周期天数： 1 、 7 、 30 、 0 （0 表示 all-time，默认 7）
  - `data` (array[object])：交易统计数据列表
  - `address` (string)：用户钱包地址
  - `winRate` (string)：胜率
  - `orderCount` (integer)：成交订单数
  - `closePosCount` (integer)：平仓次数
  - `avgPosDuration` (integer)：平均持仓时间（秒）
- 返回字段示例：`code`、`msg`、`data`、`address`、`winRate`、`orderCount`、`closePosCount`、`avgPosDuration`、`maxDrawdown`、`totalPnl`

### 20. `GET /api/upgrade/v2/hl/traders/:address/completed-trades`
- 接口名：获取已完成交易列表
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：可选，筛选指定币种
  - `limit` (integer)：返回记录数量限制，默认 100，最大 2000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：已完成交易列表
- 返回字段示例：`code`、`msg`、`data`、`coin`、`side`、`entryPrice`、`exitPrice`、`size`、`pnl`、`pnlPercent`

### 21. `POST /api/upgrade/v2/hl/traders/:address/completed-trades/by-time`
- 接口名：按时间查询已完成交易
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `pageNum` (integer)：页码，默认 1。最大限制 50
  - `pageSize` (integer)：每页记录数，默认 20。最大限制 2000
  - `Coin` (string)：可选，筛选指定币种，如 BTC 、 ETH
  - `endTimeFrom` (integer)：可选，结束时间起始（毫秒时间戳）
  - `endTimeTo` (integer)：可选，结束时间截止（毫秒时间戳）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
- 返回字段示例：`code`、`msg`、`data`、`list`、`coin`、`side`、`entryPrice`、`exitPrice`、`size`、`pnl`

### 22. `GET /api/upgrade/v2/hl/traders/:address/current-position-history/:coin`
- 接口名：获取当前仓位历史
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：当前仓位历史数据
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`history`、`time`

### 23. `GET /api/upgrade/v2/hl/traders/:address/completed-position-history/:coin`
- 接口名：获取已完成仓位历史
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `startTime` (integer)：开始时间戳（毫秒），与 endTime 至少传一个
  - `endTime` (integer)：结束时间戳（毫秒），与 startTime 至少传一个
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`endTime`、`history`

### 24. `GET /api/upgrade/v2/hl/traders/:address/current-position-pnl/:coin`
- 接口名：获取当前仓位PnL
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，时间周期。取值范围： 15m ~ 1d
  - `limit` (integer)：可选，返回记录数量限制，默认 20，最大 1000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`interval`、`pnls`

### 25. `GET /api/upgrade/v2/hl/traders/:address/completed-position-pnl/:coin`
- 接口名：获取已完成仓位PnL
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，时间周期。取值范围： 15m ~ 1d
  - `startTime` (integer)：开始时间戳（毫秒），与 endTime 至少传一个
  - `endTime` (integer)：结束时间戳（毫秒），与 startTime 至少传一个
  - `limit` (integer)：可选，返回记录数量限制，默认 20，最大 1000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`endTime`、`interval`

### 26. `GET /api/upgrade/v2/hl/traders/:address/current-position-executions/:coin`
- 接口名：获取当前仓位操盘轨迹
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，时间周期。取值范围： 15m ~ 1d
  - `limit` (integer)：可选，返回记录数量限制，默认 20，最大 1000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`interval`、`executions`

### 27. `GET /api/upgrade/v2/hl/traders/:address/completed-position-executions/:coin`
- 接口名：获取已完成仓位操盘轨迹
- 参数：
  - `address` (string)：用户钱包地址，如 0xfe00xxx
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，时间周期。取值范围： 15m ~ 1d
  - `startTime` (integer)：开始时间戳（毫秒），与 endTime 至少传一个
  - `endTime` (integer)：结束时间戳（毫秒），与 startTime 至少传一个
  - `limit` (integer)：可选，返回记录数量限制，默认 20，最大 1000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
- 返回字段示例：`code`、`msg`、`data`、`address`、`coin`、`direction`、`cross`、`startTime`、`endTime`、`interval`

### 28. `POST /api/upgrade/v2/hl/traders/accounts`
- 接口名：批量查询账户信息
- 参数：
  - `addresses` (array)：地址列表，最多 50 个地址，超出时静默截取前 50 个
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：账户信息列表
- 返回字段示例：`code`、`msg`、`data`、`address`、`currentPosition`、`effLeverage`、`lastOperationAt`、`leverage`、`marginUsage`、`marginUsageRate`

### 29. `POST /api/upgrade/v2/hl/traders/statistics`
- 接口名：批量查询交易统计
- 参数：
  - `period` (integer)：周期天数，如 1 、 7 、 30 等， 0 表示 All Time，默认 7
  - `pnlList` (boolean)：是否需要 pnl 曲线数据
  - `addresses` (array)：地址列表，最多 50 个地址，超出时静默截取前 50 个
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：交易统计数据列表
- 返回字段示例：`code`、`msg`、`data`、`address`、`avgHoldingSec`、`currentPosition`、`effLeverage`、`lastOperationAt`、`leverage`、`longPnl`

### 30. `POST /api/upgrade/v2/hl/traders/clearinghouse-state`
- 接口名：批量获取永续合约账户状态
- 参数：
  - `addresses` (array)：必填，地址列表，最多 50 个，超出时静默截取前 50 个
  - `dex` (string)：可选，DEX名称，默认空字符串表示主DEX
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：账户状态列表
  - `data[].address` (string)：地址
- 返回字段示例：`code`、`msg`、`data`、`address`、`state`、`marginSummary`、`accountValue`、`totalNtlPos`、`totalRawUsd`、`totalMarginUsed`

### 31. `POST /api/upgrade/v2/hl/traders/spot-clearinghouse-state`
- 接口名：批量获取现货账户状态
- 参数：
  - `addresses` (array)：必填，地址列表，最多 50 个，超出时静默截取前 50 个
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：账户状态列表
  - `data[].address` (string)：地址
  - `data[].spotState` (object)：现货账户状态
- 返回字段示例：`code`、`msg`、`data`、`address`、`spotState`、`balances`、`coin`、`token`、`total`、`hold`

### 32. `GET /api/upgrade/v2/hl/whales/latest-events`
- 接口名：获取鲸鱼仓位事件
- 参数：
  - `limit` (integer)：可选，返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：鲸鱼仓位事件列表
- 返回字段示例：`code`、`msg`、`data`、`user`、`symbol`、`marginMode`、`positionSize`、`entryPrice`、`liqPrice`、`positionValueUsd`

### 33. `GET /api/upgrade/v2/hl/whales/directions`
- 接口名：获取鲸鱼仓位多空数
- 参数：
  - `coin` (string)：可选，筛选指定币种，如 ETH 、 BTC
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：多空数统计数据
- 返回字段示例：`code`、`msg`、`data`、`longCount`、`shortCount`

### 34. `GET /api/upgrade/v2/hl/liquidations/stat`
- 接口名：获取强平统计
- 参数：
  - `coin` (string)：可选，筛选指定币种，如 ETH 、 BTC
  - `interval` (string)：可选，时间间隔，取值范围 1s ~ 60d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：强平统计数据
- 返回字段示例：`code`、`msg`、`data`、`startTime`、`addresses`、`shortLiquidations`、`longLiquidations`、`totalFilled`、`longFilled`、`shortFilled`

### 35. `GET /api/upgrade/v2/hl/liquidations/stat-by-coin`
- 接口名：获取强平统计（分币种）
- 参数：
  - `interval` (string)：可选，时间间隔，取值范围 1s ~ 60d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：按币种分组的强平统计数据
- 返回字段示例：`code`、`msg`、`data`、`coin`、`addresses`、`shortLiquidations`、`longLiquidations`、`totalFilled`、`longFilled`、`shortFilled`

### 36. `GET /api/upgrade/v2/hl/liquidations/history`
- 接口名：获取强平历史
- 参数：
  - `coin` (string)：可选，筛选指定币种，如 ETH 、 BTC
  - `interval` (string)：可选，时间间隔，取值范围 1m ~ 60d
  - `limit` (integer)：可选，返回记录数量限制，默认 20，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：强平历史数据
- 返回字段示例：`code`、`msg`、`data`、`startTime`、`addresses`、`shortLiquidations`、`longLiquidations`、`totalFilled`、`longFilled`、`shortFilled`

### 37. `GET /api/upgrade/v2/hl/liquidations/top-positions`
- 接口名：获取Top强平仓位
- 参数：
  - `interval` (string)：必传 ，时间周期，取值范围 1m ~ 60d
  - `coin` (string)：必传 ，筛选指定币种，如 BTC 、 ETH
  - `limit` (integer)：必传 ，返回记录数量限制，默认 10，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：Top 强平仓位数组
- 返回字段示例：`code`、`msg`、`data`、`time`、`address`、`coin`、`direction`、`oid`、`liqPrice`、`liquidatedVal`

### 38. `POST /api/upgrade/v2/hl/smart/find`
- 接口名：发现聪明钱地址
- 参数：
  - `pageNum` (integer)：页码，默认 1，最大 20
  - `pageSize` (integer)：每页记录数，默认 20，最大 25
  - `period` (integer)：周期天数，如 7 表示最近7天
  - `sort` (string)：排序方式，可选值： win-rate （胜率）、 account-balance （账户余额）、 ROI （收益率）、 pnl （盈亏）、 position-count （持仓数量...
  - `pnlList` (boolean)：是否需要 pnl 曲线数据
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
- 返回字段示例：`code`、`msg`、`data`、`address`、`avgHoldingSec`、`currentPosition`、`effLeverage`、`lastOperationAt`、`leverage`、`longPnl`

### 39. `GET /api/upgrade/v2/hl/whales/history-long-ratio`
- 接口名：获取历史鲸鱼仓位多空比
- 参数：
  - `interval` (string)：可选，时间间隔，默认 1h 。可选值： 10m 、 1h 、 4h 、 1d
  - `limit` (integer)：可选，返回记录数量限制，默认 50，最大 200
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：历史多空比数据
- 返回字段示例：`code`、`msg`、`data`、`time`、`longRatio`、`positionValueDiff`、`longPositionValueRatio`

### 40. `GET /api/upgrade/v2/hl/whales/open-positions`
- 接口名：查询鲸鱼仓位
- 参数：
  - `coin` (string)：可选，筛选指定币种，如 ETH 、 BTC
  - `dir` (string)：可选，筛选方向，可选值： long （多头）、 short （空头）
  - `npnlSide` (string)：可选，浮盈/浮亏筛选，可选值： profit （浮盈）、 loss （浮亏）
  - `frSide` (string)：可选，资金费盈亏筛选，可选值： profit （盈）、 loss （亏）
  - `topBy` (string)：可选，排序方式，可选值： position-value （仓位价值）、 margin-balance （保证金余额）、 create-time （创建时间）、 profit （盈利...
  - `take` (integer)：可选，返回记录数量限制，默认 10，最大 200
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
- 返回字段示例：`code`、`msg`、`data`、`user`、`symbol`、`positionSize`、`entryPrice`、`liqPrice`、`leverage`、`marginBalance`

### 41. `GET /api/upgrade/v2/hl/twap-states/:address/latest`
- 接口名：获取TWAP订单状态
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `coin` (string)：可选，筛选指定币种
  - `limit` (integer)：可选，返回记录数量限制，默认 100，最大 100
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：TWAP 订单状态列表
- 返回字段示例：`code`、`msg`、`data`

### 42. `GET /api/upgrade/v2/hl/max-drawdown/:address`
- 接口名：获取最大回撤
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `days` (integer)：可选，统计天数。取值： 1 、 7 、 30 、 60 、 90
  - `scope` (string)：可选，统计范围，默认 perp （当前仅支持 perp ）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：最大回撤数据
- 返回字段示例：`code`、`msg`、`data`、`high`、`time`、`value`、`low`、`maxDrawdown`、`netIn`

### 43. `POST /api/upgrade/v2/hl/batch-max-drawdown`
- 接口名：批量获取最大回撤
- 参数：
  - `addresses` (array)：地址列表，最多 50 个地址，超出时静默截取前 50 个
  - `days` (integer)：可选，统计天数。取值： 1 、 7 、 30 、 60 、 90 、 0 （0 表示 all-time）
  - `scope` (string)：可选，统计范围，默认 perp （当前仅支持 perp ）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：最大回撤数据列表，每个元素包含 Address 、 High 、 Low 、 MaxDrawdown 、 NetIn
- 返回字段示例：`code`、`msg`、`data`、`Address`、`High`、`time`、`value`、`Low`、`MaxDrawdown`、`NetIn`

### 44. `GET /api/upgrade/v2/hl/ledger-updates/net-flow/:address`
- 接口名：获取账本净流入
- 参数：
  - `address` (string)：用户钱包地址，如 0x0089xxx
  - `days` (integer)：可选，统计天数。取值： 1 、 7 、 30 、 60 、 90
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：账本净流入数据， netPerpIn - 合约账户净流入， netSpotIn - 现货账户净流入
- 返回字段示例：`code`、`msg`、`data`、`netPerpIn`、`netSpotIn`

### 45. `POST /api/upgrade/v2/hl/ledger-updates/batch-net-flow`
- 接口名：批量获取账本净流入
- 参数：
  - `addresses` (array)：地址列表，最多 50 个地址，超出时静默截取前 50 个
  - `days` (integer)：可选，统计天数。取值： 1 、 7 、 30 、 60 、 90 、 0 （0 表示 all-time）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：账本净流入数据列表，每个元素包含 address 、 netPerpIn 、 netSpotIn
- 返回字段示例：`code`、`msg`、`data`、`address`、`netPerpIn`、`netSpotIn`

### 46. `GET /api/upgrade/v2/hl/open-interest/summary`
- 接口名：获取当前未平仓位统计
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：未平仓位统计，包含 positionCount 、 longPv 、 shortPv 、 totalPv 、 avgPv
- 返回字段示例：`code`、`msg`、`data`、`positionCount`、`longPv`、`shortPv`、`totalPv`、`avgPv`

### 47. `GET /api/upgrade/v2/hl/open-interest/top-coins`
- 接口名：获取头部币种未平仓位统计
- 参数：
  - `limit` (integer)：可选，返回币种数量，默认 10，最大 50
  - `interval` (string)：最近时间窗口，默认 3d 。取值范围： 15m ~ 180d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：币种未平仓位统计数组
- 返回字段示例：`code`、`msg`、`data`、`coin`、`positionCount`、`longPv`、`shortPv`、`totalPv`、`avgPv`

### 48. `GET /api/upgrade/v2/hl/accumulated-taker-delta/:coin`
- 接口名：获取主动买卖累计差值
- 参数：
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，最近时间窗口。取值范围： 1s ~ 60d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：主动买卖累计差值，包含 szDelta 、 valDelta
- 返回字段示例：`code`、`msg`、`data`、`szDelta`、`valDelta`

### 49. `GET /api/upgrade/v2/hl/orderbooks/history-summaries/:coin`
- 接口名：历史订单簿统计
- 参数：
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：可选，最近时间窗口，默认 1d 。取值范围： 1h ~ 180d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：订单簿统计摘要
- 返回字段示例：`code`、`msg`、`data`、`time`、`coin`、`bidVolume`、`askVolume`

### 50. `GET /api/upgrade/v2/hl/open-interest/history/:coin`
- 接口名：历史未平仓位
- 参数：
  - `coin` (string)：币种名称（如：ETH）
  - `interval` (string)：最近时间窗口，默认 3d ，取值范围 15m ~ 180d
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：数据数组，每条记录包含： time - 时间戳 coin - 币种名称 positionCount - 仓位数量 longCount - 多头仓位数量 longPv - 多头仓位价...
- 返回字段示例：`code`、`msg`、`data`、`time`、`coin`、`positionCount`、`longCount`、`longPv`、`totalPv`、`avgPv`

### 51. `GET /api/upgrade/v2/hl/klines-with-taker-vol/:coin/:interval`
- 接口名：获取K线（含主动买卖量）
- 参数：
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：K线周期，取值范围： 1s ~ 1w 。常用值： 1m 、 3m 、 5m 、 15m 、 30m 、 1h 、 4h 、 8h 、 1d 、 1w
  - `startTime` (integer)：可选，开始时间（毫秒时间戳）
  - `endTime` (integer)：可选，结束时间（毫秒时间戳）
  - `limit` (integer)：可选，返回记录数量限制，默认 100，最大 2000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
- 返回字段示例：`code`、`msg`、`data`、`openTime`、`tc`、`size`、`amount`、`tcBuyer`、`sizeBuyer`、`amountBuyer`

## Info 统一端点子接口（21）

### 1. `POST /api/upgrade/v2/hl/info`
- 接口名：Info API 统一端点
- 参数：
  - `type` (string)：请求类型，支持以下值： meta : 获取永续合约元数据 spotMeta : 获取现货元数据 clearinghouseState : 获取用户永续合约账户状态（需要 user）...
  - `user` (string)：用户钱包地址，部分 type 需要此参数
  - `startTime` (integer)：开始时间（毫秒），部分 type 需要此参数
  - `endTime` (integer)：结束时间（毫秒），可选
  - `coin` (string)：币种名称，部分 type 需要此参数
  - `oid` (integer|string)：订单ID，orderStatus 类型需要此参数
  - `dex` (string)：DEX名称，frontendOpenOrders 类型可选
  - `aggregateByTime` (boolean)：是否按时间聚合，userFills/userFillsByTime 类型可选
- 返回字段示例：`code`、`msg`、`data`、`universe`、`name`、`szDecimals`、`maxLeverage`

### 2. `POST /api/upgrade/v2/hl/info`
- 接口名：获取现货元数据
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：现货元数据
- 返回字段示例：`code`、`msg`、`data`、`universe`、`tokens`、`name`、`szDecimals`、`weiDecimals`、`index`

### 3. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户永续合约账户状态
- 参数：
  - `user` (string)：用户钱包地址，如 0x0000000000000000000000000000000000000000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：用户账户状态数据
- 返回字段示例：`code`、`msg`、`data`、`assetPositions`、`position`、`coin`、`entryPx`、`leverage`、`type`、`value`

### 4. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户现货账户状态
- 参数：
  - `user` (string)：用户钱包地址，如 0x0000000000000000000000000000000000000000
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：用户现货账户状态数据
- 返回字段示例：`code`、`msg`、`data`、`balances`、`coin`、`hold`、`total`

### 5. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户挂单
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：挂单列表
- 返回字段示例：`code`、`msg`、`data`、`coin`、`limitPx`、`oid`、`side`、`sz`、`timestamp`

### 6. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户挂单（前端格式）
- 参数：
  - `user` (string)：用户钱包地址
  - `dex` (string)：可选，永续 DEX 名称。默认空字符串表示第一个永续 DEX，包含现货挂单
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：挂单列表（前端格式）
- 返回字段示例：`code`、`msg`、`data`、`coin`、`isPositionTpsl`、`isTrigger`、`limitPx`、`oid`、`orderType`、`origSz`

### 7. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户手续费
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：用户手续费信息
- 返回字段示例：`code`、`msg`、`data`、`dailyUserVlm`、`feeSchedule`、`taker`、`maker`

### 8. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户成交记录（Info API）
- 参数：
  - `user` (string)：用户钱包地址
  - `aggregateByTime` (boolean)：可选，是否按时间聚合
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：成交记录列表
- 返回字段示例：`code`、`msg`、`data`、`closedPnl`、`coin`、`crossed`、`dir`、`hash`、`oid`、`px`

### 9. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户指定时间范围成交记录
- 参数：
  - `user` (string)：用户钱包地址
  - `startTime` (integer)：开始时间（毫秒时间戳）
  - `endTime` (integer)：可选，结束时间（毫秒时间戳），默认当前时间
  - `aggregateByTime` (boolean)：可选，是否按时间聚合
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`closedPnl`、`coin`、`dir`、`oid`、`px`、`side`、`sz`

### 10. `POST /api/upgrade/v2/hl/info`
- 接口名：获取K线数据
- 参数：
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `interval` (string)：K线周期，可选值： 1m 、 3m 、 5m 、 15m 、 30m 、 1h 、 2h 、 4h 、 8h 、 12h 、 1d 、 3d 、 1w 、 1M
  - `startTime` (integer)：开始时间（毫秒时间戳）
  - `endTime` (integer)：可选，结束时间（毫秒时间戳）
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
- 返回字段示例：`code`、`msg`、`data`、`T`、`c`、`h`、`i`、`l`、`n`、`o`

### 11. `POST /api/upgrade/v2/hl/info`
- 接口名：获取永续DEX列表
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：永续 DEX 列表
- 返回字段示例：`code`、`msg`、`data`

### 12. `POST /api/upgrade/v2/hl/info`
- 接口名：获取所有 mid price
- 参数：
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：所有 mid price 映射
- 返回字段示例：`code`、`msg`、`data`、`BTC`、`ETH`、`SOL`

### 13. `POST /api/upgrade/v2/hl/info`
- 接口名：获取 L2 订单簿
- 参数：
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：L2 订单簿数据
- 返回字段示例：`code`、`msg`、`data`、`coin`、`levels`、`n`、`px`、`sz`、`time`

### 14. `POST /api/upgrade/v2/hl/info`
- 接口名：获取历史订单
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：历史订单列表
- 返回字段示例：`code`、`msg`、`data`、`order`、`coin`、`side`、`limitPx`、`sz`、`oid`、`timestamp`

### 15. `POST /api/upgrade/v2/hl/info`
- 接口名：获取订单状态
- 参数：
  - `user` (string)：用户钱包地址
  - `oid` (string|integer)：订单 ID，可以是数字或十六进制字符串
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：订单状态信息
- 返回字段示例：`code`、`msg`、`data`、`order`、`coin`、`limitPx`、`oid`、`side`、`sz`、`timestamp`

### 16. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户资金费用历史
- 参数：
  - `user` (string)：用户钱包地址
  - `startTime` (integer)：开始时间（毫秒时间戳）
  - `endTime` (integer)：可选，结束时间（毫秒时间戳），默认当前时间
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：资金费用历史列表
- 返回字段示例：`code`、`msg`、`data`、`delta`、`coin`、`fundingRate`、`szi`、`type`、`usdc`、`hash`

### 17. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户非资金费账本更新
- 参数：
  - `user` (string)：用户钱包地址
  - `startTime` (integer)：开始时间（毫秒时间戳）
  - `endTime` (integer)：可选，结束时间（毫秒时间戳），默认当前时间
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：账本更新记录列表
- 返回字段示例：`code`、`msg`、`data`、`delta`、`type`、`usdc`、`hash`、`time`

### 18. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户投资组合信息
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：投资组合信息
- 返回字段示例：`code`、`msg`、`data`

### 19. `POST /api/upgrade/v2/hl/info`
- 接口名：获取 Web 综合数据
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：Web 综合数据
- 返回字段示例：`code`、`msg`、`data`

### 20. `POST /api/upgrade/v2/hl/info`
- 接口名：获取用户 TWAP 切片成交
- 参数：
  - `user` (string)：用户钱包地址
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (array)：TWAP 切片成交记录列表
- 返回字段示例：`code`、`msg`、`data`

### 21. `POST /api/upgrade/v2/hl/info`
- 接口名：获取活跃资产数据
- 参数：
  - `user` (string)：用户钱包地址
  - `coin` (string)：币种名称，如 BTC 、 ETH
  - `AccessKeyId` (string)：用户访问密钥ID
  - `SignatureNonce` (string)：签名随机数
  - `Timestamp` (string)：请求时间戳(秒)，有效期30秒
  - `Signature` (string)：使用 HmacSHA1 + Base64 生成的签名，请参考 如何获取 API 认证参数
  - `data` (object)：活跃资产数据
- 返回字段示例：`code`、`msg`、`data`
