# CryptoAnalysis - Hyperliquid 反脆弱策略系统

## 📝 项目简介

基于 Hyperliquid 链上数据的量化交易策略系统，核心策略：识别脆弱地址（高杠杆、低胜率、频繁爆仓），反向跟单获利。

**当前阶段**：MVP 开发 - 数据采集 + 特征计算 + 评分模型 + 回测验证

---

## 📂 项目结构

```
CryptoAnalysis/
├── config/                      # 配置文件
│   ├── .env                     # 数据库连接信息（敏感，不提交）
│   ├── config.yaml              # 主配置文件
│   └── config.example.yaml      # 配置模板
├── docs/                        # 文档
│   ├── DATABASE.md              # 数据库设计文档
│   ├── HYPERLIQUID_API.md       # API 接口文档
│   ├── FILL_FIELDS.md           # 字段详解
│   ├── TIMEZONE_POLICY.md       # 时区策略
│   └── SCRIPTS.md               # 脚本使用说明
├── scripts/                     # 数据采集脚本
│   ├── fetch_address_fills.py              # 全量获取交易历史
│   └── fetch_address_fills_incremental.py  # 增量更新（推荐）
├── utils/                       # 工具类
│   └── db_utils.py              # 数据库连接工具（自动设置时区）
├── sql/                         # SQL 文件
│   └── schema.sql               # 数据库表结构
├── venv/                        # 虚拟环境
├── logs/                        # 日志目录
├── AGENTS.md                    # 开发流程规范
├── SOUL.md                      # 项目定位与风格
├── TOOLS.md                     # 工具与配置
├── IDENTITY.md                  # 身份定义
├── USER.md                      # 用户信息
├── HEARTBEAT.md                 # 心跳任务
└── requirements.txt             # Python 依赖
```

---

## 🚀 快速开始

### **1. 环境准备**

#### **克隆项目**
```bash
git clone <repository-url>
cd CryptoAnalysis
```

#### **创建虚拟环境**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

#### **安装依赖**
```bash
pip install -r requirements.txt
```

**主要依赖**：
- `hyperliquid-python-sdk` - Hyperliquid API 客户端
- `pymysql` - MySQL 数据库驱动
- `python-dotenv` - 环境变量管理

---

### **2. 配置数据库**

#### **复制配置模板**
```bash
cp config/config.example.yaml config/config.yaml
cp config/.env.example config/.env
```

#### **编辑 config/.env**
```bash
# 数据库配置
DB_HOST=your_mysql_host
DB_PORT=3306
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=fourieralpha_hl

# 飞书 Webhook（可选）
LARK_WEBHOOK=https://open.larksuite.com/open-apis/bot/v2/hook/...
```

#### **创建数据库表**
```bash
mysql -h <host> -u <user> -p <database> < sql/schema.sql
```

---

### **3. 添加监控地址**

```bash
# 进入 Python 环境
source venv/bin/activate
python
```

```python
from utils.db_utils import get_connection
from datetime import datetime

conn = get_connection()
cursor = conn.cursor()

# 插入地址
cursor.execute("""
    INSERT INTO hl_address_list 
    (address, label, source, first_seen_at, last_updated_at, status)
    VALUES (%s, %s, %s, %s, %s, %s)
""", (
    '0x020ca66c30bec2c4fe3861a94e4db4a498a35872',
    '麻吉大哥',
    'manual',
    datetime.now(),
    datetime.now(),
    'active'
))

conn.commit()
cursor.close()
conn.close()
```

---

### **4. 采集数据**

#### **首次全量获取**
```bash
python scripts/fetch_address_fills.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
```

#### **增量更新（推荐）**
```bash
python scripts/fetch_address_fills_incremental.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
```

---

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [DATABASE.md](docs/DATABASE.md) | 数据库设计（11 张表 + 1 个视图） |
| [HYPERLIQUID_API.md](docs/HYPERLIQUID_API.md) | API 接口文档（6 个接口） |
| [FILL_FIELDS.md](docs/FILL_FIELDS.md) | 字段详解（真实示例） |
| [TIMEZONE_POLICY.md](docs/TIMEZONE_POLICY.md) | 时区策略（北京时间） |
| [SCRIPTS.md](docs/SCRIPTS.md) | 脚本使用说明 |

---

## 🗄️ 数据库表清单

| 表名 | 说明 | 状态 |
|------|------|------|
| **hl_address_list** | 地址列表 | ✅ 使用中 |
| **hl_fills** | 交易历史（原始成交数据） | ✅ 使用中 |
| **v_order_summary** | 订单汇总视图 | ✅ 使用中 |
| hl_position_snapshots | 持仓快照 | 🚧 待开发 |
| hl_address_features | 地址特征 | 🚧 待开发 |
| hl_fragile_scores | 脆弱地址评分 | 🚧 待开发 |
| hl_fragile_pool | 脆弱地址池 | 🚧 待开发 |
| hl_reverse_signals | 反向跟单信号 | 🚧 待开发 |
| hl_follow_trades | 跟单交易记录 | 🚧 待开发 |
| hl_monitor_logs | 实时监控日志 | 🚧 待开发 |
| hl_backtest_results | 回测结果 | 🚧 待开发 |

---

## 🛠️ 开发规范

### **代码规范**
- ✅ Python 类型提示（Type Hints）
- ✅ Google Style Docstring
- ✅ 异常处理 + 日志记录
- ✅ 单一职责，函数不超过 50 行

详见：[AGENTS.md](AGENTS.md)

### **时区策略**
- 所有 `DATETIME` 字段使用北京时间（Asia/Shanghai, UTC+8）
- 必须使用 `utils.db_utils.get_connection()` 获取数据库连接

详见：[docs/TIMEZONE_POLICY.md](docs/TIMEZONE_POLICY.md)

---

## 📊 数据流

```
API 采集
   ↓
hl_fills（原始成交数据）
   ↓
v_order_summary（订单汇总视图）
   ↓
特征计算（胜率、杠杆、持仓时间等）
   ↓
脆弱地址评分
   ↓
反向信号生成
```

---

## 🔄 开发路线图

### **Phase 1: 数据基础**（当前）
- [x] 数据库设计与建表
- [x] Hyperliquid SDK 封装
- [x] 数据采集脚本（全量 + 增量）
- [ ] HyperBot API 客户端
- [ ] 数据采集调度器

### **Phase 2: 特征与评分**
- [ ] 特征计算引擎（胜率、杠杆、持仓时间等）
- [ ] 脆弱地址评分模型
- [ ] 地址分级（L1/L2/L3/L4）
- [ ] 动态池子管理

### **Phase 3: 回测与验证**
- [ ] 回测引擎
- [ ] 历史数据准备（90 天）
- [ ] 分类稳定性验证
- [ ] 反向操作模拟
- [ ] 收益曲线分析

### **Phase 4: 实时监控**
- [ ] 实时监控服务（每 1 分钟）
- [ ] 反向信号生成
- [ ] 信号推送（飞书/Telegram）
- [ ] 监控日志与告警

### **Phase 5: 交易执行**
- [ ] Hyperliquid 交易 API 集成
- [ ] 仓位管理
- [ ] 熔断机制
- [ ] 风控系统

---

## 🔧 故障排查

### **虚拟环境问题**
```bash
# 删除旧环境
rm -rf venv

# 重新创建
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### **数据库连接失败**
- 检查 `config/.env` 配置是否正确
- 测试数据库连接：`python utils/db_utils.py`

### **时区问题**
- 必须使用 `utils.db_utils.get_connection()`
- 不要直接使用 `pymysql.connect()`

---

## 📝 维护日志

### 2026-04-07
- ✅ 创建数据库表结构（11 张表）
- ✅ 实现数据采集脚本（全量 + 增量）
- ✅ 创建订单汇总视图（v_order_summary）
- ✅ 完善项目文档（5 个 MD 文档）
- ✅ 统一时区策略（北京时间）

---

## 📞 联系方式

- **Telegram**: @aylwins
- **项目地址**: [GitHub](https://github.com/...)

---

## 📄 开源协议

MIT License

---

**最后更新**: 2026-04-07
