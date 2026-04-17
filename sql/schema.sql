-- ============================================================
-- CryptoAnalysis - fourieralpha_hl 数据库 Schema
-- 自动从数据库同步生成
-- 最后更新: 2026-04-09
-- ============================================================

CREATE DATABASE IF NOT EXISTS `fourieralpha_hl` DEFAULT CHARACTER SET utf8mb4;

USE `fourieralpha_hl`;

-- Table: hl_address_features
DROP TABLE IF EXISTS `hl_address_features`;
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
  `max_drawdown` decimal(5,2) DEFAULT NULL COMMENT '最大回撤(%，待实现)',
  `hold_loss_ratio` decimal(10,2) DEFAULT NULL COMMENT '死扛指数(亏损持仓时间/盈利持仓时间，待实现)',
  `active_days` int DEFAULT NULL COMMENT '活跃天数',
  `avg_trades_per_day` decimal(10,2) DEFAULT NULL COMMENT '日均交易次数',
  `last_trade_time` bigint DEFAULT NULL COMMENT '最后一笔交易时间戳(ms)',
  `liquidation_per_month` decimal(10,2) DEFAULT NULL COMMENT '清算次数/月',
  `has_refill_behavior` tinyint(1) DEFAULT '0' COMMENT '是否有后续补仓行为',
  `consecutive_loss_add_count` int DEFAULT '0' COMMENT '连续亏损后加仓次数',
  `add_position_score` decimal(10,2) DEFAULT '0.00' COMMENT '加仓效果得分（可负）',
  `scalping_score` decimal(10,2) DEFAULT '0.00' COMMENT '做T行为得分（可负）',
  `max_consecutive_loss_count` int DEFAULT '0' COMMENT '最长连续亏损笔数',
  `avg_refill_count` decimal(10,2) DEFAULT NULL COMMENT '平均补仓次数',
  `scalping_count` int DEFAULT NULL COMMENT '做T累计总次数',
  `is_excluded` tinyint(1) DEFAULT '0' COMMENT '是否剔除储备池',
  `chase_rate` decimal(5,2) DEFAULT NULL COMMENT '追涨杀跌率(%)',
  `loss_concentration` decimal(5,2) DEFAULT NULL COMMENT '单一币种亏损集中度(%)',
  `avg_holding_hours` decimal(10,2) DEFAULT NULL COMMENT '平均持仓时长(小时)',
  `margin_call_count` int DEFAULT '0' COMMENT '追加保证金次数',
  `recent_7d_trades` int NOT NULL DEFAULT '0' COMMENT '近7天白名单币种交易笔数（Close）',
  PRIMARY KEY (`id`),
  KEY `idx_address_time` (`address`,`calculated_at` DESC),
  KEY `idx_calculated_at` (`calculated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='地址特征(计算结果)';

-- Table: hl_address_list
DROP TABLE IF EXISTS `hl_address_list`;
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

-- Table: hl_backtest_results
DROP TABLE IF EXISTS `hl_backtest_results`;
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

-- Table: hl_fills
DROP TABLE IF EXISTS `hl_fills`;
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

-- Table: hl_follow_trades
DROP TABLE IF EXISTS `hl_follow_trades`;
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

-- Table: hl_fragile_pool
DROP TABLE IF EXISTS `hl_fragile_pool`;
CREATE TABLE `hl_fragile_pool` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `label` varchar(100) DEFAULT NULL COMMENT '地址标签',
  `fragile_level` enum('L1','L2','L3','L4') NOT NULL COMMENT '脆弱等级',
  `pool_weight` decimal(5,4) NOT NULL DEFAULT '0.0000' COMMENT '池子权重(0-1)',
  `monitor_status` enum('active','paused','stopped') DEFAULT 'active' COMMENT '监控状态',
  `last_monitored_at` datetime DEFAULT NULL COMMENT '最后监控时间',
  `last_fill_time` bigint DEFAULT NULL COMMENT '最后一笔 fill 时间戳(ms,用于增量获取)',
  `total_signals` int DEFAULT '0' COMMENT '生成信号总数',
  `total_trades` int DEFAULT '0' COMMENT '跟单交易总数',
  `entry_date` date NOT NULL COMMENT '入池日期',
  `entry_score` int DEFAULT NULL COMMENT '入池时的评分',
  `exit_date` date DEFAULT NULL COMMENT '出池日期(NULL=仍在池中)',
  `exit_reason` varchar(100) DEFAULT NULL COMMENT '出池原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `address` (`address`),
  KEY `idx_monitor_status` (`monitor_status`,`last_monitored_at`),
  KEY `idx_level` (`fragile_level`),
  KEY `idx_entry_date` (`entry_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='脆弱地址池(实时监控)';

-- Table: hl_fragile_scores
DROP TABLE IF EXISTS `hl_fragile_scores`;
CREATE TABLE `hl_fragile_scores` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `address` varchar(66) NOT NULL COMMENT '钱包地址',
  `feature_id` bigint DEFAULT NULL COMMENT '关联 hl_address_features.id',
  `scored_at` datetime NOT NULL COMMENT '评分时间',
  `total_score` decimal(10,2) NOT NULL COMMENT '总分（可超100，可为负）',
  `fragile_level` enum('L1','L2','L3','L4') DEFAULT NULL COMMENT '脆弱等级 L1≥85/L2≥70/L3≥50/L4<50',
  `factor1_score` decimal(5,2) DEFAULT NULL COMMENT '因子一：补仓模式 /15',
  `factor2_score` decimal(5,2) DEFAULT NULL COMMENT '因子二：综合盈亏 /20',
  `factor3_score` decimal(5,2) DEFAULT NULL COMMENT '因子三：清算 /25',
  `factor4_score` decimal(5,2) DEFAULT NULL COMMENT '因子四：追涨杀跌+亏损集中度 /20',
  `factor5_score` decimal(5,2) DEFAULT '0.00' COMMENT '因子五：追加保证金 /20',
  `factor6_score` decimal(5,2) DEFAULT NULL COMMENT '因子六：平均持仓时长 /5',
  PRIMARY KEY (`id`),
  KEY `feature_id` (`feature_id`),
  KEY `idx_address_time` (`address`,`scored_at` DESC),
  KEY `idx_level_score` (`fragile_level`,`total_score` DESC),
  CONSTRAINT `hl_fragile_scores_ibfk_1` FOREIGN KEY (`feature_id`) REFERENCES `hl_address_features` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='脆弱地址评分(v2)';

-- Table: hl_monitor_logs
DROP TABLE IF EXISTS `hl_monitor_logs`;
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

-- Table: hl_position_details
DROP TABLE IF EXISTS `hl_position_details`;
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

-- Table: hl_position_snapshots
DROP TABLE IF EXISTS `hl_position_snapshots`;
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

-- Table: hl_reverse_signals
DROP TABLE IF EXISTS `hl_reverse_signals`;
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

-- View: v_order_summary
CREATE ALGORITHM=UNDEFINED DEFINER=`admin`@`%` SQL SECURITY DEFINER VIEW `v_order_summary` AS select `hl_fills`.`address` AS `address`,`hl_fills`.`oid` AS `oid`,`hl_fills`.`hash` AS `hash`,`hl_fills`.`coin` AS `coin`,`hl_fills`.`dir` AS `dir`,count(0) AS `fill_count`,sum(`hl_fills`.`sz`) AS `total_sz`,avg(`hl_fills`.`px`) AS `avg_px`,sum(`hl_fills`.`fee`) AS `total_fee`,sum(`hl_fills`.`closed_pnl`) AS `total_pnl`,min(`hl_fills`.`time`) AS `first_fill_time`,max(`hl_fills`.`time`) AS `last_fill_time`,min(`hl_fills`.`start_position`) AS `start_position`,(min(`hl_fills`.`start_position`) + (case when (`hl_fills`.`dir` like '%Long') then sum(`hl_fills`.`sz`) when (`hl_fills`.`dir` like '%Short') then -(sum(`hl_fills`.`sz`)) else 0 end)) AS `end_position`,max(`hl_fills`.`crossed`) AS `is_crossed` from `hl_fills` group by `hl_fills`.`address`,`hl_fills`.`oid`,`hl_fills`.`hash`,`hl_fills`.`coin`,`hl_fills`.`dir`;
