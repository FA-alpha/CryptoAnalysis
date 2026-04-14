-- ============================================
-- 脆弱地址模型 V3.0 - 含异常币种过滤
-- 日期: 2026-04-14
-- ============================================

-- =====================
-- 1. 创建 V3 脆弱池（排除异常币种地址）
-- =====================

DROP TABLE IF EXISTS hl_fragile_pool_v3;

CREATE TABLE hl_fragile_pool_v3 AS
SELECT p.*
FROM hl_fragile_pool_dev1 p
WHERE p.address COLLATE utf8mb4_unicode_ci NOT IN (
    -- 排除异常币种交易占比 > 50% 的地址
    SELECT address COLLATE utf8mb4_unicode_ci
    FROM (
        SELECT 
            address,
            SUM(CASE WHEN coin LIKE '@%' OR coin LIKE 'cash:%' OR coin LIKE 'xyz:%' THEN 1 ELSE 0 END) / COUNT(*) as abnormal_ratio
        FROM hl_fills
        GROUP BY address
    ) t
    WHERE abnormal_ratio > 0.5
);

-- =====================
-- 2. 添加正常币种交易占比列
-- =====================

ALTER TABLE hl_fragile_pool_v3 ADD COLUMN normal_coin_ratio DECIMAL(5,4);

UPDATE hl_fragile_pool_v3 p
JOIN (
    SELECT 
        address,
        1 - SUM(CASE WHEN coin LIKE '@%' OR coin LIKE 'cash:%' OR coin LIKE 'xyz:%' THEN 1 ELSE 0 END) / COUNT(*) as normal_ratio
    FROM hl_fills
    GROUP BY address
) t ON p.address COLLATE utf8mb4_unicode_ci = t.address COLLATE utf8mb4_unicode_ci
SET p.normal_coin_ratio = t.normal_ratio;

-- =====================
-- 3. 添加索引
-- =====================

ALTER TABLE hl_fragile_pool_v3 ADD PRIMARY KEY (address);
ALTER TABLE hl_fragile_pool_v3 ADD INDEX idx_level (fragile_level);
ALTER TABLE hl_fragile_pool_v3 ADD INDEX idx_score (fragile_score);
ALTER TABLE hl_fragile_pool_v3 ADD INDEX idx_type (fragile_type);

-- =====================
-- 4. 统计验证
-- =====================

-- 4.1 各层级分布
SELECT 
    fragile_level,
    COUNT(*) as count,
    ROUND(AVG(total_pnl), 0) as avg_pnl,
    ROUND(AVG(normal_coin_ratio), 3) as avg_normal_ratio
FROM hl_fragile_pool_v3
GROUP BY fragile_level
ORDER BY fragile_level;

-- 4.2 脆弱类型分布
SELECT 
    fragile_type,
    COUNT(*) as count,
    ROUND(AVG(total_pnl), 0) as avg_pnl
FROM hl_fragile_pool_v3
GROUP BY fragile_type
ORDER BY avg_pnl;

-- 4.3 异常币种过滤效果
SELECT 
    'V2.0 (dev1)' as version,
    COUNT(*) as total,
    SUM(CASE WHEN fragile_level = 'L4' THEN 1 ELSE 0 END) as L4,
    SUM(CASE WHEN fragile_level = 'L3' THEN 1 ELSE 0 END) as L3,
    SUM(CASE WHEN fragile_level = 'L2' THEN 1 ELSE 0 END) as L2
FROM hl_fragile_pool_dev1
UNION ALL
SELECT 
    'V3.0 (filtered)' as version,
    COUNT(*) as total,
    SUM(CASE WHEN fragile_level = 'L4' THEN 1 ELSE 0 END) as L4,
    SUM(CASE WHEN fragile_level = 'L3' THEN 1 ELSE 0 END) as L3,
    SUM(CASE WHEN fragile_level = 'L2' THEN 1 ELSE 0 END) as L2
FROM hl_fragile_pool_v3;

-- =====================
-- 5. 常用查询
-- =====================

-- 5.1 获取高危脆弱地址
-- SELECT address, fragile_score, fragile_type, total_pnl
-- FROM hl_fragile_pool_v3
-- WHERE fragile_level = 'L4'
-- ORDER BY fragile_score DESC;

-- 5.2 获取「死扛+加仓」型地址
-- SELECT *
-- FROM hl_fragile_pool_v3
-- WHERE fragile_type = 'stubborn_adder'
-- ORDER BY total_pnl ASC;

-- 5.3 排除的地址（异常币种交易占比>50%）
-- SELECT 
--     address,
--     abnormal_ratio,
--     total_trades
-- FROM (
--     SELECT 
--         address,
--         SUM(CASE WHEN coin LIKE '@%' OR coin LIKE 'cash:%' OR coin LIKE 'xyz:%' THEN 1 ELSE 0 END) / COUNT(*) as abnormal_ratio,
--         COUNT(*) as total_trades
--     FROM hl_fills
--     GROUP BY address
-- ) t
-- WHERE abnormal_ratio > 0.5
-- ORDER BY abnormal_ratio DESC;
