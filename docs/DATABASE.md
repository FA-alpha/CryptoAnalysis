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
| [hl_address_features](#hl-address-features) | 地址特征（计算结果） | ✅ 使用中（V3新增字段）|
| [hl_address_list](#hl-address-list) | 地址列表 | ✅ 使用中 |
| [hl_backtest_results](#hl-backtest-results) | 回测结果 | ✅ 使用中 |
| [hl_fills](#hl-fills) | 交易历史（原始成交数据） | ✅ 使用中 |
| [hl_ledger_updates](#hl-ledger-updates) | 非资金费账本流水（充值/提现/转账/vault） | ✅ 使用中 |
| [hl_follow_trades](#hl-follow-trades) | 跟单交易记录 | ✅ 使用中 |
| [hl_fragile_pool](#hl-fragile-pool) | 脆弱地址+币种监控池 | ✅ 使用中（2026-04-23 重建，加 coin 字段）|
| [hl_pool_change_logs](#hl-pool-change-logs) | 入池/出池变更日志 | ✅ 使用中（2026-04-23 新增）|
| [hl_fragile_scores](#hl-fragile-scores) | 脆弱地址评分 | ✅ 使用中（V3新增字段）|
| [hl_monitor_logs](#hl-monitor-logs) | 实时监控日志 | ✅ 使用中 |
| [hl_position_details](#hl-position-details) | 持仓明细 | ✅ 使用中 |
| [hl_position_snapshots](#hl-position-snapshots) | 持仓快照（汇总） | ✅ 使用中 |
| [hl_reverse_signals](#hl-reverse-signals) | 反向跟单信号 | ✅ 使用中 |

## 📑 视图清单

| 视图名称 | 说明 | 状态 |
|----------|------|------|
| [v_order_summary](#v_order_summary) | - | ✅ 使用中 |

---

## 1. hl_address_features

### **表说明**
地址特征（计算结果）

### **表结构**

```sql
CREATE TABLE `hl_address_features` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `calculated_at` datetime NOT NULL COMMENT '计算时间',
  `data_period_start` bigint DEFAULT NULL COMMENT '数据起始时间戳(ms)',
  `data_period_end` bigint DEFAULT NULL COMMENT '数据结束时间戳(ms)',
  `total_trades` int NOT NULL DEFAULT '0' COMMENT '总交易次数',
  `win_rate` decimal(5,2) DEFAULT NULL COMMENT '胜率(%)',
  `avg_win_pnl` decimal(20,6) DEFAULT NULL COMMENT '平均盈利',
  `avg_loss_pnl` decimal(20,6) DEFAULT NULL COMMENT '平均亏损',
  `profit_loss_ratio` decimal(10,2) DEFAULT NULL COMMENT '盈亏比',
  `total_realized_pnl` decimal(20,6) DEFAULT NULL COMMENT '总已实现盈亏',
  `total_fee` decimal(20,6) DEFAULT NULL COMMENT '总手续费',
  `avg_leverage` decimal(10,2) DEFAULT NULL COMMENT '平均实际杠杆',
  `max_leverage` decimal(10,2) DEFAULT NULL COMMENT '最大实际杠杆',
  `avg_margin_utilization` decimal(5,2) DEFAULT NULL COMMENT '平均保证金使用率(%)',
  `max_margin_utilization` decimal(5,2) DEFAULT NULL COMMENT '最大保证金使用率(%)',
  `coin_concentration` decimal(5,2) DEFAULT NULL COMMENT '单币种集中度(%)',
  `liquidation_count` int DEFAULT '0' COMMENT '清算次数',
  `max_drawdown` decimal(5,2) DEFAULT NULL COMMENT '最大回撤(%, 待实现)',
  `hold_loss_ratio` decimal(10,2) DEFAULT NULL COMMENT '死扛指数(亏损持仓时间/盈利持仓时间, 待实现)',
  `active_days` int DEFAULT NULL COMMENT '活跃天数',
  `avg_trades_per_day` decimal(10,2) DEFAULT NULL COMMENT '日均交易次数',
  `last_trade_time` bigint DEFAULT NULL COMMENT '最后一笔交易时间戳(ms)',
  PRIMARY KEY (`id`),
  KEY `idx_address_time` (`address`,`calculated_at` DESC),
  KEY `idx_calculated_at` (`calculated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='地址特征(计算结果)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `calculated_at` | datetime | ✅ | 计算时间 |
| `data_period_start` | bigint | ❌ | 数据起始时间戳(ms) |
| `data_period_end` | bigint | ❌ | 数据结束时间戳(ms) |
| `total_trades` | int | ✅ | 总交易次数 |
| `win_rate` | decimal(5,2) | ❌ | 胜率(%) |
| `avg_win_pnl` | decimal(20,6) | ❌ | 平均盈利 |
| `avg_loss_pnl` | decimal(20,6) | ❌ | 平均亏损 |
| `profit_loss_ratio` | decimal(10,2) | ❌ | 盈亏比 |
| `total_realized_pnl` | decimal(20,6) | ❌ | 总已实现盈亏 |
| `total_fee` | decimal(20,6) | ❌ | 总手续费 |
| `avg_leverage` | decimal(10,2) | ❌ | 平均实际杠杆 |
| `max_leverage` | decimal(10,2) | ❌ | 最大实际杠杆 |
| `avg_margin_utilization` | decimal(5,2) | ❌ | 平均保证金使用率(%) |
| `max_margin_utilization` | decimal(5,2) | ❌ | 最大保证金使用率(%) |
| `coin_concentration` | decimal(5,2) | ❌ | 单币种集中度(%) |
| `liquidation_count` | int | ❌ | 清算次数 |
| `max_drawdown` | decimal(5,2) | ❌ | 最大回撤(%，待实现) |
| `hold_loss_ratio` | decimal(10,2) | ❌ | 死扛指数(亏损持仓时间/盈利持仓时间，待实现) |
| `active_days` | int | ❌ | 活跃天数 |
| `avg_trades_per_day` | decimal(10,2) | ❌ | 日均交易次数 |
| `last_trade_time` | bigint | ❌ | 最后一笔交易时间戳(ms) |
| `liquidation_per_month` | decimal(10,2) | ❌ | 清算次数/月 |
| `has_refill_behavior` | tinyint(1) | ❌ | 是否有补仓行为(0/1) |
| `consecutive_loss_add_count` | int | ❌ | 连续亏损后加仓次数 |
| `add_position_score` | decimal(10,2) | ❌ | 加仓效果得分 |
| `scalping_score` | decimal(10,2) | ❌ | 做T行为得分 |
| `max_consecutive_loss_count` | int | ❌ | 最长连续亏损笔数 |
| `avg_refill_count` | decimal(10,2) | ❌ | **[V3新增]** 平均补仓次数（订单周期平均，四舍五入） |
| `scalping_count` | int | ❌ | **[V3新增]** 做T累计总次数 |
| `is_excluded` | tinyint(1) | ❌ | **[V3新增]** 是否剔除储备池(做T>15或等差规律性补仓) |
| `chase_rate` | decimal(5,2) | ❌ | **[V3新增]** 追涨杀跌率(%) |
| `loss_concentration` | decimal(5,2) | ❌ | **[V3新增]** 单一币种亏损集中度(%) |
| `avg_holding_hours` | decimal(10,2) | ❌ | **[V3新增]** 平均持仓时长(小时) |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| idx_address_time | address | 普通 | - |
| idx_calculated_at | calculated_at | 普通 | - |

---

## 2. hl_address_list

### **表说明**
地址列表

### **表结构**

```sql
CREATE TABLE `hl_address_list` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `label` varchar(100) DEFAULT NULL COMMENT '地址标签/别名',
  `source` varchar(50) DEFAULT 'hyperbot' COMMENT '来源:hyperbot/manual',
  `first_seen_at` datetime NOT NULL COMMENT '首次发现时间',
  `last_updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `status` enum('active','inactive','excluded') DEFAULT 'active' COMMENT '状态',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `address` (`address`),
  KEY `idx_status` (`status`),
  KEY `idx_last_updated` (`last_updated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='地址列表';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `label` | varchar(100) | ❌ | 地址标签/别名 |
| `source` | varchar(50) | ❌ | 来源:hyperbot/manual |
| `first_seen_at` | datetime | ✅ | 首次发现时间 |
| `last_updated_at` | datetime | ✅ | 最后更新时间 |
| `status` | enum('active','inactive','excluded') | ❌ | 状态 |
| `created_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| address | address | 唯一 | - |
| idx_status | status | 普通 | - |
| idx_last_updated | last_updated_at | 普通 | - |

---

## 3. hl_backtest_results

### **表说明**
回测结果

### **表结构**

```sql
CREATE TABLE `hl_backtest_results` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `backtest_name` varchar(100) DEFAULT NULL COMMENT '回测名称/批次',
  `backtest_date` date NOT NULL COMMENT '回测日期',
  `period_start` bigint NOT NULL COMMENT '回测期起始时间戳(ms)',
  `period_end` bigint NOT NULL COMMENT '回测期结束时间戳(ms)',
  `reverse_trade_count` int DEFAULT NULL COMMENT '反向交易次数',
  `reverse_win_rate` decimal(5,2) DEFAULT NULL COMMENT '反向胜率(%)',
  `reverse_total_pnl` decimal(20,6) DEFAULT NULL COMMENT '反向总盈亏',
  `reverse_profit_loss_ratio` decimal(10,2) DEFAULT NULL COMMENT '反向盈亏比',
  `max_drawdown` decimal(5,2) DEFAULT NULL COMMENT '最大回撤(%)',
  `sharpe_ratio` decimal(10,2) DEFAULT NULL COMMENT '夏普比率',
  `classification_stable` tinyint(1) DEFAULT NULL COMMENT '分类是否稳定',
  `avg_score` decimal(10,2) DEFAULT NULL COMMENT '期间平均评分',
  `score_volatility` decimal(10,2) DEFAULT NULL COMMENT '评分波动率',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_address` (`address`),
  KEY `idx_backtest_name` (`backtest_name`),
  KEY `idx_backtest_date` (`backtest_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='回测结果';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `backtest_name` | varchar(100) | ❌ | 回测名称/批次 |
| `backtest_date` | date | ✅ | 回测日期 |
| `period_start` | bigint | ✅ | 回测期起始时间戳(ms) |
| `period_end` | bigint | ✅ | 回测期结束时间戳(ms) |
| `reverse_trade_count` | int | ❌ | 反向交易次数 |
| `reverse_win_rate` | decimal(5,2) | ❌ | 反向胜率(%) |
| `reverse_total_pnl` | decimal(20,6) | ❌ | 反向总盈亏 |
| `reverse_profit_loss_ratio` | decimal(10,2) | ❌ | 反向盈亏比 |
| `max_drawdown` | decimal(5,2) | ❌ | 最大回撤(%) |
| `sharpe_ratio` | decimal(10,2) | ❌ | 夏普比率 |
| `classification_stable` | tinyint(1) | ❌ | 分类是否稳定 |
| `avg_score` | decimal(10,2) | ❌ | 期间平均评分 |
| `score_volatility` | decimal(10,2) | ❌ | 评分波动率 |
| `created_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| idx_address | address | 普通 | - |
| idx_backtest_name | backtest_name | 普通 | - |
| idx_backtest_date | backtest_date | 普通 | - |

---

## 4. hl_fills

### **表说明**
交易历史（原始成交数据）

### **表结构**

```sql
CREATE TABLE `hl_fills` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `coin` varchar(20) NOT NULL COMMENT '币种(可能包含前缀如 xyz:GOLD)',
  `sz` decimal(20,8) NOT NULL COMMENT '成交数量',
  `px` decimal(20,6) NOT NULL COMMENT '成交价格',
  `dir` varchar(20) NOT NULL COMMENT '方向:Open Long/Open Short/Close/Liquidation',
  `closed_pnl` decimal(20,6) DEFAULT '0.000000' COMMENT '已实现盈亏(平仓时)',
  `fee` decimal(20,6) DEFAULT '0.000000' COMMENT '手续费',
  `fee_token` varchar(10) DEFAULT 'USDC' COMMENT '手续费币种',
  `time` bigint NOT NULL COMMENT '成交时间戳(ms)',
  `hash` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '交易哈希',
  `tid` bigint DEFAULT NULL COMMENT '成交ID（唯一标识）',
  `oid` bigint DEFAULT NULL COMMENT '订单ID',
  `twap_id` varchar(100) DEFAULT NULL COMMENT 'TWAP订单ID',
  `side` varchar(5) DEFAULT NULL COMMENT 'A=主动买/B=主动卖',
  `start_position` decimal(20,8) DEFAULT NULL COMMENT '成交前持仓',
  `crossed` tinyint(1) DEFAULT '1' COMMENT '是否全仓模式',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tid` (`tid`),
  KEY `idx_address_time` (`address`,`time` DESC),
  KEY `idx_coin` (`coin`),
  KEY `idx_dir` (`dir`),
  KEY `idx_time` (`time`),
  KEY `idx_oid` (`oid`),
  KEY `idx_hash` (`hash`)
) ENGINE=InnoDB AUTO_INCREMENT=22994 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='交易历史(原始数据)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `coin` | varchar(20) | ✅ | 币种(可能包含前缀如 xyz:GOLD) |
| `sz` | decimal(20,8) | ✅ | 成交数量 |
| `px` | decimal(20,6) | ✅ | 成交价格 |
| `dir` | varchar(20) | ✅ | 方向:Open Long/Open Short/Close/Liquidation |
| `closed_pnl` | decimal(20,6) | ❌ | 已实现盈亏(平仓时) |
| `fee` | decimal(20,6) | ❌ | 手续费 |
| `fee_token` | varchar(10) | ❌ | 手续费币种 |
| `time` | bigint | ✅ | 成交时间戳(ms) |
| `hash` | varchar(100) | ❌ | 交易哈希 |
| `tid` | bigint | ❌ | 成交ID（唯一标识） |
| `oid` | bigint | ❌ | 订单ID |
| `twap_id` | varchar(100) | ❌ | TWAP订单ID |
| `side` | varchar(5) | ❌ | A=主动买/B=主动卖 |
| `start_position` | decimal(20,8) | ❌ | 成交前持仓 |
| `crossed` | tinyint(1) | ❌ | 是否全仓模式 |
| `created_at` | datetime | ✅ | 入库时间 |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| uk_tid | tid | 唯一 | - |
| idx_address_time | address | 普通 | - |
| idx_coin | coin | 普通 | - |
| idx_dir | dir | 普通 | - |
| idx_time | time | 普通 | - |
| idx_oid | oid | 普通 | - |
| idx_hash | hash | 普通 | - |

---

## 4.1 hl_ledger_updates

### **表说明**
非资金费账本流水（`userNonFundingLedgerUpdates`）。用于沉淀地址资金流事件：外部充提、内部转账、账户划转、vault 申购/赎回/分润、借贷与费用等。

### **字段说明（核心）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `address` | varchar(66) | 被采集地址 |
| `time` | bigint | 事件时间戳(ms) |
| `hash` | varchar(100) | 事件哈希 |
| `type` | varchar(50) | 事件类型（见下方 type 字典） |
| `usdc_amount` | decimal(20,6) | 统一 USDC 金额口径（按 type 映射） |
| `sender_address` | varchar(66) | 发送地址（如 `send`） |
| `destination_address` | varchar(66) | 接收地址（如 `send`） |
| `source_dex` | varchar(20) | 资金来源账户类型（spot/perp） |
| `destination_dex` | varchar(20) | 资金去向账户类型（spot/perp） |
| `token` | varchar(20) | 资产符号 |
| `amount` | decimal(20,6) | 原始 token 数量 |
| `usdc_value` | decimal(20,6) | 原始 USDC 估值 |
| `vault_address` | varchar(66) | vault 地址（vault 系事件） |
| `requested_usd` | decimal(20,6) | 请求赎回金额（vaultWithdraw） |
| `net_withdrawn_usd` | decimal(20,6) | 实际净到账金额（vaultWithdraw） |
| `commission` | decimal(20,6) | 佣金金额（vaultLeaderCommission） |
| `operation` | varchar(50) | vault 操作语义字段 |

### **type 字典（分析口径）**

| `type` | 分类 | 资金方向（相对 address） | 备注 |
|------|------|------|------|
| `deposit` | 外部充提 | 流入 | 外部 -> Hyper |
| `withdraw` | 外部充提 | 流出 | Hyper -> 外部 |
| `send` | 内部转账 | 视 sender/destination 判定 | 不计外部净流 |
| `accountClassTransfer` | 内部划转 | 同地址内部重分配 | `spot <-> perp` |
| `spotTransfer` | 内部划转 | 视对手方判定 | 不计外部净流 |
| `vaultCreate` | vault 结构事件 | 视字段判定 | 可伴随初始投入 |
| `vaultDeposit` | vault 申购 | 流出 | 地址 -> vault |
| `vaultWithdraw` | vault 赎回 | 流入 | vault -> 地址 |
| `vaultDistribution` | vault 分润 | 流入 | 收益分配 |
| `vaultLeaderCommission` | vault 佣金 | 常见为 leader 流入 | 费用/分润类 |
| `borrowLend` | 借贷 | 视 token/事件语义 | 内部资金事件 |
| `cStakingTransfer` | staking 划转 | 视 token/事件语义 | 内部资金事件 |
| `accountActivationGas` | 费用 | 流出 | 账户激活 gas |

> 建议维护三套指标：`external_net_flow`（仅 deposit/withdraw）、`internal_flow`（send/transfer/vault）、`vault_pnl_flow`（vaultWithdraw + vaultDistribution - vaultDeposit - vaultLeaderCommission）。

---

## 5. hl_follow_trades

### **表说明**
跟单交易记录

### **表结构**

```sql
CREATE TABLE `hl_follow_trades` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `trade_id` varchar(50) NOT NULL COMMENT '交易ID',
  `signal_id` varchar(50) NOT NULL COMMENT '关联信号ID',
  `source_address` varchar(66) NOT NULL COMMENT '脆弱地址',
  `coin` varchar(20) NOT NULL COMMENT '币种',
  `direction` varchar(20) NOT NULL COMMENT '方向:Long/Short',
  `action` enum('open','add','reduce','close') NOT NULL COMMENT '操作:开仓/加仓/减仓/平仓',
  `size` decimal(20,8) NOT NULL COMMENT '数量',
  `entry_price` decimal(20,6) NOT NULL COMMENT '开仓价',
  `close_price` decimal(20,6) DEFAULT NULL COMMENT '平仓价(如果已平仓)',
  `fee` decimal(20,6) NOT NULL COMMENT '手续费',
  `realized_pnl` decimal(20,6) DEFAULT NULL COMMENT '已实现盈亏(平仓后)',
  `trade_status` enum('open','closed') DEFAULT 'open' COMMENT '交易状态',
  `opened_at` datetime NOT NULL COMMENT '开仓时间',
  `closed_at` datetime DEFAULT NULL COMMENT '平仓时间',
  `original_fill_hash` varchar(100) DEFAULT NULL COMMENT '脆弱地址的原始 fill hash',
  `our_fill_hash` varchar(100) DEFAULT NULL COMMENT '我们的成交 hash',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `trade_id` (`trade_id`),
  KEY `signal_id` (`signal_id`),
  KEY `idx_source_address` (`source_address`),
  KEY `idx_trade_status` (`trade_status`,`coin`),
  KEY `idx_opened_at` (`opened_at` DESC),
  CONSTRAINT `hl_follow_trades_ibfk_1` FOREIGN KEY (`signal_id`) REFERENCES `hl_reverse_signals` (`signal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='跟单交易记录';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `trade_id` | varchar(50) | ✅ | 交易ID |
| `signal_id` | varchar(50) | ✅ | 关联信号ID |
| `source_address` | varchar(66) | ✅ | 脆弱地址 |
| `coin` | varchar(20) | ✅ | 币种 |
| `direction` | varchar(20) | ✅ | 方向:Long/Short |
| `action` | enum('open','add','reduce','close') | ✅ | 操作:开仓/加仓/减仓/平仓 |
| `size` | decimal(20,8) | ✅ | 数量 |
| `entry_price` | decimal(20,6) | ✅ | 开仓价 |
| `close_price` | decimal(20,6) | ❌ | 平仓价(如果已平仓) |
| `fee` | decimal(20,6) | ✅ | 手续费 |
| `realized_pnl` | decimal(20,6) | ❌ | 已实现盈亏(平仓后) |
| `trade_status` | enum('open','closed') | ❌ | 交易状态 |
| `opened_at` | datetime | ✅ | 开仓时间 |
| `closed_at` | datetime | ❌ | 平仓时间 |
| `original_fill_hash` | varchar(100) | ❌ | 脆弱地址的原始 fill hash |
| `our_fill_hash` | varchar(100) | ❌ | 我们的成交 hash |
| `created_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| trade_id | trade_id | 唯一 | - |
| signal_id | signal_id | 普通 | - |
| idx_source_address | source_address | 普通 | - |
| idx_trade_status | trade_status | 普通 | - |
| idx_opened_at | opened_at | 普通 | - |

---

## 6. hl_fragile_pool

> ⚠️ 2026-04-23 重建：粒度从地址级改为**地址+币种级**，新增 `coin`、`total_score` 字段，UNIQUE KEY 改为 `(address, coin)`。

### **表说明**
脆弱地址+币种监控池。每条记录代表一个地址+币种组合，满足入池条件后由 `update_fragile_pool.py` 维护。

### **入池条件**
- 整体评分 L1 或 L2
- `pnl_all_time < 0`（总亏损）
- `pnl_month < 0`（近30天亏损）
- 该币种 `recent_7d_trades > 10`

### **出池条件**
- 评分降至 L3/L4
- 该币种 `recent_7d_trades <= 10`
- 地址 `status = excluded`

### **表结构**

```sql
CREATE TABLE `hl_fragile_pool` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `coin` varchar(20) NOT NULL COMMENT '监控币种',
  `label` varchar(100) DEFAULT NULL COMMENT '地址标签',
  `fragile_level` enum('L1','L2','L3','L4') NOT NULL COMMENT '脆弱等级',
  `total_score` decimal(10,2) DEFAULT NULL COMMENT '入池时整体评分',
  `pool_weight` decimal(5,4) NOT NULL DEFAULT '0.0000' COMMENT '池子权重(0-1)',
  `monitor_status` enum('active','paused','stopped') DEFAULT 'active' COMMENT '监控状态',
  `last_monitored_at` datetime DEFAULT NULL COMMENT '最后监控时间',
  `last_fill_time` bigint DEFAULT NULL COMMENT '最后一笔fill时间戳(ms)',
  `total_signals` int DEFAULT '0' COMMENT '生成信号总数',
  `total_trades` int DEFAULT '0' COMMENT '跟单交易总数',
  `entry_date` date NOT NULL COMMENT '入池日期',
  `entry_score` decimal(10,2) DEFAULT NULL COMMENT '入池时的评分',
  `exit_date` date DEFAULT NULL COMMENT '出池日期(NULL=仍在池中)',
  `exit_reason` varchar(100) DEFAULT NULL COMMENT '出池原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_address_coin` (`address`, `coin`),
  KEY `idx_monitor_status` (`monitor_status`,`last_monitored_at`),
  KEY `idx_level` (`fragile_level`),
  KEY `idx_entry_date` (`entry_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='脆弱地址+币种监控池';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `coin` | varchar(20) | ✅ | 监控币种 |
| `label` | varchar(100) | ❌ | 地址标签 |
| `fragile_level` | enum('L1','L2','L3','L4') | ✅ | 脆弱等级 |
| `total_score` | decimal(10,2) | ❌ | 入池时整体评分 |
| `pool_weight` | decimal(5,4) | ✅ | 池子权重(0-1) |
| `monitor_status` | enum('active','paused','stopped') | ❌ | 监控状态 |
| `last_monitored_at` | datetime | ❌ | 最后监控时间 |
| `last_fill_time` | bigint | ❌ | 最后一笔fill时间戳(ms) |
| `total_signals` | int | ❌ | 生成信号总数 |
| `total_trades` | int | ❌ | 跟单交易总数 |
| `entry_date` | date | ✅ | 入池日期 |
| `entry_score` | decimal(10,2) | ❌ | 入池时的评分 |
| `exit_date` | date | ❌ | 出池日期(NULL=仍在池中) |
| `exit_reason` | varchar(100) | ❌ | 出池原因 |
| `created_at` | datetime | ✅ | - |
| `updated_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| uk_address_coin | (address, coin) | 唯一 | 防重复入池 |
| idx_monitor_status | monitor_status | 普通 | 监控查询 |
| idx_level | fragile_level | 普通 | 等级筛选 |
| idx_entry_date | entry_date | 普通 | 日期查询 |

---

## 6b. hl_pool_change_logs

### **表说明**
地址+币种入池/出池变更日志。每次入池或出池都写一条记录，用于追踪池子变化历史。

### **表结构**

```sql
CREATE TABLE `hl_pool_change_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `coin` varchar(20) NOT NULL COMMENT '币种',
  `action` enum('enter','exit') NOT NULL COMMENT '入池/出池',
  `fragile_level` enum('L1','L2','L3','L4') DEFAULT NULL COMMENT '脆弱等级',
  `total_score` decimal(10,2) DEFAULT NULL COMMENT '当时评分',
  `pnl_all_time` decimal(20,6) DEFAULT NULL COMMENT '总PnL',
  `pnl_month` decimal(20,6) DEFAULT NULL COMMENT '近30天PnL',
  `recent_7d_trades` int DEFAULT NULL COMMENT '近7天该币种交易笔数',
  `reason` varchar(200) DEFAULT NULL COMMENT '入池/出池原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_address_coin` (`address`, `coin`),
  KEY `idx_action_time` (`action`, `created_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址+币种入池/出池日志';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `coin` | varchar(20) | ✅ | 币种 |
| `action` | enum('enter','exit') | ✅ | 入池/出池 |
| `fragile_level` | enum | ❌ | 操作时的脆弱等级 |
| `total_score` | decimal(10,2) | ❌ | 操作时的评分 |
| `pnl_all_time` | decimal(20,6) | ❌ | 入池时的总PnL |
| `pnl_month` | decimal(20,6) | ❌ | 入池时的近30天PnL |
| `recent_7d_trades` | int | ❌ | 操作时近7天该币种交易笔数 |
| `reason` | varchar(200) | ❌ | 入池/出池具体原因 |
| `created_at` | datetime | ✅ | 操作时间 |

---

## 7. hl_fragile_scores

### **表说明**
脆弱地址评分

### **表结构**

```sql
CREATE TABLE `hl_fragile_scores` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `feature_id` bigint DEFAULT NULL COMMENT '关联 hl_address_features.id',
  `scored_at` datetime NOT NULL COMMENT '评分时间',
  `risk_behavior_score` int NOT NULL COMMENT '风险行为评分 /40',
  `loss_feature_score` int NOT NULL COMMENT '亏损特征评分 /35',
  `mentality_score` int NOT NULL COMMENT '心态特征评分 /25',
  `total_score` int NOT NULL COMMENT '总分 /100',
  `fragile_level` enum('L1','L2','L3','L4') DEFAULT NULL COMMENT '脆弱等级',
  `in_pool` tinyint(1) DEFAULT '0' COMMENT '是否入池',
  `pool_weight` decimal(5,4) DEFAULT '0.0000' COMMENT '池子权重',
  `pool_entry_date` date DEFAULT NULL COMMENT '入池日期',
  `pool_exit_date` date DEFAULT NULL COMMENT '出池日期',
  PRIMARY KEY (`id`),
  KEY `feature_id` (`feature_id`),
  KEY `idx_address_time` (`address`,`scored_at` DESC),
  KEY `idx_level_score` (`fragile_level`,`total_score` DESC),
  KEY `idx_in_pool` (`in_pool`,`fragile_level`),
  CONSTRAINT `hl_fragile_scores_ibfk_1` FOREIGN KEY (`feature_id`) REFERENCES `hl_address_features` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='脆弱地址评分';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `feature_id` | bigint | ❌ | 关联 hl_address_features.id |
| `scored_at` | datetime | ✅ | 评分时间 |
| `risk_behavior_score` | int | ✅ | 风险行为评分 /40 |
| `loss_feature_score` | int | ✅ | 亏损特征评分 /35 |
| `mentality_score` | int | ✅ | 心态特征评分 /25 |
| `total_score` | int | ✅ | 总分 /100 |
| `fragile_level` | enum('L1','L2','L3','L4') | ❌ | 脆弱等级 |
| `in_pool` | tinyint(1) | ❌ | 是否入池 |
| `pool_weight` | decimal(5,4) | ❌ | 池子权重 |
| `pool_entry_date` | date | ❌ | 入池日期 |
| `pool_exit_date` | date | ❌ | 出池日期 |
| `trading_behavior_score` | decimal(10,2) | ❌ | 加仓/做T行为得分（可负） |
| `factor1_score` | decimal(5,2) | ❌ | **[V3新增]** 因子一：补仓模式得分（/15） |
| `factor2_score` | decimal(5,2) | ❌ | **[V3新增]** 因子二：综合盈亏得分（/20） |
| `factor3_score` | decimal(5,2) | ❌ | **[V3新增]** 因子三：清算得分（/25） |
| `factor4_score` | decimal(5,2) | ❌ | **[V3新增]** 因子四：追涨杀跌+亏损集中度得分（/20） |
| `factor5_score` | decimal(5,2) | ❌ | **[V3新增]** 因子五：追加保证金得分（暂缓，固定0分） |
| `factor6_score` | decimal(5,2) | ❌ | **[V3新增]** 因子六：平均持仓时长得分（/5） |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| feature_id | feature_id | 普通 | - |
| idx_address_time | address | 普通 | - |
| idx_level_score | fragile_level | 普通 | - |
| idx_in_pool | in_pool | 普通 | - |

---

## 8. hl_monitor_logs

### **表说明**
实时监控日志

### **表结构**

```sql
CREATE TABLE `hl_monitor_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '监控地址',
  `check_time` datetime NOT NULL COMMENT '检查时间',
  `has_new_fills` tinyint(1) NOT NULL COMMENT '是否有新 fills',
  `new_fills_count` int DEFAULT '0' COMMENT '新 fills 数量',
  `signals_generated` int DEFAULT '0' COMMENT '生成信号数量',
  `execution_time_ms` int DEFAULT NULL COMMENT '执行耗时(ms)',
  `error_occurred` tinyint(1) DEFAULT '0' COMMENT '是否发生错误',
  `error_message` text COMMENT '错误信息',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_address_time` (`address`,`check_time` DESC),
  KEY `idx_check_time` (`check_time` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='实时监控日志';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 监控地址 |
| `check_time` | datetime | ✅ | 检查时间 |
| `has_new_fills` | tinyint(1) | ✅ | 是否有新 fills |
| `new_fills_count` | int | ❌ | 新 fills 数量 |
| `signals_generated` | int | ❌ | 生成信号数量 |
| `execution_time_ms` | int | ❌ | 执行耗时(ms) |
| `error_occurred` | tinyint(1) | ❌ | 是否发生错误 |
| `error_message` | text | ❌ | 错误信息 |
| `created_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| idx_address_time | address | 普通 | - |
| idx_check_time | check_time | 普通 | - |

---

## 9. hl_position_details

### **表说明**
持仓明细

### **表结构**

```sql
CREATE TABLE `hl_position_details` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `snapshot_id` bigint NOT NULL COMMENT '关联 hl_position_snapshots.id',
  `coin` varchar(20) NOT NULL COMMENT '币种',
  `szi` decimal(20,8) NOT NULL COMMENT '持仓数量(正=多,负=空)',
  `entry_px` decimal(20,6) NOT NULL COMMENT '开仓均价',
  `position_value` decimal(20,6) NOT NULL COMMENT '仓位价值',
  `unrealized_pnl` decimal(20,6) DEFAULT '0.000000' COMMENT '未实现盈亏',
  `return_on_equity` decimal(10,6) DEFAULT '0.000000' COMMENT 'ROE',
  `liquidation_px` decimal(20,6) DEFAULT NULL COMMENT '清算价',
  `margin_used` decimal(20,6) DEFAULT NULL COMMENT '占用保证金',
  `leverage_type` varchar(20) DEFAULT NULL COMMENT '杠杆类型:cross/isolated',
  `leverage_value` int DEFAULT NULL COMMENT '杠杆倍数',
  `max_leverage` int DEFAULT NULL COMMENT '最大杠杆',
  `cum_funding_all_time` decimal(20,6) DEFAULT NULL COMMENT '历史累计资金费',
  `cum_funding_since_open` decimal(20,6) DEFAULT NULL COMMENT '开仓后累计资金费',
  PRIMARY KEY (`id`),
  KEY `idx_snapshot_coin` (`snapshot_id`,`coin`),
  KEY `idx_coin` (`coin`),
  CONSTRAINT `hl_position_details_ibfk_1` FOREIGN KEY (`snapshot_id`) REFERENCES `hl_position_snapshots` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='持仓明细(每个快照的持仓列表)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `snapshot_id` | bigint | ✅ | 关联 hl_position_snapshots.id |
| `coin` | varchar(20) | ✅ | 币种 |
| `szi` | decimal(20,8) | ✅ | 持仓数量(正=多,负=空) |
| `entry_px` | decimal(20,6) | ✅ | 开仓均价 |
| `position_value` | decimal(20,6) | ✅ | 仓位价值 |
| `unrealized_pnl` | decimal(20,6) | ❌ | 未实现盈亏 |
| `return_on_equity` | decimal(10,6) | ❌ | ROE |
| `liquidation_px` | decimal(20,6) | ❌ | 清算价 |
| `margin_used` | decimal(20,6) | ❌ | 占用保证金 |
| `leverage_type` | varchar(20) | ❌ | 杠杆类型:cross/isolated |
| `leverage_value` | int | ❌ | 杠杆倍数 |
| `max_leverage` | int | ❌ | 最大杠杆 |
| `cum_funding_all_time` | decimal(20,6) | ❌ | 历史累计资金费 |
| `cum_funding_since_open` | decimal(20,6) | ❌ | 开仓后累计资金费 |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| idx_snapshot_coin | snapshot_id | 普通 | - |
| idx_coin | coin | 普通 | - |

---

## 10. hl_position_snapshots

### **表说明**
持仓快照（汇总）

### **表结构**

```sql
CREATE TABLE `hl_position_snapshots` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `snapshot_time` bigint NOT NULL COMMENT 'API 返回的时间戳(ms)',
  `snapshot_date` date DEFAULT NULL COMMENT '快照日期（代表哪一天的数据）',
  `account_value` decimal(20,6) NOT NULL COMMENT '账户价值',
  `total_margin_used` decimal(20,6) NOT NULL COMMENT '已用保证金',
  `total_raw_usd` decimal(20,6) DEFAULT NULL COMMENT '钱包余额 / USD 净余额（可为负，全部充值-全部提现-资金费用净利润等）',
  `total_ntl_pos` decimal(20,6) DEFAULT NULL COMMENT '总名义持仓价值',
  `withdrawable` decimal(20,6) DEFAULT NULL COMMENT '可提现金额',
  `pnl_day` decimal(20,6) DEFAULT NULL COMMENT '当日盈亏 (USDC)',
  `pnl_week` decimal(20,6) DEFAULT NULL COMMENT '本周盈亏 (USDC)',
  `pnl_month` decimal(20,6) DEFAULT NULL COMMENT '本月盈亏 (USDC)',
  `pnl_all_time` decimal(20,6) DEFAULT NULL COMMENT '历史总盈亏 (USDC)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_address_time` (`address`,`snapshot_time`),
  KEY `idx_address_time` (`address`,`snapshot_time` DESC),
  KEY `idx_snapshot_time` (`snapshot_time`),
  KEY `idx_snapshot_date` (`snapshot_date`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='持仓快照(汇总)';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `address` | varchar(66) | ✅ | 钱包地址 |
| `snapshot_time` | bigint | ✅ | API 返回的时间戳(ms) |
| `snapshot_date` | date | ❌ | 快照日期（代表哪一天的数据） |
| `account_value` | decimal(20,6) | ✅ | 账户价值 |
| `total_margin_used` | decimal(20,6) | ✅ | 已用保证金 |
| `total_raw_usd` | decimal(20,6) | ❌ | 钱包余额 / USD 净余额（可为负，全部充值-全部提现-资金费用净利润等） |
| `total_ntl_pos` | decimal(20,6) | ❌ | 总名义持仓价值 |
| `withdrawable` | decimal(20,6) | ❌ | 可提现金额 |
| `pnl_day` | decimal(20,6) | ❌ | 当日盈亏 (USDC) |
| `pnl_week` | decimal(20,6) | ❌ | 本周盈亏 (USDC) |
| `pnl_month` | decimal(20,6) | ❌ | 本月盈亏 (USDC) |
| `pnl_all_time` | decimal(20,6) | ❌ | 历史总盈亏 (USDC) |
| `created_at` | datetime | ✅ | 入库时间 |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| uk_address_time | address | 唯一 | - |
| idx_address_time | address | 普通 | - |
| idx_snapshot_time | snapshot_time | 普通 | - |
| idx_snapshot_date | snapshot_date | 普通 | - |

---

## 11. hl_reverse_signals

### **表说明**
反向跟单信号

### **表结构**

```sql
CREATE TABLE `hl_reverse_signals` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `signal_id` varchar(50) NOT NULL COMMENT '信号ID(防重复)',
  `source_address` varchar(66) NOT NULL COMMENT '脆弱地址',
  `signal_type` enum('new_position','add_position','close_position','liquidation') NOT NULL COMMENT '信号类型',
  `coin` varchar(20) NOT NULL COMMENT '币种',
  `original_direction` varchar(20) NOT NULL COMMENT '脆弱地址的操作方向',
  `original_size` decimal(20,8) NOT NULL COMMENT '脆弱地址的操作数量',
  `original_price` decimal(20,6) NOT NULL COMMENT '脆弱地址的成交价',
  `original_fill_time` bigint NOT NULL COMMENT '脆弱地址的成交时间戳(ms)',
  `reverse_direction` varchar(20) NOT NULL COMMENT '反向操作方向',
  `reverse_size` decimal(20,8) NOT NULL COMMENT '反向操作建议数量',
  `reverse_weight` decimal(5,4) NOT NULL COMMENT '信号权重(基于地址权重)',
  `signal_status` enum('pending','executed','cancelled','expired') DEFAULT 'pending' COMMENT '信号状态',
  `generated_at` datetime NOT NULL COMMENT '生成时间',
  `executed_at` datetime DEFAULT NULL COMMENT '执行时间',
  `cancel_reason` varchar(200) DEFAULT NULL COMMENT '取消原因',
  `executed_price` decimal(20,6) DEFAULT NULL COMMENT '实际成交价',
  `executed_size` decimal(20,8) DEFAULT NULL COMMENT '实际成交量',
  `slippage` decimal(10,6) DEFAULT NULL COMMENT '滑点(%)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `signal_id` (`signal_id`),
  KEY `idx_source_address` (`source_address`,`generated_at` DESC),
  KEY `idx_signal_status` (`signal_status`,`generated_at` DESC),
  KEY `idx_coin` (`coin`),
  KEY `idx_generated_at` (`generated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='反向跟单信号';
```

### **字段说明**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | bigint | ✅ | - |
| `signal_id` | varchar(50) | ✅ | 信号ID(防重复) |
| `source_address` | varchar(66) | ✅ | 脆弱地址 |
| `signal_type` | enum('new_position','add_position','close_position','liquidation') | ✅ | 信号类型 |
| `coin` | varchar(20) | ✅ | 币种 |
| `original_direction` | varchar(20) | ✅ | 脆弱地址的操作方向 |
| `original_size` | decimal(20,8) | ✅ | 脆弱地址的操作数量 |
| `original_price` | decimal(20,6) | ✅ | 脆弱地址的成交价 |
| `original_fill_time` | bigint | ✅ | 脆弱地址的成交时间戳(ms) |
| `reverse_direction` | varchar(20) | ✅ | 反向操作方向 |
| `reverse_size` | decimal(20,8) | ✅ | 反向操作建议数量 |
| `reverse_weight` | decimal(5,4) | ✅ | 信号权重(基于地址权重) |
| `signal_status` | enum('pending','executed','cancelled','expired') | ❌ | 信号状态 |
| `generated_at` | datetime | ✅ | 生成时间 |
| `executed_at` | datetime | ❌ | 执行时间 |
| `cancel_reason` | varchar(200) | ❌ | 取消原因 |
| `executed_price` | decimal(20,6) | ❌ | 实际成交价 |
| `executed_size` | decimal(20,8) | ❌ | 实际成交量 |
| `slippage` | decimal(10,6) | ❌ | 滑点(%) |
| `created_at` | datetime | ✅ | - |

### **索引**

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | id | 唯一 | - |
| signal_id | signal_id | 唯一 | - |
| idx_source_address | source_address | 普通 | - |
| idx_signal_status | signal_status | 普通 | - |
| idx_coin | coin | 普通 | - |
| idx_generated_at | generated_at | 普通 | - |

---

## 视图: v_order_summary

```sql
CREATE ALGORITHM=UNDEFINED DEFINER=`admin`@`%` SQL SECURITY DEFINER VIEW `v_order_summary` AS select `hl_fills`.`address` AS `address`,`hl_fills`.`oid` AS `oid`,`hl_fills`.`hash` AS `hash`,`hl_fills`.`coin` AS `coin`,`hl_fills`.`dir` AS `dir`,count(0) AS `fill_count`,sum(`hl_fills`.`sz`) AS `total_sz`,avg(`hl_fills`.`px`) AS `avg_px`,sum(`hl_fills`.`fee`) AS `total_fee`,sum(`hl_fills`.`closed_pnl`) AS `total_pnl`,min(`hl_fills`.`time`) AS `first_fill_time`,max(`hl_fills`.`time`) AS `last_fill_time`,min(`hl_fills`.`start_position`) AS `start_position`,(min(`hl_fills`.`start_position`) + (case when (`hl_fills`.`dir` like '%Long') then sum(`hl_fills`.`sz`) when (`hl_fills`.`dir` like '%Short') then -(sum(`hl_fills`.`sz`)) else 0 end)) AS `end_position`,max(`hl_fills`.`crossed`) AS `is_crossed` from `hl_fills` group by `hl_fills`.`address`,`hl_fills`.`oid`,`hl_fills`.`hash`,`hl_fills`.`coin`,`hl_fills`.`dir`;
```

---

## 📝 维护日志

### 2026-04-09
- ✅ 从数据库自动同步表结构

---

**最后更新**: 2026-04-09