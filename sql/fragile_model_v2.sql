-- ============================================================
-- 脆弱地址建模 V2.0 - SQL 实现
-- 数据库: fourieralpha_hl
-- 创建时间: 2026-04-14
-- ============================================================

-- ------------------------------------------------------------
-- Step 1: 创建特征计算表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS hl_fragile_model_dev1;

CREATE TABLE hl_fragile_model_dev1 AS
SELECT 
    af.address,
    af.total_realized_pnl,
    af.total_fee,
    af.liquidation_count,
    af.win_rate,
    af.active_days,
    af.max_leverage,
    af.coin_concentration,
    
    -- 1. 止盈止损比 (最强预测指标)
    t.avg_win,
    t.avg_loss,
    t.avg_win / NULLIF(t.avg_loss, 0.01) as discipline_ratio,
    
    -- 2. 交易频率和规模
    t.total_trades,
    t.fills_per_day,
    t.avg_trade_value,
    
    -- 3. 清算详情
    t.liq_cross_count,
    t.liq_isolated_count,
    t.adl_count,
    t.liq_cross_count * 15 + t.liq_isolated_count * 10 + t.adl_count * 5 as liq_severity_score,
    
    -- 4. 单笔最大亏损
    t.max_single_loss,
    t.total_loss,
    t.max_single_loss / NULLIF(t.total_loss, 0.01) as max_single_loss_ratio,
    
    -- 5. 多空偏好
    t.long_ratio,
    
    -- 6. 加仓行为
    t.add_position_count,
    t.new_position_count,
    t.add_position_count / NULLIF(t.add_position_count + t.new_position_count, 0) as add_position_ratio

FROM hl_address_features af
JOIN (
    SELECT 
        address,
        COUNT(*) as total_trades,
        COUNT(*) / NULLIF(COUNT(DISTINCT DATE(FROM_UNIXTIME(time/1000))), 0) as fills_per_day,
        AVG(ABS(sz * px)) as avg_trade_value,
        
        -- 止盈止损
        AVG(CASE WHEN closed_pnl > 0 THEN closed_pnl ELSE NULL END) as avg_win,
        AVG(CASE WHEN closed_pnl < 0 THEN ABS(closed_pnl) ELSE NULL END) as avg_loss,
        
        -- 清算分类
        SUM(CASE WHEN dir LIKE 'Liquidated Cross%' THEN 1 ELSE 0 END) as liq_cross_count,
        SUM(CASE WHEN dir LIKE 'Liquidated Isolated%' THEN 1 ELSE 0 END) as liq_isolated_count,
        SUM(CASE WHEN dir = 'Auto-Deleveraging' THEN 1 ELSE 0 END) as adl_count,
        
        -- 单笔最大亏损
        MIN(closed_pnl) as max_single_loss,
        SUM(CASE WHEN closed_pnl < 0 THEN closed_pnl ELSE 0 END) as total_loss,
        
        -- 多空偏好
        SUM(CASE WHEN dir LIKE '%Long%' OR dir = 'Buy' THEN 1 ELSE 0 END) / COUNT(*) as long_ratio,
        
        -- 加仓行为
        SUM(CASE WHEN dir LIKE 'Open%' AND start_position != 0 THEN 1 ELSE 0 END) as add_position_count,
        SUM(CASE WHEN dir LIKE 'Open%' AND start_position = 0 THEN 1 ELSE 0 END) as new_position_count
        
    FROM hl_fills
    GROUP BY address
    HAVING COUNT(*) >= 50  -- 至少50笔交易才有统计意义
) t ON af.address = t.address;

-- ------------------------------------------------------------
-- Step 2: 添加分类字段
-- ------------------------------------------------------------
ALTER TABLE hl_fragile_model_dev1 
ADD COLUMN trading_style VARCHAR(20),
ADD COLUMN discipline_type VARCHAR(20),
ADD COLUMN direction_bias_type VARCHAR(20),
ADD COLUMN add_behavior_type VARCHAR(20),
ADD COLUMN fragile_score INT DEFAULT 0,
ADD COLUMN fragile_type VARCHAR(50),
ADD COLUMN fragile_level VARCHAR(10),
ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- 添加索引
ALTER TABLE hl_fragile_model_dev1 ADD PRIMARY KEY (address);
ALTER TABLE hl_fragile_model_dev1 ADD INDEX idx_fragile_score (fragile_score);
ALTER TABLE hl_fragile_model_dev1 ADD INDEX idx_fragile_level (fragile_level);
ALTER TABLE hl_fragile_model_dev1 ADD INDEX idx_fragile_type (fragile_type);

-- ------------------------------------------------------------
-- Step 3: 填充分类标签
-- ------------------------------------------------------------
UPDATE hl_fragile_model_dev1 SET
    -- 交易风格
    trading_style = CASE 
        WHEN fills_per_day >= 40 AND avg_trade_value >= 5000 THEN 'quant_bot'
        WHEN fills_per_day >= 40 THEN 'scalper'
        WHEN fills_per_day < 10 AND avg_trade_value >= 10000 THEN 'all_in'
        ELSE 'retail'
    END,
    
    -- 纪律类型
    discipline_type = CASE 
        WHEN discipline_ratio >= 2.0 THEN 'disciplined'
        WHEN discipline_ratio >= 1.0 THEN 'normal'
        WHEN discipline_ratio >= 0.5 THEN 'weak'
        WHEN discipline_ratio >= 0.3 THEN 'poor'
        ELSE 'stubborn'
    END,
    
    -- 方向偏好
    direction_bias_type = CASE 
        WHEN long_ratio > 0.8 THEN 'extreme_long'
        WHEN long_ratio < 0.2 THEN 'extreme_short'
        WHEN long_ratio > 0.6 OR long_ratio < 0.4 THEN 'biased'
        ELSE 'neutral'
    END,
    
    -- 加仓行为
    add_behavior_type = CASE 
        WHEN add_position_ratio > 0.9 THEN 'extreme_adder'
        WHEN add_position_ratio > 0.7 THEN 'frequent_adder'
        WHEN add_position_ratio > 0.5 THEN 'moderate_adder'
        ELSE 'normal'
    END;

-- ------------------------------------------------------------
-- Step 4: 计算脆弱评分
-- ------------------------------------------------------------
UPDATE hl_fragile_model_dev1 SET fragile_score = 
    -- 1. 交易纪律 (35分满分) - 最重要
    CASE discipline_type
        WHEN 'stubborn' THEN 25
        WHEN 'poor' THEN 18
        WHEN 'weak' THEN 10
        WHEN 'normal' THEN 4
        ELSE 0
    END +
    
    -- 2. 加仓行为 (20分满分)
    CASE add_behavior_type
        WHEN 'extreme_adder' THEN 15
        WHEN 'frequent_adder' THEN 10
        WHEN 'moderate_adder' THEN 5
        ELSE 0
    END +
    
    -- 3. 方向偏好 (10分满分)
    CASE direction_bias_type
        WHEN 'extreme_long' THEN 10
        WHEN 'extreme_short' THEN 10
        WHEN 'biased' THEN 5
        ELSE 0
    END +
    
    -- 4. 清算严重度 (20分满分)
    CASE 
        WHEN liq_severity_score / NULLIF(active_days/30, 0.1) >= 30 THEN 20
        WHEN liq_severity_score / NULLIF(active_days/30, 0.1) >= 15 THEN 15
        WHEN liq_severity_score / NULLIF(active_days/30, 0.1) >= 5 THEN 8
        WHEN liq_severity_score > 0 THEN 4
        ELSE 0
    END +
    
    -- 5. 单笔最大亏损 (10分满分)
    CASE 
        WHEN max_single_loss_ratio > 0.5 THEN 10
        WHEN max_single_loss_ratio > 0.3 THEN 6
        ELSE 0
    END +
    
    -- 6. 总亏损 (5分满分)
    CASE 
        WHEN total_realized_pnl < -100000 THEN 5
        WHEN total_realized_pnl < -50000 THEN 3
        ELSE 0
    END;

-- ------------------------------------------------------------
-- Step 5: 设置脆弱类型
-- ------------------------------------------------------------
UPDATE hl_fragile_model_dev1 SET fragile_type = 
    CASE 
        WHEN discipline_type = 'stubborn' AND add_behavior_type IN ('extreme_adder', 'frequent_adder') 
            THEN 'stubborn_adder'
        WHEN discipline_type = 'stubborn' 
            THEN 'stubborn'
        WHEN add_behavior_type = 'extreme_adder' 
            THEN 'extreme_adder'
        WHEN direction_bias_type IN ('extreme_long', 'extreme_short') AND liq_severity_score > 10 
            THEN 'directional_liquidator'
        WHEN liq_severity_score / NULLIF(active_days/30, 0.1) >= 15 
            THEN 'frequent_liquidator'
        WHEN total_fee / NULLIF(ABS(total_realized_pnl), 0.01) > 0.5 
            THEN 'fee_bleeder'
        ELSE 'mixed'
    END
WHERE fragile_score >= 30;

-- ------------------------------------------------------------
-- Step 6: 设置脆弱等级
-- ------------------------------------------------------------
UPDATE hl_fragile_model_dev1 SET fragile_level = 
    CASE 
        WHEN fragile_score >= 60 THEN 'L4'
        WHEN fragile_score >= 45 THEN 'L3'
        WHEN fragile_score >= 30 THEN 'L2'
        ELSE 'EXCLUDE'
    END;

-- ------------------------------------------------------------
-- Step 7: 创建脆弱地址池表 (只包含入池地址)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS hl_fragile_pool_dev1;

CREATE TABLE hl_fragile_pool_dev1 AS
SELECT 
    address,
    fragile_score,
    fragile_level,
    fragile_type,
    discipline_type,
    add_behavior_type,
    direction_bias_type,
    trading_style,
    ROUND(total_realized_pnl, 2) as total_pnl,
    ROUND(discipline_ratio, 4) as discipline_ratio,
    ROUND(add_position_ratio, 4) as add_position_ratio,
    liq_severity_score,
    total_trades,
    active_days,
    NOW() as created_at,
    NOW() as updated_at
FROM hl_fragile_model_dev1
WHERE fragile_score >= 30
  AND trading_style != 'quant_bot'  -- 排除量化机器人
ORDER BY fragile_score DESC;

-- 添加主键和索引
ALTER TABLE hl_fragile_pool_dev1 ADD PRIMARY KEY (address);
ALTER TABLE hl_fragile_pool_dev1 ADD INDEX idx_level (fragile_level);
ALTER TABLE hl_fragile_pool_dev1 ADD INDEX idx_type (fragile_type);
ALTER TABLE hl_fragile_pool_dev1 ADD INDEX idx_score (fragile_score DESC);

-- ------------------------------------------------------------
-- Step 8: 验证统计
-- ------------------------------------------------------------

-- 分层统计
SELECT 
    fragile_level,
    COUNT(*) as count,
    ROUND(AVG(total_pnl), 2) as avg_pnl,
    ROUND(AVG(discipline_ratio), 4) as avg_discipline,
    ROUND(AVG(fragile_score), 1) as avg_score
FROM hl_fragile_pool_dev1
GROUP BY fragile_level
ORDER BY fragile_level;

-- 类型统计
SELECT 
    fragile_type,
    COUNT(*) as count,
    ROUND(AVG(total_pnl), 2) as avg_pnl,
    ROUND(AVG(fragile_score), 1) as avg_score
FROM hl_fragile_pool_dev1
GROUP BY fragile_type
ORDER BY avg_pnl;

-- 总数统计
SELECT 
    COUNT(*) as total_fragile_addresses,
    SUM(CASE WHEN fragile_level = 'L4' THEN 1 ELSE 0 END) as L4_count,
    SUM(CASE WHEN fragile_level = 'L3' THEN 1 ELSE 0 END) as L3_count,
    SUM(CASE WHEN fragile_level = 'L2' THEN 1 ELSE 0 END) as L2_count
FROM hl_fragile_pool_dev1;
