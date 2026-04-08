# CRON_JOBS.md - 服务器定时任务配置指南

## 📋 概述

本文档说明如何在 Linux 服务器上配置 cron 定时任务，实现每日自动化数据采集。

---

## 🖥️ 环境要求

- **操作系统**: Linux（Ubuntu / CentOS 均可）
- **Python**: 3.10+（使用项目 venv）
- **数据库**: 已配置 `config/.env`，服务器 IP 已加入数据库白名单

---

## 📦 部署步骤

### 1. 拉取项目到服务器

```bash
ssh user@your-server-ip
cd /opt
git clone git@github.com:FA-alpha/CryptoAnalysis.git
cd CryptoAnalysis
```

### 2. 安装依赖

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. 配置数据库连接

```bash
cp config/.env.example config/.env
vim config/.env
```

```ini
DB_HOST=fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=XFGAd9wJYMJqSD7C
DB_NAME=fourieralpha_hl
```

### 4. 创建日志目录

```bash
mkdir -p /opt/CryptoAnalysis/logs
```

### 5. 验证脚本可正常运行

```bash
cd /opt/CryptoAnalysis

# 测试持仓快照
venv/bin/python scripts/fetch_all_position_snapshots.py

# 测试 fills 增量更新
venv/bin/python scripts/fetch_address_fills_incremental.py
```

---

## ⏰ 定时任务配置

### 推荐任务安排

| 时间（北京时间） | 任务 | 说明 |
|----------------|------|------|
| **00:00** | fills 增量更新 | 获取当日新增成交记录 |
| **00:03** | 持仓快照 | `snapshot_date` 自动归为前一天 |
| **00:30** | 特征计算 | 依赖 fills + 快照数据 |
| **00:45** | 评分计算 | 依赖特征计算结果 |

> 00:03 执行持仓快照时，`snapshot_date` 自动归为**前一天**（代表昨日收盘状态），这是脚本内置的逻辑。

---

### 配置 crontab

```bash
crontab -e
```

粘贴以下内容（**将 `/opt/CryptoAnalysis` 替换为实际路径**）：

```cron
# ============================================================
# CryptoAnalysis 数据采集定时任务
# 时区：Asia/Shanghai（北京时间）
# ============================================================
CRON_TZ=Asia/Shanghai

# 00:00 fills 增量更新（新地址自动全量，已有地址增量）
0 0 * * * /opt/CryptoAnalysis/venv/bin/python /opt/CryptoAnalysis/scripts/fetch_address_fills_incremental.py >> /opt/CryptoAnalysis/logs/fills.log 2>&1

# 00:03 持仓快照（snapshot_date 自动归为前一天）
3 0 * * * /opt/CryptoAnalysis/venv/bin/python /opt/CryptoAnalysis/scripts/fetch_all_position_snapshots.py >> /opt/CryptoAnalysis/logs/snapshot.log 2>&1

# 00:30 特征计算（依赖 fills + 快照数据）
30 0 * * * /opt/CryptoAnalysis/venv/bin/python /opt/CryptoAnalysis/scripts/calculate_address_features.py >> /opt/CryptoAnalysis/logs/features.log 2>&1

# 00:45 评分计算（依赖特征计算结果）
45 0 * * * /opt/CryptoAnalysis/venv/bin/python /opt/CryptoAnalysis/scripts/calculate_fragile_scores.py >> /opt/CryptoAnalysis/logs/scores.log 2>&1
```

> ⚠️ **关键注意事项**：
> - cron 中必须用 **venv 的完整路径**（`/opt/.../venv/bin/python`），不能用 `source activate`
> - `CRON_TZ=Asia/Shanghai` 确保时区正确，否则 00:03 会按服务器时区执行
> - 日志用 `>>` 追加，`2>&1` 同时捕获错误输出

### 验证 crontab 已生效

```bash
crontab -l
```

---

## 📊 确认服务器时区

```bash
timedatectl | grep "Time zone"
```

- 如果服务器已是 `Asia/Shanghai` → crontab 里可以不写 `CRON_TZ`
- 如果是 UTC 或其他时区 → **必须加 `CRON_TZ=Asia/Shanghai`**

---

## 📝 日志管理

### 实时查看日志

```bash
# 持仓快照日志
tail -f /opt/CryptoAnalysis/logs/snapshot.log

# fills 更新日志
tail -f /opt/CryptoAnalysis/logs/fills.log
```

### 配置日志自动轮转（防止文件过大）

```bash
sudo vim /etc/logrotate.d/cryptoanalysis
```

```
/opt/CryptoAnalysis/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

---

## 🔍 排查问题

### 任务没有执行

```bash
# 查看 cron 执行记录
grep CRON /var/log/syslog | tail -30       # Ubuntu/Debian
grep CRON /var/log/cron | tail -30         # CentOS/RHEL

# 检查 cron 服务状态
sudo systemctl status cron                  # Ubuntu/Debian
sudo systemctl status crond                 # CentOS/RHEL
```

### 手动模拟定时任务环境执行

```bash
# 完全模拟 cron 执行环境（无交互式 shell）
env -i HOME=/root /opt/CryptoAnalysis/venv/bin/python /opt/CryptoAnalysis/scripts/fetch_all_position_snapshots.py
```

### 服务器 IP 未加入数据库白名单

```bash
# 查看服务器出口 IP
curl ifconfig.me

# 然后在数据库控制台将该 IP 加入安全组/白名单
```

### 日志目录无权限

```bash
mkdir -p /opt/CryptoAnalysis/logs
chmod 755 /opt/CryptoAnalysis/logs
```

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [SCRIPTS.md](./SCRIPTS.md) | 脚本详细使用说明 |
| [DATABASE.md](./DATABASE.md) | 数据库表结构 |
| [TIMEZONE_POLICY.md](./TIMEZONE_POLICY.md) | 时区策略 |

---

**最后更新**: 2026-04-08
