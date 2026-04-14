# 脆弱地址建模方案 V2.0

> 基于真实数据验证的多维度脆弱地址识别模型

## 一、核心发现（数据验证）

### 1.1 止盈止损纪律是最强预测指标

| 纪律类型 | 地址数 | 平均亏损 | 倍数 |
|---------|--------|----------|------|
| 纪律好 (>=2.0) | 599 | -$2.7万 | 1x |
| 一般 (1.0-2.0) | 1473 | -$4.7万 | 1.7x |
| 偏弱 (0.5-1.0) | 2318 | -$7万 | 2.6x |
| 差 (0.3-0.5) | 1396 | -$7.1万 | 2.6x |
| **死扛型 (<0.3)** | 2042 | **-$15.9万** | **6x** |

**结论：** 止盈止损比 (discipline_ratio) 是最强的脆弱预测指标

### 1.2 加仓行为验证

| 加仓行为 | 地址数 | 平均亏损 | 倍数 |
|---------|--------|----------|------|
| 极端加仓 (>90%) | 2424 | **-$14.6万** | **4x** |
| 高频加仓 (70-90%) | 2764 | -$6.4万 | 1.8x |
| 中度加仓 (50-70%) | 1385 | -$5.9万 | 1.6x |
| 少量加仓 (30-50%) | 773 | -$5万 | 1.4x |
| 几乎不加仓 (<30%) | 575 | -$3.6万 | 1x |

**结论：** 极端加仓型亏损是不加仓型的 4 倍

### 1.3 脆弱类型分布

| 类型 | 数量 | 平均亏损 | 特征 |
|------|------|----------|------|
| **stubborn_adder** | 1590 | **-$18.6万** | 死扛+加仓，最脆弱 |
| frequent_liquidator | 5 | -$24.1万 | 频繁爆仓 |
| extreme_adder | 998 | -$12万 | 极端加仓 |
| stubborn | 547 | -$5.4万 | 纯死扛 |
| fee_bleeder | 45 | -$1万 | 手续费吃掉利润 |

---

## 二、多层次评估框架

```
┌─────────────────────────────────────────────────────────────────┐
│                    脆弱地址多层次评估框架                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  【第一层：交易纪律画像】权重 35%                                │
│  ├── discipline_ratio (止盈止损比) - 最强指标                   │
│  ├── 死扛型 (<0.3) = 25分                                       │
│  ├── 差 (0.3-0.5) = 18分                                        │
│  ├── 偏弱 (0.5-1.0) = 10分                                      │
│  └── 一般 (1.0-2.0) = 4分                                       │
│                                                                 │
│  【第二层：加仓行为画像】权重 20%                                │
│  ├── add_position_ratio (加仓比例)                              │
│  ├── 极端加仓 (>90%) = 15分                                     │
│  ├── 高频加仓 (70-90%) = 10分                                   │
│  └── 中度加仓 (50-70%) = 5分                                    │
│                                                                 │
│  【第三层：方向偏好画像】权重 10%                                │
│  ├── long_ratio (多头比例)                                      │
│  ├── 极端多头/空头 (>80% 或 <20%) = 10分                        │
│  └── 偏向 (60-80% 或 20-40%) = 5分                              │
│                                                                 │
│  【第四层：清算严重度】权重 20%                                  │
│  ├── liq_severity_score = Cross×15 + Isolated×10 + ADL×5       │
│  ├── 月均 >=30分 = 20分                                         │
│  ├── 月均 15-30分 = 15分                                        │
│  └── 月均 5-15分 = 8分                                          │
│                                                                 │
│  【第五层：单笔最大亏损】权重 10%                                │
│  ├── max_single_loss_ratio (单笔亏损/总亏损)                    │
│  ├── >50% = 10分                                                │
│  └── 30-50% = 6分                                               │
│                                                                 │
│  【第六层：总亏损】权重 5%                                       │
│  ├── < -$100k = 5分                                             │
│  └── < -$50k = 3分                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心指标定义

### 3.1 止盈止损比 (discipline_ratio)

```sql
-- 计算方式
avg_win = AVG(closed_pnl) WHERE closed_pnl > 0
avg_loss = AVG(ABS(closed_pnl)) WHERE closed_pnl < 0
discipline_ratio = avg_win / avg_loss

-- 分类
disciplined: >= 2.0  -- 纪律好
normal: 1.0 - 2.0    -- 一般
weak: 0.5 - 1.0      -- 偏弱
poor: 0.3 - 0.5      -- 差
stubborn: < 0.3      -- 死扛型
```

### 3.2 加仓比例 (add_position_ratio)

```sql
-- 计算方式
add_position_count = COUNT(*) WHERE dir LIKE 'Open%' AND start_position != 0
new_position_count = COUNT(*) WHERE dir LIKE 'Open%' AND start_position = 0
add_position_ratio = add_position_count / (add_position_count + new_position_count)

-- 分类
extreme_adder: > 90%     -- 极端加仓
frequent_adder: 70-90%   -- 高频加仓
moderate_adder: 50-70%   -- 中度加仓
normal: < 50%            -- 正常
```

### 3.3 清算严重度 (liq_severity_score)

```sql
-- 计算方式
liq_cross_count = COUNT(*) WHERE dir LIKE 'Liquidated Cross%'
liq_isolated_count = COUNT(*) WHERE dir LIKE 'Liquidated Isolated%'
adl_count = COUNT(*) WHERE dir = 'Auto-Deleveraging'

liq_severity_score = liq_cross_count * 15 + liq_isolated_count * 10 + adl_count * 5

-- Cross 爆仓最致命（全仓），Isolated 次之（逐仓），ADL 最轻（被动）
```

### 3.4 单笔最大亏损比 (max_single_loss_ratio)

```sql
-- 计算方式
max_single_loss = MIN(closed_pnl)  -- 最大单笔亏损（负数）
total_loss = SUM(closed_pnl) WHERE closed_pnl < 0
max_single_loss_ratio = max_single_loss / total_loss
```

---

## 四、评分模型 SQL 实现

### 4.1 创建特征表

```sql
CREATE TABLE hl_fragile_model_v2 AS
SELECT 
    af.address,
    af.total_realized_pnl,
    af.total_fee,
    af.liquidation_count,
    af.win_rate,
    af.active_days,
    af.max_leverage,
    af.coin_concentration,
    
    -- 止盈止损比
    t.avg_win,
    t.avg_loss,
    t.avg_win / NULLIF(t.avg_loss, 0.01) as discipline_ratio,
    
    -- 交易频率和规模
    t.total_trades,
    t.fills_per_day,
    t.avg_trade_value,
    
    -- 清算详情
    t.liq_cross_count,
    t.liq_isolated_count,
    t.adl_count,
    t.liq_cross_count * 15 + t.liq_isolated_count * 10 + t.adl_count * 5 as liq_severity_score,
    
    -- 单笔最大亏损
    t.max_single_loss,
    t.total_loss,
    t.max_single_loss / NULLIF(t.total_loss, 0.01) as max_single_loss_ratio,
    
    -- 多空偏好
    t.long_ratio,
    
    -- 加仓行为
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
        AVG(CASE WHEN closed_pnl > 0 THEN closed_pnl ELSE NULL END) as avg_win,
        AVG(CASE WHEN closed_pnl < 0 THEN ABS(closed_pnl) ELSE NULL END) as avg_loss,
        SUM(CASE WHEN dir LIKE 'Liquidated Cross%' THEN 1 ELSE 0 END) as liq_cross_count,
        SUM(CASE WHEN dir LIKE 'Liquidated Isolated%' THEN 1 ELSE 0 END) as liq_isolated_count,
        SUM(CASE WHEN dir = 'Auto-Deleveraging' THEN 1 ELSE 0 END) as adl_count,
        MIN(closed_pnl) as max_single_loss,
        SUM(CASE WHEN closed_pnl < 0 THEN closed_pnl ELSE 0 END) as total_loss,
        SUM(CASE WHEN dir LIKE '%Long%' OR dir = 'Buy' THEN 1 ELSE 0 END) / COUNT(*) as long_ratio,
        SUM(CASE WHEN dir LIKE 'Open%' AND start_position != 0 THEN 1 ELSE 0 END) as add_position_count,
        SUM(CASE WHEN dir LIKE 'Open%' AND start_position = 0 THEN 1 ELSE 0 END) as new_position_count
    FROM hl_fills
    GROUP BY address
    HAVING COUNT(*) >= 50
) t ON af.address = t.address;
```

### 4.2 添加分类字段

```sql
ALTER TABLE hl_fragile_model_v2 
ADD COLUMN trading_style VARCHAR(20),
ADD COLUMN discipline_type VARCHAR(20),
ADD COLUMN direction_bias_type VARCHAR(20),
ADD COLUMN add_behavior_type VARCHAR(20),
ADD COLUMN fragile_score INT DEFAULT 0,
ADD COLUMN fragile_type VARCHAR(50),
ADD COLUMN fragile_level VARCHAR(10);
```

### 4.3 填充分类

```sql
UPDATE hl_fragile_model_v2 SET
    trading_style = CASE 
        WHEN fills_per_day >= 40 AND avg_trade_value >= 5000 THEN 'quant_bot'
        WHEN fills_per_day >= 40 THEN 'scalper'
        WHEN fills_per_day < 10 AND avg_trade_value >= 10000 THEN 'all_in'
        ELSE 'retail'
    END,
    discipline_type = CASE 
        WHEN discipline_ratio >= 2.0 THEN 'disciplined'
        WHEN discipline_ratio >= 1.0 THEN 'normal'
        WHEN discipline_ratio >= 0.5 THEN 'weak'
        WHEN discipline_ratio >= 0.3 THEN 'poor'
        ELSE 'stubborn'
    END,
    direction_bias_type = CASE 
        WHEN long_ratio > 0.8 THEN 'extreme_long'
        WHEN long_ratio < 0.2 THEN 'extreme_short'
        WHEN long_ratio > 0.6 OR long_ratio < 0.4 THEN 'biased'
        ELSE 'neutral'
    END,
    add_behavior_type = CASE 
        WHEN add_position_ratio > 0.9 THEN 'extreme_adder'
        WHEN add_position_ratio > 0.7 THEN 'frequent_adder'
        WHEN add_position_ratio > 0.5 THEN 'moderate_adder'
        ELSE 'normal'
    END;
```

### 4.4 计算脆弱评分

```sql
UPDATE hl_fragile_model_v2 SET fragile_score = 
    -- 1. 交易纪律 (35分满分)
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
```

### 4.5 设置脆弱类型和等级

```sql
-- 设置脆弱类型
UPDATE hl_fragile_model_v2 SET fragile_type = 
    CASE 
        WHEN discipline_type = 'stubborn' AND add_behavior_type IN ('extreme_adder', 'frequent_adder') THEN 'stubborn_adder'
        WHEN discipline_type = 'stubborn' THEN 'stubborn'
        WHEN add_behavior_type = 'extreme_adder' THEN 'extreme_adder'
        WHEN direction_bias_type IN ('extreme_long', 'extreme_short') AND liq_severity_score > 10 THEN 'directional_liquidator'
        WHEN liq_severity_score / NULLIF(active_days/30, 0.1) >= 15 THEN 'frequent_liquidator'
        WHEN total_fee / NULLIF(ABS(total_realized_pnl), 0.01) > 0.5 THEN 'fee_bleeder'
        ELSE 'mixed'
    END
WHERE fragile_score >= 30;

-- 设置脆弱等级
UPDATE hl_fragile_model_v2 SET fragile_level = 
    CASE 
        WHEN fragile_score >= 60 THEN 'L4'
        WHEN fragile_score >= 45 THEN 'L3'
        WHEN fragile_score >= 30 THEN 'L2'
        ELSE 'EXCLUDE'
    END;
```

---

## 五、脆弱地址入池规则

### 5.1 分层标准

| 等级 | 分数范围 | 数量预估 | 信号权重 | 用途 |
|------|---------|---------|---------|------|
| L4 高危 | >= 60 | ~200 | 高 | 优先反向信号 |
| L3 中度 | 45-59 | ~1400 | 中 | 标准反向信号 |
| L2 轻度 | 30-44 | ~2700 | 低 | 辅助参考 |
| 排除 | < 30 | ~3600 | - | 不入池 |

### 5.2 入池 SQL

```sql
-- 创建脆弱地址池表
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
    total_realized_pnl,
    discipline_ratio,
    add_position_ratio,
    liq_severity_score,
    total_trades,
    active_days,
    NOW() as created_at,
    NOW() as updated_at
FROM hl_fragile_model_v2
WHERE fragile_score >= 30
  AND trading_style != 'quant_bot'  -- 排除量化机器人
ORDER BY fragile_score DESC;
```

---

## 六、验证结果

### 6.1 评分分层有效性

| 等级 | 地址数 | 平均亏损 | 平均纪律比 | 验证 |
|------|--------|----------|-----------|------|
| L4 高危 | 202 | **-$46.9万** | 0.089 | ✅ 亏损最大 |
| L3 中度 | 1442 | -$14.6万 | 0.198 | ✅ |
| L2 轻度 | 2707 | -$9.4万 | 2.428 | ✅ |
| 排除 | 3577 | -$3.1万 | 1.550 | ✅ 亏损最小 |

**结论：** L4 高危组平均亏损是排除组的 **15 倍**，模型有效

### 6.2 最脆弱地址示例

| 地址 | 评分 | 类型 | 总亏损 | 纪律比 |
|------|------|------|--------|--------|
| 0x736... | 65 | stubborn_adder | -$616万 | 0.138 |
| 0xc07... | 65 | stubborn_adder | -$591万 | 0.110 |
| 0x467... | 65 | stubborn_adder | -$175万 | 0.129 |

**全部都是 stubborn_adder 类型（死扛+极端加仓）！**

---

## 七、待优化项

| 优先级 | 问题 | 后续方案 |
|--------|------|---------|
| P1 | 浮亏加仓率未计算 | 需要交易配对逻辑 |
| P1 | 死扛时间未计算 | 需要持仓时间分析 |
| P2 | 币种维度细分 | V3 版本 |
| P2 | 追涨杀跌检测 | 需要 K 线数据 |
| P3 | 报复性交易检测 | 需要时间序列分析 |

---

## 八、使用建议

1. **反向信号优先级：** L4 > L3 > L2
2. **最佳信号来源：** `stubborn_adder` 类型
3. **避免跟踪：** `fee_bleeder` 类型（方向可能对，只是手续费吃掉利润）
4. **动态更新：** 建议每周重新计算评分
