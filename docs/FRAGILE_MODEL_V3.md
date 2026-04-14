# 脆弱地址建模方案 V3.0

> 在 V2.0 基础上增加币种过滤，排除异常交易行为

## 更新日志

| 版本 | 日期 | 变更 |
|------|------|------|
| V3.0 | 2026-04-14 | 增加异常币种过滤（符文、合成资产） |
| V2.0 | 2026-04-14 | 多维度评分模型 |
| V1.0 | 2026-04-13 | 初始方案 |

---

## 一、V3.0 核心变更：异常币种过滤

### 1.1 问题背景

数据分析发现：
- **符文币（@开头）**：26万笔交易，1940个地址
- **合成资产（cash:/xyz:）**：50万笔交易，1565个地址
- 这些币种的交易行为与常规币种差异大，影响评分准确性

### 1.2 过滤规则

```sql
-- 排除条件：异常币种交易占比 > 50%
-- 异常币种包括：
--   1. 符文币: coin LIKE '@%'
--   2. 合成资产: coin LIKE 'cash:%' OR coin LIKE 'xyz:%'
```

### 1.3 过滤效果

| 指标 | V2.0 | V3.0 | 变化 |
|------|------|------|------|
| 总地址数 | 3956 | **3385** | -571 (-14.4%) |
| L4 高危 | 185 | **182** | -3 |
| L3 中度 | 1263 | **1087** | -176 |
| L2 轻度 | 2508 | **2116** | -392 |

### 1.4 过滤后各层级效果

| 等级 | 数量 | 平均亏损 | 正常币种占比 |
|------|------|----------|-------------|
| L4 高危 | 182 | **-$48.4万** | 92.2% |
| L3 中度 | 1087 | -$10.7万 | 90.2% |
| L2 轻度 | 2116 | -$9.1万 | 88.2% |

**结论：** L4 高危地址平均亏损 $48.4万，是 L2 的 5.3 倍，区分度良好。

---

## 二、完整评分模型

### 2.1 核心指标（保留 V2.0）

| 维度 | 指标 | 权重 | 说明 |
|------|------|------|------|
| 交易纪律 | discipline_ratio | 35% | 止盈/止损比 |
| 加仓行为 | add_position_ratio | 25% | 加仓交易占比 |
| 清算风险 | liq_severity_score | 20% | 加权清算得分 |
| 方向偏好 | direction_bias | 10% | 多空极端偏好 |
| 总亏损 | total_realized_pnl | 10% | 历史累计亏损 |

### 2.2 评分规则

#### 2.2.1 交易纪律评分（35分）

```sql
CASE 
    WHEN discipline_ratio < 0.3 THEN 35   -- 死扛型
    WHEN discipline_ratio < 0.5 THEN 25
    WHEN discipline_ratio < 1.0 THEN 15
    WHEN discipline_ratio < 2.0 THEN 8
    ELSE 0                                 -- 纪律好
END
```

#### 2.2.2 加仓行为评分（25分）

```sql
CASE 
    WHEN add_position_ratio > 0.9 THEN 25  -- 极端加仓
    WHEN add_position_ratio > 0.7 THEN 18
    WHEN add_position_ratio > 0.5 THEN 10
    ELSE 0
END
```

#### 2.2.3 清算风险评分（20分）

```sql
-- 清算严重度 = Cross清算×15 + Isolated清算×10 + ADL×5
CASE 
    WHEN liq_severity_score / active_months >= 30 THEN 20
    WHEN liq_severity_score / active_months >= 15 THEN 12
    WHEN liq_severity_score / active_months >= 5 THEN 6
    ELSE 0
END
```

#### 2.2.4 方向偏好评分（10分）

```sql
CASE 
    WHEN long_ratio > 0.9 OR long_ratio < 0.1 THEN 10  -- 极端
    WHEN long_ratio > 0.75 OR long_ratio < 0.25 THEN 5 -- 偏向
    ELSE 0                                              -- 中性
END
```

#### 2.2.5 总亏损评分（10分）

```sql
CASE 
    WHEN total_realized_pnl < -100000 THEN 10
    WHEN total_realized_pnl < -50000 THEN 6
    WHEN total_realized_pnl < -10000 THEN 3
    ELSE 0
END
```

### 2.3 分层入池规则

| 等级 | 分数范围 | 信号权重 | 预估数量 |
|------|---------|---------|---------|
| L4 高危 | ≥ 70 | 高 | ~180 |
| L3 中度 | 50-69 | 中 | ~1100 |
| L2 轻度 | 30-49 | 低 | ~2100 |
| 排除 | < 30 | - | - |

---

## 三、数据库表结构

### 3.1 脆弱池表 `hl_fragile_pool_v3`

```sql
CREATE TABLE hl_fragile_pool_v3 (
    address VARCHAR(66) NOT NULL,
    fragile_score INT DEFAULT 0,
    fragile_level VARCHAR(7) NOT NULL,        -- L2/L3/L4
    fragile_type VARCHAR(50),                  -- stubborn_adder/extreme_adder/...
    discipline_type VARCHAR(20),               -- stubborn/weak/normal/good
    add_behavior_type VARCHAR(20),             -- extreme/frequent/moderate/normal
    direction_bias_type VARCHAR(20),           -- extreme_long/extreme_short/biased/neutral
    trading_style VARCHAR(20),                 -- retail/scalper/all_in/quant_bot
    total_pnl DECIMAL(17,2),
    discipline_ratio DECIMAL(29,4),
    add_position_ratio DECIMAL(27,4),
    liq_severity_score DECIMAL(27,0),
    total_trades BIGINT DEFAULT 0,
    active_days INT,
    normal_coin_ratio DECIMAL(5,4),            -- V3 新增：正常币种交易占比
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (address),
    INDEX idx_level (fragile_level),
    INDEX idx_score (fragile_score)
);
```

---

## 四、待实现功能（V4.0 规划）

| 功能 | 优先级 | 复杂度 | 说明 |
|------|--------|--------|------|
| 加仓效果 ±分 | P1 | 高 | 区分「扩大亏损」vs「摊薄成本」 |
| 做T行为 ±分 | P2 | 高 | 识别做T盈亏效果 |
| 浮亏加仓检测 | P2 | 高 | 需要交易配对逻辑 |
| 连续亏损后加仓 | P3 | 中 | 心态崩盘检测 |
| 死扛指数 | P3 | 中 | 持仓时间对比 |

---

## 五、使用说明

### 5.1 查询脆弱池

```sql
-- 获取高危脆弱地址
SELECT address, fragile_score, fragile_type, total_pnl
FROM hl_fragile_pool_v3
WHERE fragile_level = 'L4'
ORDER BY fragile_score DESC;
```

### 5.2 按类型筛选

```sql
-- 获取「死扛+加仓」型地址（最危险）
SELECT *
FROM hl_fragile_pool_v3
WHERE fragile_type = 'stubborn_adder'
ORDER BY total_pnl ASC;
```

### 5.3 信号权重建议

| 场景 | 权重方案 |
|------|---------|
| 高频策略 | L4: 1.0, L3: 0.6, L2: 0.3 |
| 保守策略 | 只用 L4 |
| 统计套利 | L4: 0.5, L3: 0.3, L2: 0.2 |
