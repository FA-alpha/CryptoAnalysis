# v2 升级说明

> 更新时间：2026-04-13 19:00  
> 从评分模型 v1 升级到 v2.1

**最新版本**：v2.1（新增最长连亏指标 + 连亏识别优化）

---

## 主要变更

### 1. 数据库变更（已完成）

```sql
-- hl_fills 表
ALTER TABLE hl_fills MODIFY COLUMN dir VARCHAR(50);  -- 支持完整清算类型

-- hl_address_features 表新增字段 (v2.0)
ALTER TABLE hl_address_features ADD COLUMN liquidation_per_month DECIMAL(10,2);
ALTER TABLE hl_address_features ADD COLUMN has_refill_behavior TINYINT(1) DEFAULT 0;
ALTER TABLE hl_address_features ADD COLUMN consecutive_loss_add_count INT DEFAULT 0;
ALTER TABLE hl_address_features ADD COLUMN add_position_score DECIMAL(10,2) DEFAULT 0;
ALTER TABLE hl_address_features ADD COLUMN scalping_score DECIMAL(10,2) DEFAULT 0;

-- v2.1 新增字段 🆕
ALTER TABLE hl_address_features ADD COLUMN max_consecutive_loss_count INT DEFAULT 0;

-- hl_fragile_scores 表
ALTER TABLE hl_fragile_scores ADD COLUMN trading_behavior_score DECIMAL(10,2) DEFAULT 0;
ALTER TABLE hl_fragile_scores MODIFY COLUMN total_score DECIMAL(10,2);
```

### 2. 新脚本

| 脚本 | 说明 |
|------|------|
| `scripts/calculate_address_features_v2.py` | 新特征计算引擎 |
| `scripts/calculate_fragile_scores_v2.py` | 新评分引擎 |

**旧脚本保留但不再使用**：
- `calculate_address_features.py`
- `calculate_fragile_scores.py`

### 3. 评分体系变更

| 维度 | v1 | v2.0 | v2.1 🆕 |
|------|----|-----|-----|
| 杠杆 | position_details.leverage_value | 账户整体杠杆（快照） | 同 v2.0 |
| 清算 | 只看 dir | 官方 + 近似清算（50%亏损） | 同 v2.0 |
| 仓位 | 20分固定 | 10分 + 补仓修正 | 同 v2.0 |
| 连续亏损 | 无 | 每笔Close独立 | 时间窗口+方向合并 |
| 最长连亏 | 无 | 无 | 新增（5分） |
| 心态特征 | 无 | 20分 | **25分** |
| 加仓/做T | 无 | 双向±15分 | 同 v2.0 |
| 总分 | 0~100 | 约 -10~120 | **约 -10~125** |

---

## 使用方式

```bash
# 1. 计算特征（v2）
python scripts/calculate_address_features_v2.py

# 2. 计算评分（v2）
python scripts/calculate_fragile_scores_v2.py

# 3. 查询结果
mysql> SELECT address, total_score, fragile_level
       FROM hl_fragile_scores
       ORDER BY scored_at DESC, total_score DESC
       LIMIT 10;
```

---

## 核心改进

### 清算识别更准确

**旧版**：只看 `dir LIKE 'Liquidat%'`  
**新版**：官方清算 + 近似清算

**近似清算定义**：
- 全仓平掉（sz ≈ |start_position|）
- 亏损
- 亏损占名义价值 ≥ 50%

**原因**：很多人在清算价前手动平仓，但本质已是爆仓。

### 杠杆来源更可靠

**旧版**：`position_details.leverage_value`（全仓模式全是 40，无区分度）  
**新版**：`total_ntl_pos / account_value`（快照历史均值，真实杠杆）

### 仓位评分更精细

**旧版**：80% 利用率一刀切 20 分  
**新版**：80% 利用率基础 7 分，但如果有补仓行为 → -3 分

**原因**：留有补仓空间且实际使用的人，风险相对可控。

### 连续亏损识别优化（v2.1 核心）

**旧版问题**：
- 每笔 Close 都独立计数
- 会把“同一次做错方向的分批止损”算成多次亏损

**新版改进（方案D）**：
- 同 coin + 同方向（Long/Short） + 1小时内的连续 Close，算同一次亏损事件
- 中间有盈利 Close，归零计数

**例子**：
```
做多BTC，价格跌了，分批止损：
Close 3个 pnl=-6000  ← 止损1
Close 3个 pnl=-12000 ← 止损2 (时间<1h, 同Long)
Close 4个 pnl=-24000 ← 止损3 (时间<1h, 同Long)

旧版：算 3 次连续亏损
新版：算 1 次连续亏损（同一次做错方向）
```

### 支持双向计分

**新版新增**：加仓/做T 行为得分（-6~+15 分）

- 加仓后成功摊薄成本且盈利 → 负分（降低风险评分）
- 加仓后亏损扩大 → 正分（增加风险评分）
- 做T盈利 → 负分
- 做T反而放大亏损 → 正分

**当前状态**：简化版返回 0 分，完整版待实现。

### 新增最长连亏指标（v2.1）

反映心态崩溃程度：
- ≥10笔 → 5分
- ≥7笔 → 3分
- ≥5笔 → 1分

---

## 服务器部署

定时任务需更新为 v2 脚本：

```cron
# /home/ubuntu/crontab

# 每天凌晨执行
0 0 * * * cd /home/ubuntu/CryptoAnalysis && /home/ubuntu/CryptoAnalysis/venv/bin/python scripts/fetch_address_fills_incremental.py >> logs/fills.log 2>&1
3 0 * * * cd /home/ubuntu/CryptoAnalysis && /home/ubuntu/CryptoAnalysis/venv/bin/python scripts/fetch_all_position_snapshots.py >> logs/snapshots.log 2>&1
10 0 * * * cd /home/ubuntu/CryptoAnalysis && /home/ubuntu/CryptoAnalysis/venv/bin/python scripts/calculate_address_features_v2.py >> logs/features.log 2>&1
20 0 * * * cd /home/ubuntu/CryptoAnalysis && /home/ubuntu/CryptoAnalysis/venv/bin/python scripts/calculate_fragile_scores_v2.py >> logs/scores.log 2>&1
```

---

## 详细文档

- 评分模型详细规则：`docs/SCORING_MODEL_V2.md`
- 脚本使用说明：`docs/SCRIPTS.md`（待更新）
- 数据库设计：`docs/DATABASE.md`

---

*升级完成后建议手动执行一次 v2 脚本验证。*
