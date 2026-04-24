# 更新日志

## [0.3.1] - 2026-04-24

### 🔧 monitor_combined.py 修复与优化

#### 修复
- ✅ HTTP 429 退避不生效问题：`except HTTPStatusError` 里 429 只 `continue` 没有 sleep
- ✅ 429 退避结束后 `last_req_ms` 未重置，导致批量请求无间隔打出

#### 优化
- ✅ 飞书推送时间改为北京时间（UTC+8）
- ✅ 平仓/减仓时推送已实现盈亏（closedPnl）
- ✅ 开仓/加仓显示当前持仓（startPosition + sz）
- ✅ 平仓/减仓显示剩余持仓（startPosition - sz）

#### 数据库变更
- ✅ 删除废弃表 `hl_monitor_addresses`（已由 `hl_fragile_pool` 替代）

---

## [0.3.0] - 2026-04-16

### 🎯 因子五实现 + 数据库清理

#### 新功能
- ✅ **因子五：追加保证金（20分）** 正式实现
  - 识别逻辑：`accountClassTransfer + to_perp=1` + 发生在亏损持仓期间
  - 评分：1次=5分 / 3次=10分 / 5次=15分 / ≥10次=20分
- ✅ **`fetch_ledger_updates.py`** 升级
  - 新增单地址模式：`python fetch_ledger_updates.py <address>`
  - 全量模式：无历史数据时不传时间参数，拉取全部历史
  - 增量模式：有历史数据时从 `MAX(time)` 往后增量
- ✅ **主流币种过滤**：特征计算仅统计 BTC/ETH/SOL/DOGE/XRP/ADA/HYPE/BCH/BNB

#### 数据库变更
- ✅ `hl_address_features` 新增字段：`margin_call_count`
- ✅ `hl_address_features` 删除废弃字段：`loss_add_ratio`、`chase_ratio`、`total_loss_holding_seconds`、`total_profit_holding_seconds`、`avg_loss_holding_seconds`、`avg_profit_holding_seconds`
- ✅ `hl_fragile_scores` 删除废弃字段：`risk_behavior_score`、`loss_feature_score`、`mentality_score`、`trading_behavior_score`、`in_pool`、`pool_weight`、`pool_entry_date`、`pool_exit_date`
- ✅ 删除废弃表：`hl_fragile_model_v2`、`hl_fragile_pool_dev1`、`hl_fragile_pool_v3`

#### 文档更新
- ✅ `sql/schema.sql` - 同步最新表结构
- ✅ `docs/DATABASE.md` - 同步字段变更
- ✅ `docs/SCRIPTS.md` - 新增 fetch_ledger_updates / v2 脚本说明

---

## [0.2.1] - 2026-04-13 19:00

### 🔧 评分模型 v2.1 优化

#### 数据库变更
- ✅ `hl_address_features` 新增字段：
  - `max_consecutive_loss_count` - 最长连续亏损笔数

#### 脚本更新
- ✅ `calculate_address_features.py` - 连续亏损识别改为**方案D**：
  - 同 coin + 同方向 + 1小时内的连续 Close，算同一次亏损事件
  - 中间有盈利 Close，归零计数
  - 同时统计最长连续亏损笔数
- ✅ `calculate_fragile_scores.py` - 新增最长连亏评分（5分）

#### 评分体系变更
- **心态特征**：20分 → **25分**
  - 连亏后加仓（10分）
  - 追涨杀跌率（5分）
  - 最长连亏笔数（5分）🆕
  - 死扛指数（5分，待实现）
- **总分范围**：约 -10~120 → **约 -10~125**

#### 文档更新
- ✅ `docs/SCORING_MODEL_V2.md` - 更新为 v2.1
- ✅ `CHANGELOG.md` - 新增 v2.1 版本记录

---

## [0.2.0] - 2026-04-13

### 🎯 评分模型 v2（重大更新）

#### 数据库变更
- ✅ `hl_fills.dir` 字段从 VARCHAR(20) 扩展到 VARCHAR(50)（支持完整清算类型）
- ✅ `hl_address_features` 新增 5 个字段：
  - `liquidation_per_month` - 清算次数/月
  - `has_refill_behavior` - 是否有后续补仓行为
  - `consecutive_loss_add_count` - 连续亏损后加仓次数
  - `add_position_score` - 加仓效果得分（可负）
  - `scalping_score` - 做T行为得分（可负）
- ✅ `hl_fragile_scores` 新增字段：
  - `trading_behavior_score` - 加仓/做T行为得分
  - `total_score` 改为 DECIMAL(10,2)（支持小数和负分）

#### 新脚本
- ✅ `calculate_address_features.py` - 新特征计算引擎
  - 杠杆改为账户整体杠杆（快照数据）
  - 清算识别：官方 + 近似清算（全仓平 + 亏损≥50%）
  - 连续亏损后加仓识别
  - 补仓行为识别
- ✅ `calculate_fragile_scores.py` - 新评分引擎
  - 总分动态（理论 -10~120 分）
  - 仓位利用率引入补仓修正
  - 加仓/做T 双向计分（当前简化版返回 0）

#### 文档更新
- ✅ `docs/SCORING_MODEL_V2.md` - 完整评分规则文档
- ✅ 修复时区问题：`hl_address_list.first_seen_at/last_updated_at` 统一为北京时间

#### 评分体系变更
- **风险行为（35分）**：杠杆(15) + 仓位利用率+补仓修正(10)
- **亏损特征（30分）**：胜率(15) + 清算/月(10) + 总PnL%(5)
- **心态特征（20分）**：连亏后加仓(10) + 追涨杀跌(5) + 死扛(5)
- **加仓/做T（±15分）**：加仓效果(-6~+8) + 做T盈亏(-3~+7)

---

## [0.1.2] - 2026-04-10

### 新增功能
- ✅ `import_coinglass_from_json.py` - 从本地 JSON 文件批量导入 CoinGlass 地址到 `hl_address_list`（单条 SQL 多 VALUES 批量写入）

### 功能优化
- ✅ `fetch_coinglass_addresses.py` - 改用 JSON.parse hook 拦截页面解密后明文，替代原 `window.__req` 方案
- ✅ `fetch_coinglass_addresses.py` - 新增保存原始数据到本地 JSON 文件（`data/` 目录）
- ✅ `fetch_coinglass_addresses.py` - 只写入 remark 14/15/16 地址，label 写入对应中文说明（割肉侠/扛单狂人/爆仓达人）
- ✅ 数据库写入改为批量查重 + 单条 SQL 多 VALUES，避免逐条插入性能问题

### 数据现状（2026-04-10）
- `hl_address_list`：1224 个地址（割肉侠 955 / 扛单狂人 232 / 爆仓达人 36 / 其他 1）
- `hl_fills`：1,229,609 条交易记录

---

## [0.1.1] - 2026-04-09

### 新增功能
- ✅ `fetch_coinglass_addresses.py` - 通过 Playwright 从 CoinGlass 批量抓取 Hyperliquid 地址写入 `hl_address_list`

### 文档更新
- ✅ `SCRIPTS.md` - 补充 `fetch_coinglass_addresses.py` 使用说明（2026-04-10 补录）

---

## [0.1.0] - 2026-04-07

### 新增功能
- ✅ 数据库设计与建表（11 张表 + 1 个视图）
- ✅ Hyperliquid API 数据采集脚本
  - `fetch_address_fills.py` - 全量获取交易历史
  - `fetch_address_fills_incremental.py` - 增量更新交易历史
  - `fetch_all_position_snapshots.py` - 批量获取持仓快照 ⭐
- ✅ 数据库工具类（自动设置时区为北京时间）
- ✅ 完整的项目文档
  - `DATABASE.md` - 数据库设计
  - `HYPERLIQUID_API.md` - API 接口文档
  - `FILL_FIELDS.md` - 字段详解
  - `TIMEZONE_POLICY.md` - 时区策略
  - `SCRIPTS.md` - 脚本使用说明
  - `CRON_JOBS.md` - 定时任务配置（服务器部署）⭐
  - `README.md` - 项目主文档

### 数据库变更

#### hl_fills 表
**新增字段**：
- `fee_token` VARCHAR(10) - 手续费币种（默认 USDC）
- `tid` BIGINT - 成交ID（唯一标识）⭐
- `oid` BIGINT - 订单ID
- `twap_id` VARCHAR(100) - TWAP订单ID
- `start_position` DECIMAL(20,8) - 成交前持仓
- `crossed` BOOLEAN - 是否全仓模式

**索引变更**：
- ❌ 删除 `UNIQUE KEY uk_hash (hash)`
- ✅ 新增 `UNIQUE KEY uk_tid (tid)` ⭐
- ✅ 新增 `INDEX idx_hash (hash)`
- ✅ 新增 `INDEX idx_oid (oid)`

**原因**：
- 一个订单（hash/oid）可能被拆成多笔成交（tid）
- 使用 hash 作为唯一键会丢失数据
- tid 是每笔成交的唯一标识

#### hl_position_snapshots 表
**新增字段**：
- `total_raw_usd` DECIMAL(20,6) - 钱包余额/USD净余额（可为负）
- `total_ntl_pos` DECIMAL(20,6) - 总名义持仓价值
- `withdrawable` DECIMAL(20,6) - 可提现金额

**索引变更**：
- ✅ 新增 `UNIQUE KEY uk_address_time (address, snapshot_time)` ⭐

#### hl_position_details 表
**新增字段**：
- `cum_funding_all_time` DECIMAL(20,6) - 历史累计资金费
- `cum_funding_since_open` DECIMAL(20,6) - 开仓后累计资金费

#### v_order_summary 视图
**新增视图**：订单级别的成交汇总
- 自动聚合同一订单的多笔成交
- 计算总数量、平均价格、总手续费等
- 计算订单前后持仓变化

### 技术改进
- ✅ 统一时区策略（所有时间字段使用北京时间）
- ✅ 批量插入优化（每批 500 条）
- ✅ 增量更新机制（只获取新数据）
- ✅ 去重策略（INSERT IGNORE + tid 唯一键）

### 文档完善
- ✅ 所有路径改为相对路径（便于 Git 分享）
- ✅ 新增 `.gitignore`（排除敏感信息）
- ✅ 新增 `requirements.txt`（依赖清单）
- ✅ 新增 `config/.env.example`（配置模板）

---

## [0.2.0] - 2026-04-08

### 新增功能
- ✅ 持仓快照模块完成（hl_position_snapshots + hl_position_details）
  - `fetch_all_position_snapshots.py` 批量获取所有 active 地址持仓
  - 同时拉取各时间维度 PnL（今日/周/月/历史）
  - snapshot_date 自动归档逻辑（00:xx 执行时归为前一天）
  - Upsert 逻辑（同日重复执行时更新快照 + 重建持仓明细）
- ✅ fills 采集脚本统一（fetch_address_fills_incremental.py）
  - 合并原全量/增量两个脚本为一个统一版本
  - 自动判断：无历史数据 → userFills 全量 2000 条；有历史数据 → userFillsByTime 增量
  - 启用 aggregateByTime=True（合并同一订单的部分成交）
  - 改用 UPSERT（ON DUPLICATE KEY UPDATE）替代 INSERT IGNORE
- ✅ 脆弱地址评分模型（calculate_fragile_scores.py）
  - 总分 100 分：风险行为(35) + 亏损特征(40) + 行为模式(25)
  - 地址分级：L1≥75 / L2≥60 / L3≥40 / L4<40
- ✅ 特征计算引擎（calculate_address_features.py）
  - 胜率、杠杆、持仓时间、保证金使用率等特征计算
- ✅ 服务器部署完成（AWS EC2）
  - 项目路径：/home/ubuntu/CryptoAnalysis
  - 配置 crontab 定时任务（北京时间）

### 定时任务（服务器已配置）
| 时间（北京时间） | 任务 |
|----------------|------|
| 00:00 | fills 增量更新 |
| 00:03 | 持仓快照（snapshot_date 归前一天） |
| 00:10 | 特征计算 |
| 00:20 | 评分计算 |

### 实测评分结果
| 地址 | 分数 | 等级 |
|------|------|------|
| 爆仓达人3（0xf7d4） | 73 | L2 |
| 爆仓达人1（0x697e） | 63 | L2 |
| 爆仓达人2（0xdeea） | 47 | L3 |
| 麻吉大哥（0x020c） | 40 | L3 |

### 数据库变更

#### hl_position_snapshots 表
**新增字段**：
- `pnl_day` DECIMAL(20,6) - 今日 PnL
- `pnl_week` DECIMAL(20,6) - 本周 PnL
- `pnl_month` DECIMAL(20,6) - 本月 PnL
- `pnl_all_time` DECIMAL(20,6) - 历史总 PnL
- `snapshot_date` DATE - 归档日期（用于按天去重）

### 技术改进
- ✅ aggregateByTime=True 全面启用（减少噪音，适合脆弱地址分析）
- ✅ hash 全零时存储为 NULL（0x000...000 → NULL）
- ✅ 数据插入前按 time 字段升序排序

### 维护记录

#### 2026-04-08
- 完成持仓快照模块（hl_position_snapshots + hl_position_details）
- 统一 fills 采集脚本（删除旧版 fetch_address_fills.py）
- 完成特征计算 + 评分模型，实测 4 个地址
- 部署到 AWS EC2 服务器，配置 crontab 定时任务

---

## 下一步计划

### Phase 2: 特征与评分
- [x] 特征计算引擎（胜率、杠杆、持仓时间等）
- [x] 脆弱地址评分模型
- [x] 地址分级（L1/L2/L3/L4）
- [ ] 动态池子管理

### Phase 3: 回测与验证
- [ ] 回测引擎
- [ ] 历史数据准备（90 天）
- [ ] 分类稳定性验证
- [ ] 收益曲线分析

---

## 维护记录

### 2026-04-07
- 创建项目基础结构
- 完成数据采集模块
- 完善项目文档
- 更新 SQL schema 文件

---

**版本说明**：遵循语义化版本 [主版本.次版本.修订号]
