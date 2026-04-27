-- ============================================================
-- 策略系统迁移脚本
-- 版本: v0.2.0
-- 日期: 2026-04-27
-- ============================================================

-- ── 新表 1：hl_strategies（策略配置持久化）──────────────────
CREATE TABLE IF NOT EXISTS `hl_strategies` (
  `id`            BIGINT NOT NULL AUTO_INCREMENT,
  `strategy_id`   VARCHAR(64) NOT NULL COMMENT '外部传入的策略ID，唯一',
  `name`          VARCHAR(100) NOT NULL COMMENT '策略名称',
  `description`   VARCHAR(500) DEFAULT NULL COMMENT '策略描述',
  `status`        ENUM('active','stopped') NOT NULL DEFAULT 'active' COMMENT '策略状态',
  `filter_params` JSON NOT NULL COMMENT '筛选参数快照',
  `address_count` INT NOT NULL DEFAULT 0 COMMENT '当前监控地址+币种对数量',
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次创建时间',
  `updated_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `started_at`    DATETIME NOT NULL COMMENT '最后一次启动时间',
  `stopped_at`    DATETIME DEFAULT NULL COMMENT '最后一次停止时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_strategy_id` (`strategy_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='策略配置表';

-- ── 新表 2：hl_strategy_addresses（策略↔地址+币种关联）──────
CREATE TABLE IF NOT EXISTS `hl_strategy_addresses` (
  `id`             BIGINT NOT NULL AUTO_INCREMENT,
  `strategy_id`    VARCHAR(64) NOT NULL COMMENT '关联策略ID',
  `address`        VARCHAR(66) NOT NULL COMMENT '钱包地址',
  `coin`           VARCHAR(20) NOT NULL COMMENT '监控币种',
  `score`          DECIMAL(5,2) DEFAULT NULL COMMENT '加入时的评分快照',
  `level`          CHAR(2) DEFAULT NULL COMMENT '加入时的等级快照 L1/L2/L3/L4',
  `included_at`    DATETIME NOT NULL COMMENT '加入监控时间',
  `excluded_at`    DATETIME DEFAULT NULL COMMENT '移出时间（NULL=当前有效）',
  `exclude_reason` VARCHAR(100) DEFAULT NULL COMMENT '移出原因: score_drop/filter_change/strategy_stopped/manual',
  `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_strategy_address_coin` (`strategy_id`, `address`, `coin`),
  KEY `idx_strategy_active` (`strategy_id`, `excluded_at`),
  KEY `idx_address_coin` (`address`, `coin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='策略监控地址+币种关联表';

-- ── 修改现有表：hl_reverse_signals 加 strategy_id ──────────
ALTER TABLE `hl_reverse_signals`
  ADD COLUMN `strategy_id` VARCHAR(64) DEFAULT NULL COMMENT '关联策略ID' AFTER `signal_id`,
  ADD KEY `idx_strategy_id` (`strategy_id`);

-- ── 修改现有表：hl_follow_trades 加 strategy_id ─────────────
ALTER TABLE `hl_follow_trades`
  ADD COLUMN `strategy_id` VARCHAR(64) DEFAULT NULL COMMENT '关联策略ID' AFTER `signal_id`,
  ADD KEY `idx_strategy_id` (`strategy_id`);
