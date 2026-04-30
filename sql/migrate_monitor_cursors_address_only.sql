-- ============================================================
-- 将 hl_monitor_cursors 从 address+coin 迁移到 address-only
-- 版本: v0.2.3
-- 日期: 2026-04-29
-- ============================================================

-- 说明：
--   - 目标表仅保留 address，last_fill_time 取同一 address 下的 MAX(last_fill_time)
--   - 你当前表预计为空，但这里做了保底数据合并

START TRANSACTION;

-- 1) 创建新表（address-only）
CREATE TABLE IF NOT EXISTS `hl_monitor_cursors_new` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `address` VARCHAR(66) NOT NULL COMMENT '钱包地址',
  `last_fill_time` BIGINT DEFAULT NULL COMMENT '最后处理的时间戳(ms)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_address` (`address`),
  KEY `idx_last_fill_time` (`last_fill_time`),
  KEY `idx_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='全局监控游标（address）';

-- 2) 将旧表数据合并写入新表（按地址取最大 last_fill_time）
INSERT INTO `hl_monitor_cursors_new` (`address`, `last_fill_time`)
SELECT
  `address`,
  MAX(`last_fill_time`) AS last_fill_time
FROM `hl_monitor_cursors`
GROUP BY `address`
ON DUPLICATE KEY UPDATE
  `last_fill_time` = GREATEST(`hl_monitor_cursors_new`.`last_fill_time`, VALUES(`last_fill_time`));

-- 3) 替换旧表
DROP TABLE `hl_monitor_cursors`;
RENAME TABLE `hl_monitor_cursors_new` TO `hl_monitor_cursors`;

COMMIT;

