# CryptoAnalysis - 开发指南

> Hyperliquid 反脆弱策略系统 - 开发文档

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库初始化

```bash
# 连接到 MySQL
mysql -h YOUR_HOST -u YOUR_USER -p

# 创建数据库（如果不存在）
CREATE DATABASE crypto_analysis DEFAULT CHARSET=utf8mb4;

# 导入表结构
USE crypto_analysis;
source sql/schema.sql;

# 验证
SHOW TABLES;
```

### 3. 配置文件

```bash
# 复制配置模板
cp config/config.example.yaml config/config.yaml

# 编辑配置文件，填入真实信息
vim config/config.yaml
```

### 4. 运行测试

```bash
# 运行单元测试
pytest tests/ -v

# 运行覆盖率测试
pytest --cov=src tests/
```

---

## 📁 项目结构

```
CryptoAnalysis/
├── src/                        # 源代码
│   ├── data/                   # 数据采集
│   │   ├── hyperliquid_client.py
│   │   ├── hyperbot_client.py
│   │   └── collector.py
│   ├── features/               # 特征计算
│   │   ├── calculator.py
│   │   └── indicators.py
│   ├── scoring/                # 评分模型
│   │   ├── fragile_scorer.py
│   │   └── classifier.py
│   ├── backtest/               # 回测引擎
│   │   ├── engine.py
│   │   └── metrics.py
│   ├── monitoring/             # 实时监控
│   │   ├── monitor.py
│   │   └── signal_generator.py
│   ├── db/                     # 数据库
│   │   ├── models.py           # ORM 模型
│   │   ├── repository.py       # 数据访问层
│   │   └── migrations/         # 数据库迁移
│   └── utils/                  # 工具函数
│       ├── config.py
│       ├── logger.py
│       └── notifications.py
├── scripts/                    # 可执行脚本
│   ├── init_db.py              # 初始化数据库
│   ├── collect_addresses.py    # 采集地址池
│   ├── calculate_features.py   # 计算特征
│   ├── score_fragile.py        # 评分
│   ├── run_backtest.py         # 回测
│   ├── maintenance_service.py  # 定期维护服务
│   └── realtime_monitor.py     # 实时监控服务
├── tests/                      # 测试
│   ├── test_features/
│   ├── test_scoring/
│   └── test_backtest/
├── config/                     # 配置文件
│   ├── config.yaml             # 实际配置（不提交 Git）
│   └── config.example.yaml     # 配置模板
├── sql/                        # 数据库脚本
│   └── schema.sql              # 建表 SQL
├── logs/                       # 日志目录
├── notebooks/                  # Jupyter 分析笔记本
├── docs/                       # 策略文档
├── requirements.txt            # 依赖列表
├── .gitignore
└── README.md
```

---

## 🔧 开发流程

### Phase 1: 数据采集（当前）

#### 1.1 实现 Hyperliquid 客户端

```python
# src/data/hyperliquid_client.py
from hyperliquid.info import Info

class HyperliquidClient:
    async def get_user_state(address: str) -> dict:
        """获取用户持仓"""
        pass
    
    async def get_user_fills(address: str, start_time: int) -> List[dict]:
        """获取用户交易历史"""
        pass
```

#### 1.2 实现 HyperBot 客户端

```python
# src/data/hyperbot_client.py
class HyperBotClient:
    async def get_smart_addresses(min_balance: float = 10000) -> List[str]:
        """获取候选地址池"""
        pass
```

#### 1.3 数据采集调度器

```python
# src/data/collector.py
class DataCollector:
    async def collect_initial_data(addresses: List[str]):
        """初始批量采集"""
        pass
    
    async def collect_incremental_data(addresses: List[str]):
        """增量更新"""
        pass
```

### Phase 2: 特征计算

#### 2.1 特征计算引擎

```python
# src/features/calculator.py
class FeatureCalculator:
    def calculate_win_rate(fills: List[dict]) -> float:
        """计算胜率"""
        pass
    
    def calculate_leverage(snapshots: List[dict]) -> float:
        """计算平均杠杆"""
        pass
```

### Phase 3: 评分模型

#### 3.1 脆弱地址评分

```python
# src/scoring/fragile_scorer.py
class FragileScorer:
    def calculate_risk_behavior_score(features: dict) -> int:
        """风险行为评分 /40"""
        pass
    
    def calculate_loss_feature_score(features: dict) -> int:
        """亏损特征评分 /35"""
        pass
    
    def calculate_mentality_score(features: dict) -> int:
        """心态特征评分 /25"""
        pass
```

### Phase 4: 回测验证

#### 4.1 回测引擎

```python
# src/backtest/engine.py
class BacktestEngine:
    def run_backtest(
        addresses: List[str],
        period_start: int,
        period_end: int
    ) -> BacktestResult:
        """运行回测"""
        pass
```

### Phase 5: 实时监控

#### 5.1 监控服务

```python
# src/monitoring/monitor.py
class RealtimeMonitor:
    async def monitor_loop():
        """实时监控循环"""
        pass
```

---

## 📊 数据库设计要点

### 表关系

```
address_list → fills
            → position_snapshots → position_details
            → address_features → fragile_scores → fragile_pool
                                                 → reverse_signals → follow_trades
            → backtest_results

fragile_pool → monitor_logs
```

### 关键索引

- `fills.hash`: 唯一键（去重）
- `fills.address + time`: 复合索引（查询优化）
- `fragile_pool.monitor_status`: 监控查询优化

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_features/test_calculator.py
def test_calculate_win_rate():
    fills = [...]
    win_rate = calculate_win_rate(fills)
    assert win_rate == 0.55
```

### 集成测试

```python
# tests/test_data/test_hyperliquid_client.py
@pytest.mark.asyncio
async def test_get_user_state():
    client = HyperliquidClient()
    state = await client.get_user_state(TEST_ADDRESS)
    assert state['marginSummary']['accountValue'] > 0
```

---

## 📝 代码规范

### 必须遵守

1. **类型提示**：所有函数必须有类型提示
2. **Docstring**：使用 Google Style
3. **异常处理**：关键操作必须 try-except
4. **日志记录**：使用 logging，不用 print
5. **代码格式化**：使用 Black

### 示例

```python
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

async def fetch_user_data(
    address: str,
    retry: int = 3
) -> Optional[dict]:
    """
    获取用户数据
    
    Args:
        address: 钱包地址
        retry: 重试次数
        
    Returns:
        用户数据字典，失败返回 None
        
    Raises:
        ValueError: 地址格式错误
    """
    try:
        # 实现逻辑
        pass
    except Exception as e:
        logger.error(f"获取用户数据失败: {e}", exc_info=True)
        return None
```

---

## 🚨 常见问题

### 1. Hyperliquid API 限流

**问题**：频繁调用 API 被限流  
**解决**：使用指数退避重试，控制并发数

### 2. 数据库连接池耗尽

**问题**：高并发时连接池满  
**解决**：增加 pool_size，及时关闭连接

### 3. 内存占用过高

**问题**：批量处理数据时内存占用高  
**解决**：分批处理，使用流式查询

---

## 🔗 相关文档

- [Hyperliquid API 文档](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)
- [HyperBot API 文档](https://openapi-docs.hyperbot.network/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [pytest 文档](https://docs.pytest.org/)

---

*持续迭代，数据驱动，稳健交付。*
