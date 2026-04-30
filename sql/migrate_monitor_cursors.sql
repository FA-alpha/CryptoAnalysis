-- ============================================================
-- 新增全局监控游标表（address 维度）
-- 版本: v0.2.3
-- 日期: 2026-04-29
-- ============================================================

CREATE TABLE IF NOT EXISTS `hl_monitor_cursors` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `address` VARCHAR(66) NOT NULL COMMENT '钱包地址',
  `last_fill_time` BIGINT DEFAULT NULL COMMENT '最后处理的 fill 时间戳(ms)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_address` (`address`),
  KEY `idx_last_fill_time` (`last_fill_time`),
  KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='全局监控游标（address）';
