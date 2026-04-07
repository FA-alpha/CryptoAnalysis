# 脚本使用说明

## 📂 脚本目录

```
scripts/
├── fetch_address_fills.py              # 全量获取交易历史（首次使用）
└── fetch_address_fills_incremental.py  # 增量更新交易历史（日常使用）⭐
```

---

## 🚀 快速开始

### **前置条件**

1. **虚拟环境已激活**
```bash
# 进入项目根目录
cd CryptoAnalysis
source venv/bin/activate
```

2. **数据库配置正确**
检查 `config/.env` 文件：
```bash
DB_HOST=fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=XFGAd9wJYMJqSD7C
DB_NAME=fourieralpha_hl
```

3. **地址已添加到 hl_address_list 表**

---

## 1. fetch_address_fills.py（全量获取）

### **功能说明**
获取指定地址的**全部交易历史**（最多 2000 条）。

### **使用场景**
- ✅ **首次采集**新地址的历史数据
- ✅ 快速获取最近的交易记录

### **命令格式**

```bash
python scripts/fetch_address_fills.py [地址]
```

### **使用示例**

#### **示例 1：指定地址**
```bash
python scripts/fetch_address_fills.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
```

#### **示例 2：使用默认地址**
```bash
# 默认使用脚本中预设的地址（麻吉大哥）
python scripts/fetch_address_fills.py
```

### **输出示例**

```
============================================================
Hyperliquid 地址交易数据获取（优化版）
============================================================

📥 正在获取地址交易数据...
   地址: 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
✅ 成功获取 2000 条 fills

=== 前 3 条数据示例 ===
[1] ETH | Open Long | 数量:12.755 | 价格:2096.8 | PnL:0.0
[2] ETH | Open Long | 数量:2.7733 | 价格:2096.8 | PnL:0.0
[3] ETH | Open Long | 数量:0.9116 | 价格:2096.8 | PnL:0.0

💾 正在批量保存到数据库...
   总数: 2000 条
   进度: 500/2000 (500 条新增)
   进度: 1000/2000 (1000 条新增)
   进度: 1500/2000 (1500 条新增)
   进度: 2000/2000 (2000 条新增)

✅ 保存完成!
   ✓ 新增: 2000 条
   - 重复跳过: 0 条
✅ 已更新地址最后更新时间（北京时间）

============================================================
✅ 完成! 成功保存 2000 条新数据
============================================================
```

### **技术细节**

| 特性 | 说明 |
|------|------|
| **API 接口** | `userFills`（获取最近 2000 条） |
| **批量插入** | 每批 500 条，分 4 批 |
| **去重策略** | `INSERT IGNORE`（基于 tid 唯一键） |
| **时区处理** | 自动使用北京时间（UTC+8） |
| **执行时间** | 约 5-10 秒 |

### **注意事项**

⚠️ **数据量限制**：最多获取最近 2000 条成交记录。如需更多历史数据，使用 `fetch_address_fills_incremental.py`。

---

## 2. fetch_address_fills_incremental.py（增量更新）⭐

### **功能说明**
从**上次更新后**开始获取新的交易记录，避免重复采集。

### **使用场景**
- ✅ **日常定期更新**已有地址的数据
- ✅ 只获取新增的交易（节省 API 调用和时间）
- ✅ 适合集成到定时任务（cron）

### **命令格式**

```bash
python scripts/fetch_address_fills_incremental.py [地址]
```

### **使用示例**

#### **示例 1：指定地址**
```bash
python scripts/fetch_address_fills_incremental.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
```

#### **示例 2：使用默认地址**
```bash
python scripts/fetch_address_fills_incremental.py
```

### **工作原理**

```
1. 查询数据库
   ↓
   SELECT MAX(time) FROM hl_fills WHERE address = ?
   
2. 获取最新时间戳
   ↓
   last_time = 1775539753049
   
3. 从上次时间 +1ms 开始获取
   ↓
   API: userFillsByTime(address, startTime = last_time + 1)
   
4. 批量保存新数据
   ↓
   INSERT IGNORE INTO hl_fills ...
```

### **输出示例**

#### **有新数据时**
```
======================================================================
Hyperliquid 地址交易数据获取（增量更新模式）
======================================================================
📅 数据库中最新记录时间: 2026-04-07 13:29:13

📥 正在获取地址交易数据（增量模式）...
   地址: 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
   起始时间: 1775539753050 (上次时间 +1ms)
✅ 成功获取 10 条 fills

=== 新数据示例（前3条）===
[1] 2026-04-07 14:14:15 | ETH | Open Long | 数量:0.0965 | PnL:0.0
[2] 2026-04-07 14:14:15 | ETH | Open Long | 数量:0.0475 | PnL:0.0
[3] 2026-04-07 14:14:15 | ETH | Open Long | 数量:0.01 | PnL:0.0

💾 正在批量保存到数据库...
   总数: 10 条
   进度: 10/10 (2 条新增)

✅ 保存完成!
   ✓ 新增: 2 条
   - 重复跳过: 8 条
✅ 已更新地址最后更新时间: 2026-04-07 14:35:06

======================================================================
✅ 完成! 成功保存 2 条新数据
======================================================================
```

#### **无新数据时**
```
======================================================================
Hyperliquid 地址交易数据获取（增量更新模式）
======================================================================
📅 数据库中最新记录时间: 2026-04-07 15:03:38

📥 正在获取地址交易数据（增量模式）...
   地址: 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
   起始时间: 1775543005353 (上次时间 +1ms)
✅ 成功获取 0 条 fills

✅ 没有新数据
```

### **技术细节**

| 特性 | 说明 |
|------|------|
| **API 接口** | `userFillsByTime`（按时间获取） |
| **起始时间** | `MAX(time) + 1 ms`（避免重复） |
| **批量插入** | 每批 500 条 |
| **去重策略** | `INSERT IGNORE`（基于 tid 唯一键） |
| **时区处理** | 自动使用北京时间（UTC+8） |
| **执行时间** | 约 2-5 秒（数据少时更快） |

### **优势**

| 对比项 | 全量获取 | 增量更新 ⭐ |
|--------|---------|------------|
| **数据量** | 固定 2000 条 | 只获取新数据 |
| **执行时间** | 5-10 秒 | 2-5 秒 |
| **API 调用** | 每次都获取 2000 条 | 只获取新增部分 |
| **适用场景** | 首次采集 | 日常更新 |

---

## 📅 定时任务配置

### **推荐方案：APScheduler**

创建定时任务脚本：

```python
# scripts/scheduled_update.py
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import subprocess

def update_all_addresses():
    """更新所有活跃地址"""
    print(f"[{datetime.now()}] 开始更新地址数据...")
    
    # 从数据库获取所有活跃地址
    import pymysql
    from utils.db_utils import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT address FROM hl_address_list WHERE status = 'active'")
    addresses = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    # 逐个更新
    for address in addresses:
        print(f"\n更新地址: {address}")
        result = subprocess.run(
            ['python', 'scripts/fetch_address_fills_incremental.py', address],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    
    print(f"[{datetime.now()}] 更新完成!")

# 创建调度器
scheduler = BlockingScheduler()

# 每 5 分钟更新一次
scheduler.add_job(update_all_addresses, 'interval', minutes=5)

print("定时任务已启动，每 5 分钟更新一次...")
scheduler.start()
```

### **运行定时任务**

```bash
python scripts/scheduled_update.py
```

---

## 🔧 故障排查

### **问题 1：ModuleNotFoundError: No module named 'hyperliquid'**

**原因**：虚拟环境未激活或依赖未安装

**解决**：
```bash
cd CryptoAnalysis
source venv/bin/activate
pip install hyperliquid-python-sdk pymysql python-dotenv
```

---

### **问题 2：pymysql.err.OperationalError: Access denied**

**原因**：数据库连接信息错误

**解决**：
检查 `config/.env` 文件：
```bash
cat config/.env
```

确保内容正确：
```
DB_HOST=fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com
DB_USER=admin
DB_PASSWORD=XFGAd9wJYMJqSD7C
DB_NAME=fourieralpha_hl
```

---

### **问题 3：No module named 'utils'**

**原因**：Python 找不到 `utils` 模块

**解决**：
确保在项目根目录运行脚本：
```bash
cd CryptoAnalysis
python scripts/fetch_address_fills_incremental.py <address>
```

---

### **问题 4：时间显示为 UTC 而不是北京时间**

**原因**：数据库连接未设置时区

**解决**：
脚本已自动处理，使用 `utils.db_utils.get_connection()` 即可。

如果手动连接数据库，需要执行：
```python
cursor.execute("SET time_zone = '+08:00'")
```

---

## 📊 数据验证

### **验证插入的数据**

```bash
# 进入 Python 环境
cd CryptoAnalysis
source venv/bin/activate
python
```

```python
from utils.db_utils import get_connection

conn = get_connection()
cursor = conn.cursor()

# 查询总记录数
cursor.execute("SELECT COUNT(*) FROM hl_fills")
print(f"总记录数: {cursor.fetchone()[0]}")

# 查询最新 5 条
cursor.execute("""
    SELECT coin, dir, sz, px, time 
    FROM hl_fills 
    ORDER BY time DESC 
    LIMIT 5
""")

for row in cursor.fetchall():
    print(row)

conn.close()
```

---

## 📚 相关文档

- [数据库设计文档](./DATABASE.md)
- [API 接口文档](./HYPERLIQUID_API.md)
- [字段详解](./FILL_FIELDS.md)
- [时区策略](./TIMEZONE_POLICY.md)

---

## 📝 最佳实践

### **1. 日常使用流程**

```bash
# 首次采集（新地址）
python scripts/fetch_address_fills.py 0x新地址

# 之后每次更新（增量）
python scripts/fetch_address_fills_incremental.py 0x新地址
```

### **2. 批量更新所有地址**

```bash
# 创建批量更新脚本
cat > scripts/update_all.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate

# 从数据库获取所有活跃地址并更新
python -c "
from utils.db_utils import get_connection
import subprocess

conn = get_connection()
cursor = conn.cursor()
cursor.execute(\"SELECT address FROM hl_address_list WHERE status = 'active'\")

for row in cursor.fetchall():
    address = row[0]
    print(f'更新地址: {address}')
    subprocess.run(['python', 'scripts/fetch_address_fills_incremental.py', address])

cursor.close()
conn.close()
"
EOF

chmod +x scripts/update_all.sh
./scripts/update_all.sh
```

### **3. 设置 cron 定时任务**

```bash
# 每 5 分钟更新一次
crontab -e

# 添加以下行（将 /path/to 替换为你的项目路径）
*/5 * * * * cd /path/to/CryptoAnalysis && ./scripts/update_all.sh >> logs/cron.log 2>&1
```

---

**最后更新**: 2026-04-07
