# CLAUDE.md - CryptoAnalysis 项目记忆

> 🔴 **强制读取**：在处理此项目任何任务前，必须先读完本文件！

## 项目信息

| 项目 | 说明 |
|------|------|
| **名称** | CryptoAnalysis |
| **分支** | dev1 (开发分支) |
| **数据库** | fourieralpha_hl (MySQL) |
| **核心策略** | 反脆弱策略 (Anti-Fragile Strategy) |

## 核心目标

```
Alpha = 聪明钱正向跟单 (30-40%) + 脆弱地址反向操作 (50-60%)
```

## 🔴 关键约定（Gotcha 索引）

| ID | 类型 | 标题 | 影响 |
|----|------|------|------|
| G001 | 🔴 gotcha | time 字段是毫秒不是秒 | 时间计算错误 |
| G002 | 🔴 gotcha | dir 字段枚举值复杂 | 漏掉清算记录 |
| G003 | 🔴 gotcha | dev1 表必须加 _dev1 后缀 | 污染生产数据 |
| G004 | 🟤 decision | 止盈止损比权重最高 (30%) | 模型设计 |

### G001: time 字段是毫秒
```sql
-- ❌ 错误
FROM_UNIXTIME(time)

-- ✅ 正确
FROM_UNIXTIME(time/1000)
```

### G002: dir 字段枚举
```
Buy, Sell, Open Long, Open Short, Close Long, Close Short
Liquidated Cross Long/Short, Liquidated Isolated Long/Short
Auto-Deleveraging, Add Margin, Remove Margin
```

### G003: 表命名规范
- 生产表: `hl_*`
- dev1 分支: `hl_*_dev1`
- 临时表: `tmp_*`

## 目录结构

```
CryptoAnalysis/
├── docs/                         # 策略文档
│   ├── ANTI_FRAGILE_STRATEGY.md  # 核心策略
│   ├── FRAGILE_MODEL_V3.md       # 脆弱模型最新版
│   └── DATA_REQUIREMENTS.md      # API 数据需求
├── src/
│   ├── data/                     # 数据采集
│   │   └── hyperliquid.py        # HL API 封装
│   ├── strategies/               # 策略实现
│   └── backtest/                 # 回测引擎
├── sql/
│   └── fragile_model_v2.sql      # 脆弱模型 SQL
└── config/
    └── config.example.yaml       # 配置模板
```

## 当前开发重点

1. **脆弱模型 V3** - 基于 `docs/FRAGILE_MODEL_V3.md`
2. **SQL 特征计算** - `sql/fragile_model_v2.sql`
3. **评分逻辑实现** - Python 模型封装

## 快速命令

```bash
# 切换分支
git checkout dev1

# 查看策略文档
cat docs/ANTI_FRAGILE_STRATEGY.md

# 查看最新模型设计
cat docs/FRAGILE_MODEL_V3.md
```

## 相关文档

- [反脆弱策略](docs/ANTI_FRAGILE_STRATEGY.md) - 策略总览
- [脆弱模型 V3](docs/FRAGILE_MODEL_V3.md) - 最新模型设计
- [数据需求](docs/DATA_REQUIREMENTS.md) - API 对比

---

**Pre-Check 流程**：
1. ✅ 读完本文件
2. 检查 Gotcha 索引是否有相关项
3. 涉及数据库 → 确认表名后缀
4. 涉及时间 → 记住毫秒转换
