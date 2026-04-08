# FEATURE_SCORING.md - 特征计算与评分

## 📋 概述

本文档说明如何计算地址特征并生成脆弱度评分。

---

## 🔄 执行流程

```
hl_fills + hl_position_snapshots
          ↓
scripts/calculate_address_features.py
          ↓
hl_address_features（特征表）
          ↓
scripts/calculate_fragile_scores.py
          ↓
hl_fragile_scores（评分表）
```

---

## 📊 数据表说明

### **1. hl_address_features（地址特征表）**

存储计算后的地址特征，每次计算生成一条新记录。

**主要字段**：

| 字段 | 说明 | 数据来源 |
|------|------|----------|
| address | 钱包地址 | - |
| calculated_at | 计算时间 | - |
| **基础统计** | | |
| total_trades | 总交易次数 | hl_fills |
| win_rate | 胜率（%） | hl_fills |
| avg_win_pnl | 平均盈利 | hl_fills |
| avg_loss_pnl | 平均亏损 | hl_fills |
| total_realized_pnl | 总已实现盈亏 | hl_fills |
| **风险指标** | | |
| avg_leverage | 平均杠杆 | hl_position_details |
| max_leverage | 最大杠杆 | hl_position_details |
| avg_margin_utilization | 平均保证金使用率（%） | hl_position_snapshots |
| coin_concentration | 单币种集中度（%） | hl_position_details |
| **亏损特征** | | |
| liquidation_count | 清算次数（推断） | hl_fills |
| max_drawdown | 最大回撤（%） | hl_position_snapshots |

---

### **2. hl_fragile_scores（脆弱地址评分表）**

存储地址的脆弱度评分，每次评分生成一条新记录。

**主要字段**：

| 字段 | 说明 | 满分 |
|------|------|------|
| address | 钱包地址 | - |
| feature_id | 关联的特征ID | - |
| scored_at | 评分时间 | - |
| **评分详情** | | |
| risk_behavior_score | 风险行为评分 | 40 |
| loss_feature_score | 亏损特征评分 | 35 |
| mentality_score | 心态特征评分 | 25 |
| total_score | 总分 | 100 |
| fragile_level | 脆弱等级（L1-L4） | - |

---

## 🎯 评分模型

### **总分构成（100分）**

```
总分 = 风险行为评分(40) + 亏损特征评分(35) + 心态特征评分(25)
```

---

### **1. 风险行为评分（40分）**

| 指标 | 满分 | 评分规则 |
|------|------|----------|
| **平均杠杆** | 15 | ≥20x → 15分<br>≥15x → 12分<br>≥10x → 8分<br>≥5x → 4分 |
| **保证金使用率** | 15 | ≥70% → 15分<br>≥60% → 12分<br>≥50% → 8分<br>≥30% → 4分 |
| **单币种集中度** | 10 | ≥90% → 10分<br>≥80% → 7分<br>≥60% → 4分 |

---

### **2. 亏损特征评分（35分）**

| 指标 | 满分 | 评分规则 |
|------|------|----------|
| **胜率** | 15 | <20% → 15分<br><30% → 12分<br><40% → 8分<br><50% → 4分 |
| **清算次数** | 10 | ≥10次 → 10分<br>≥5次 → 7分<br>≥2次 → 4分<br>≥1次 → 2分 |
| **最大回撤** | 10 | ≥80% → 10分<br>≥60% → 7分<br>≥40% → 4分<br>≥20% → 2分 |

---

### **3. 心态特征评分（25分）**

| 指标 | 满分 | 评分规则 |
|------|------|----------|
| **盈亏比** | 15 | <0.5 → 15分<br><1.0 → 10分<br><1.5 → 5分 |
| **样本充足性** | 10 | <10次交易 → 10分（样本不足） |

---

### **4. 脆弱等级划分**

| 等级 | 分数范围 | 说明 | 特征 |
|------|----------|------|------|
| **L1** | 75-100 | 极度脆弱 | 高杠杆 + 低胜率 + 多次爆仓 |
| **L2** | 60-74 | 高度脆弱 | 高杠杆 + 低胜率或多次爆仓 |
| **L3** | 40-59 | 中度脆弱 | 高杠杆或低胜率 |
| **L4** | 0-39 | 轻度脆弱 | 有一定风险特征 |

---

## 🚀 使用方法

### **1. 计算地址特征**

```bash
# 计算所有活跃地址的特征
python scripts/calculate_address_features.py
```

**输出示例**：
```
[1/1] 0x020ca66c30bec2c4fe3861a94e4db4a498a35872

[计算特征] 0x020ca66c...
   📊 计算基础统计...
   ⚙️ 计算风险指标...
   🔥 计算清算次数...
   📉 计算最大回撤...
   ✅ 特征计算完成
      胜率: 100.00%
      平均杠杆: 25.0x
      清算次数: 0
   💾 特征已保存（ID: 1）
```

---

### **2. 计算脆弱度评分**

```bash
# 对所有已计算特征的地址进行评分
python scripts/calculate_fragile_scores.py
```

**输出示例**：
```
[1/1] 0x020ca66c...
   📊 总分: 48/100 (等级: L3)
   - 风险行为: 33/40
     杠杆25.0x(极高) | 保证金58.1%(高) | 集中度100.0%(极高)
   - 亏损特征: 0/35
     胜率100.0%(正常) | 无清算 | 回撤0.0%
   - 心态特征: 15/25
     盈亏比0.00(极差) | 交易843次(充足)
   💾 评分已保存（ID: 1）
```

---

### **3. 查询评分结果**

```sql
-- 查看所有地址的最新评分
SELECT 
    s.address,
    a.label,
    s.total_score,
    s.fragile_level,
    s.risk_behavior_score,
    s.loss_feature_score,
    s.mentality_score,
    s.scored_at
FROM hl_fragile_scores s
LEFT JOIN hl_address_list a ON s.address = a.address
ORDER BY s.scored_at DESC;

-- 查看 L1/L2 级别的高危地址
SELECT 
    address,
    total_score,
    fragile_level,
    scored_at
FROM hl_fragile_scores
WHERE fragile_level IN ('L1', 'L2')
ORDER BY total_score DESC;
```

---

## 📅 定时任务

### **每日计算（推荐）**

```cron
# 每天凌晨 3 点计算特征
0 3 * * * cd /opt/CryptoAnalysis && venv/bin/python scripts/calculate_address_features.py >> logs/features.log 2>&1

# 每天凌晨 3:30 计算评分
30 3 * * * cd /opt/CryptoAnalysis && venv/bin/python scripts/calculate_fragile_scores.py >> logs/scores.log 2>&1
```

---

## 📊 真实案例分析

### **案例：麻吉大哥（0x020ca66c...）**

**特征数据**：
```
胜率: 100.00%
平均杠杆: 25.0x
清算次数: 0
总交易次数: 843
保证金使用率: 58.1%
```

**评分结果**：
```
总分: 48/100 (L3 - 中度脆弱)

风险行为: 33/40
- 杠杆 25x（极高）→ 15分
- 保证金 58.1%（高）→ 8分
- 集中度 100%（极高）→ 10分

亏损特征: 0/35
- 胜率 100%（正常）→ 0分
- 无清算 → 0分
- 无回撤 → 0分

心态特征: 15/25
- 盈亏比 0.00（极差）→ 15分
  （注：所有订单都是开仓，未平仓，所以盈亏比为0）
- 交易 843 次（充足）→ 0分
```

**分析**：
- ✅ 当前盈利状态（胜率100%，无清算）
- ❌ 高风险操作（25x杠杆，单币种，高保证金使用）
- ⚠️ **中度脆弱**：虽然目前盈利，但一旦反转风险极高

---

## 📝 注意事项

### **1. 数据依赖**

- 必须先运行数据采集脚本：
  - `fetch_address_fills_incremental.py`
  - `fetch_all_position_snapshots.py`
- 至少需要 10 笔以上的交易记录

### **2. 评分局限性**

- ⚠️ 盈亏比可能为 0（所有订单未平仓）
- ⚠️ 清算次数是推断（不一定准确）
- ⚠️ 胜率 100% 可能是样本问题（持仓时间短）

### **3. 后续优化**

- ✅ 补充资金费率数据（计算真实持仓成本）
- ✅ 补充持仓时长分析（区分开仓/平仓时间）
- ✅ 添加更多心态特征（浮亏加仓率、追涨杀跌率等）

---

## 📚 相关文档

- [数据库设计](./DATABASE.md)
- [API 接口文档](./HYPERLIQUID_API.md)
- [脚本使用说明](./SCRIPTS.md)
- [定时任务配置](./CRON_JOBS.md)

---

**最后更新**: 2026-04-07
