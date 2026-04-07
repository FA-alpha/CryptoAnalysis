# 时区策略

## 统一规则：所有时间使用北京时间（Asia/Shanghai, UTC+8）

### 1. 数据库连接设置
所有数据库连接自动设置会话时区为 `+08:00`：
```python
from utils.db_utils import get_connection

conn = get_connection()  # 自动设置时区
```

### 2. 表中的时间字段
所有 `DATETIME` 字段存储的都是北京时间：

| 表名 | 时间字段 |
|------|---------|
| **hl_address_list** | first_seen_at, last_updated_at, created_at |
| **hl_fills** | created_at |
| **hl_position_snapshots** | created_at |
| **hl_address_features** | calculated_at |
| **hl_fragile_scores** | scored_at |
| **hl_fragile_pool** | last_monitored_at, created_at, updated_at |
| **hl_reverse_signals** | generated_at, executed_at, created_at |
| **hl_follow_trades** | opened_at, closed_at, created_at |
| **hl_monitor_logs** | check_time, created_at |
| **hl_backtest_results** | created_at |

### 3. 插入数据时
使用 `NOW()` 函数自动获取当前北京时间：
```sql
INSERT INTO hl_fills (..., created_at) VALUES (..., NOW())
```

或者在 Python 中使用 `datetime.now()`（连接已设置时区）：
```python
from datetime import datetime
conn = get_connection()
cursor = conn.cursor()
cursor.execute("INSERT INTO ... VALUES (%s, NOW())", (...,))
```

### 4. 查询数据时
查询结果中的时间字段直接就是北京时间，无需转换。

### 5. Hyperliquid API 返回的时间戳
- API 返回的 `time` 字段是 **毫秒级时间戳（UTC）**
- 这个字段单独存储在 `hl_fills.time` 字段中（bigint 类型）
- 不需要转换，保持原始值用于排序和计算

### 6. 迁移说明
- 2026-04-07 已将所有现有数据的时间字段从 UTC 调整为北京时间（+8小时）
- 今后所有新插入的数据自动使用北京时间

---

## 使用示例

### 正确用法 ✅
```python
from utils.db_utils import get_connection

conn = get_connection()
cursor = conn.cursor()

# 插入当前时间（自动使用北京时间）
cursor.execute("INSERT INTO hl_monitor_logs (address, check_time, ...) VALUES (%s, NOW(), ...)", (...,))

# 查询（无需转换）
cursor.execute("SELECT check_time FROM hl_monitor_logs WHERE address = %s", (address,))
beijing_time = cursor.fetchone()[0]  # 直接就是北京时间
```

### 错误用法 ❌
```python
# ❌ 不要使用 pymysql.connect 直接连接（时区不对）
import pymysql
conn = pymysql.connect(host=..., port=..., ...)

# ❌ 不要手动 +8 小时
import datetime
beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
```

---

## 注意事项

1. **必须使用 `utils.db_utils.get_connection()`** 获取数据库连接
2. 不要直接使用 `pymysql.connect()`
3. 所有时间字段查询/插入无需手动转换
4. Hyperliquid API 的 `time` 字段（时间戳）保持原始值，不转换

---

**最后更新**: 2026-04-07
