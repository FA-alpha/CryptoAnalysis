# CRON_JOBS.md - 定时任务配置

## 📋 概述

本文档说明如何在服务器上配置定时任务，实现自动化数据采集。

---

## 🖥️ 服务器环境要求

- **操作系统**: Linux (Ubuntu/CentOS 等)
- **Python**: 3.10+
- **数据库连接**: 已配置 `config/.env`
- **定时任务工具**: cron (Linux 自带)

---

## 📦 部署前准备

### 1. 克隆项目到服务器

```bash
# SSH 登录服务器
ssh user@your-server-ip

# 克隆项目
cd /opt
git clone git@github.com:FA-alpha/CryptoAnalysis.git
cd CryptoAnalysis
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置数据库连接

```bash
# 复制配置模板
cp config/.env.example config/.env

# 编辑配置文件（填入真实数据库信息）
vim config/.env
```

**config/.env 内容**：
```ini
DB_HOST=fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=XFGAd9wJYMJqSD7C
DB_NAME=fourieralpha_hl
```

### 4. 测试脚本是否正常运行

```bash
# 测试增量更新脚本
python scripts/fetch_address_fills_incremental.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872

# 测试持仓快照脚本
python scripts/fetch_all_position_snapshots.py
```

---

## ⏰ 定时任务配置

### 1. 编辑 crontab

```bash
crontab -e
```

### 2. 添加定时任务

```cron
# ========================================
# CryptoAnalysis 数据采集定时任务
# ========================================

# 项目路径
PROJECT_DIR=/opt/CryptoAnalysis

# 日志目录
LOG_DIR=/opt/CryptoAnalysis/logs

# ========================================
# 任务 1: 增量更新交易历史（每 5 分钟）
# ========================================
*/5 * * * * cd $PROJECT_DIR && venv/bin/python scripts/fetch_address_fills_incremental.py >> $LOG_DIR/fills_incremental.log 2>&1

# ========================================
# 任务 2: 批量获取持仓快照（每 10 分钟）
# ========================================
*/10 * * * * cd $PROJECT_DIR && venv/bin/python scripts/fetch_all_position_snapshots.py >> $LOG_DIR/position_snapshots.log 2>&1

# ========================================
# 任务 3: 每日数据清理（每天凌晨 2 点）
# ========================================
0 2 * * * cd $PROJECT_DIR && venv/bin/python scripts/daily_cleanup.py >> $LOG_DIR/daily_cleanup.log 2>&1
```

### 3. 保存并退出

- **vim**: 按 `ESC`，输入 `:wq`，回车
- **nano**: 按 `Ctrl+X`，输入 `Y`，回车

### 4. 验证定时任务

```bash
# 查看当前所有定时任务
crontab -l

# 查看 cron 服务状态
sudo systemctl status cron    # Debian/Ubuntu
sudo systemctl status crond   # CentOS/RHEL
```

---

## 📊 定时任务详细说明

### 任务 1: 增量更新交易历史

**脚本**: `scripts/fetch_address_fills_incremental.py`

| 配置项 | 说明 |
|--------|------|
| **执行频率** | 每 5 分钟 (`*/5 * * * *`) |
| **功能** | 从 `hl_address_list` 获取所有活跃地址，增量更新交易历史 |
| **数据源** | Hyperliquid API (`userFillsByTime`) |
| **目标表** | `hl_fills` |
| **日志文件** | `logs/fills_incremental.log` |
| **执行时间** | 约 10-30 秒（取决于地址数量） |

**cron 语法**：
```cron
*/5 * * * * <command>
│   │ │ │ │
│   │ │ │ └─ 星期几 (0-7, 0=周日)
│   │ │ └─── 月份 (1-12)
│   │ └───── 日期 (1-31)
│   └─────── 小时 (0-23)
└────────── 分钟 (0-59)
```

---

### 任务 2: 批量获取持仓快照

**脚本**: `scripts/fetch_all_position_snapshots.py`

| 配置项 | 说明 |
|--------|------|
| **执行频率** | 每 10 分钟 (`*/10 * * * *`) |
| **功能** | 获取所有活跃地址的持仓状态 |
| **数据源** | Hyperliquid API (`clearinghouseState`) |
| **目标表** | `hl_position_snapshots` + `hl_position_details` |
| **日志文件** | `logs/position_snapshots.log` |
| **执行时间** | 约 5-15 秒 |

**数据说明**：
- 每次执行插入新的快照记录（时间序列数据）
- 用于追踪账户价值变化、保证金使用率趋势

---

### 任务 3: 每日数据清理（可选）

**脚本**: `scripts/daily_cleanup.py` (待开发)

| 配置项 | 说明 |
|--------|------|
| **执行频率** | 每天凌晨 2 点 (`0 2 * * *`) |
| **功能** | 清理 90 天以前的快照数据（可选） |
| **目标表** | `hl_position_snapshots`, `hl_position_details` |
| **日志文件** | `logs/daily_cleanup.log` |

**清理策略**（示例）：
```sql
-- 删除 90 天前的快照
DELETE FROM hl_position_snapshots 
WHERE snapshot_time < UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 90 DAY)) * 1000;
```

---

## 📝 日志管理

### 1. 创建日志目录

```bash
mkdir -p /opt/CryptoAnalysis/logs
```

### 2. 查看日志

```bash
# 实时查看增量更新日志
tail -f logs/fills_incremental.log

# 实时查看持仓快照日志
tail -f logs/position_snapshots.log

# 查看最近 100 行
tail -n 100 logs/fills_incremental.log
```

### 3. 日志轮转（防止日志文件过大）

创建 `/etc/logrotate.d/cryptoanalysis`：

```bash
sudo vim /etc/logrotate.d/cryptoanalysis
```

**内容**：
```
/opt/CryptoAnalysis/logs/*.log {
    daily                   # 每天轮转
    rotate 30               # 保留 30 天
    compress                # 压缩旧日志
    delaycompress           # 延迟压缩（保留最新一天不压缩）
    missingok               # 日志文件不存在时不报错
    notifempty              # 空日志不轮转
    create 0644 root root   # 新日志权限
}
```

**手动测试轮转**：
```bash
sudo logrotate -f /etc/logrotate.d/cryptoanalysis
```

---

## 🔍 监控与告警

### 1. 检查任务是否正常执行

```bash
# 查看 cron 执行日志
sudo tail -f /var/log/cron       # CentOS/RHEL
sudo tail -f /var/log/syslog     # Debian/Ubuntu

# 查看最近执行的命令
grep CRON /var/log/syslog | tail -20
```

### 2. 验证数据是否更新

```bash
# 连接数据库
mysql -h fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com -u admin -p fourieralpha_hl

# 查看最新的 fills 数据
SELECT address, coin, dir, FROM_UNIXTIME(time/1000) as trade_time
FROM hl_fills
ORDER BY time DESC
LIMIT 10;

# 查看最新的快照
SELECT address, account_value, FROM_UNIXTIME(snapshot_time/1000) as snapshot_time
FROM hl_position_snapshots
ORDER BY snapshot_time DESC
LIMIT 10;
```

### 3. 告警通知（可选）

**方式 1：失败时发送邮件**

```cron
# 任务失败时自动发送邮件到指定邮箱
MAILTO=your-email@example.com

*/5 * * * * cd /opt/CryptoAnalysis && venv/bin/python scripts/fetch_address_fills_incremental.py >> logs/fills_incremental.log 2>&1 || echo "Fills sync failed at $(date)" | mail -s "CryptoAnalysis Alert" $MAILTO
```

**方式 2：飞书 Webhook 通知**（需在脚本中实现）

在脚本末尾添加：
```python
import requests

def send_lark_notification(message: str):
    webhook_url = "https://open.larksuite.com/open-apis/bot/v2/hook/YOUR_WEBHOOK"
    payload = {
        "msg_type": "text",
        "content": {"text": message}
    }
    requests.post(webhook_url, json=payload)

# 任务失败时调用
if not success:
    send_lark_notification(f"❌ 数据采集失败：{error_message}")
```

---

## ⚙️ 高级配置

### 1. 自定义执行频率

| 需求 | cron 表达式 | 说明 |
|------|-------------|------|
| 每 1 分钟 | `* * * * *` | 高频采集（不推荐，API 限流） |
| 每 5 分钟 | `*/5 * * * *` | 推荐：交易历史增量更新 |
| 每 10 分钟 | `*/10 * * * *` | 推荐：持仓快照 |
| 每小时 | `0 * * * *` | 每小时整点执行 |
| 每天 2 点 | `0 2 * * *` | 每天凌晨 2 点执行 |
| 工作日 9 点 | `0 9 * * 1-5` | 周一到周五 9 点执行 |

### 2. 多地址并行采集（可选）

如果地址数量很多（>100），可以分批执行：

```cron
# 批次 1：每 5 分钟的第 0 分执行
0,5,10,15,20,25,30,35,40,45,50,55 * * * * cd /opt/CryptoAnalysis && venv/bin/python scripts/fetch_batch.py --batch=1

# 批次 2：每 5 分钟的第 2 分执行
2,7,12,17,22,27,32,37,42,47,52,57 * * * * cd /opt/CryptoAnalysis && venv/bin/python scripts/fetch_batch.py --batch=2
```

---

## 🐛 常见问题

### 1. 任务没有执行

**可能原因**：
- cron 服务未启动
- Python 虚拟环境路径错误
- 权限不足

**解决方法**：
```bash
# 检查 cron 服务
sudo systemctl status cron

# 检查脚本权限
chmod +x scripts/*.py

# 手动执行测试
cd /opt/CryptoAnalysis
venv/bin/python scripts/fetch_all_position_snapshots.py
```

### 2. 日志文件为空

**可能原因**：
- 日志目录不存在
- 没有写权限

**解决方法**：
```bash
mkdir -p /opt/CryptoAnalysis/logs
chmod 755 /opt/CryptoAnalysis/logs
```

### 3. 数据库连接失败

**可能原因**：
- `.env` 配置错误
- 服务器 IP 未加入数据库白名单

**解决方法**：
```bash
# 测试数据库连接
mysql -h fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com -u admin -p

# 检查服务器出口 IP
curl ifconfig.me
```

---

## 📚 相关文档

- [脚本使用说明](./SCRIPTS.md)
- [数据库设计](./DATABASE.md)
- [API 接口文档](./HYPERLIQUID_API.md)
- [项目主文档](../README.md)

---

**最后更新**: 2026-04-07
