# 更新日志

## [0.1.0] - 2026-04-07

### 新增功能
- ✅ 数据库设计与建表（11 张表 + 1 个视图）
- ✅ Hyperliquid API 数据采集脚本
  - `fetch_address_fills.py` - 全量获取
  - `fetch_address_fills_incremental.py` - 增量更新
- ✅ 数据库工具类（自动设置时区为北京时间）
- ✅ 完整的项目文档
  - `DATABASE.md` - 数据库设计
  - `HYPERLIQUID_API.md` - API 接口文档
  - `FILL_FIELDS.md` - 字段详解
  - `TIMEZONE_POLICY.md` - 时区策略
  - `SCRIPTS.md` - 脚本使用说明
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

## 下一步计划

### Phase 2: 特征与评分
- [ ] 特征计算引擎（胜率、杠杆、持仓时间等）
- [ ] 脆弱地址评分模型
- [ ] 地址分级（L1/L2/L3/L4）
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
