# 脚本使用说明

## 📂 脚本目录

```
scripts/
├── fetch_coinglass_addresses.py         # 从 CoinGlass 抓取 Hyperliquid 地址写入 DB（Playwright）⭐ 地址来源
├── import_coinglass_from_json.py        # 从本地 JSON 批量导入 CoinGlass 地址（离线导入）
├── fetch_address_fills_incremental.py   # 统一版 fills 采集（全量/增量自动判断）⭐ 日常使用
├── fetch_address_fills_backfill.py      # 历史 fills 补采（仅在需要补 90 天历史时手动执行一次）
├── fetch_all_position_snapshots.py      # 批量获取持仓快照（含 PnL）⭐
├── fetch_position_snapshots.py          # 单地址持仓快照
├── calculate_address_features.py        # 地址特征计算
└── calculate_fragile_scores.py          # 脆弱地址评分
```

---

## 1. fetch_coinglass_addresses.py（CoinGlass 地址采集）⭐ 地址来源

### 功能说明

通过 **Playwright** 启动无头浏览器，访问 CoinGlass 的 Hyperliquid 地址排行页，注入 JS 调用页面内部 `bSK` 函数（自动解密）批量获取地址列表，并写入 `hl_address_list` 表。

> 原理：CoinGlass 页面使用了加密 API，直接 HTTP 调用无法绕过。通过 Playwright 加载真实页面后，调用页面已解密的内部模块（`window.__req('94126').bSK`）拿到明文数据。

### 依赖

```bash
pip install playwright
playwright install chromium
```

### 使用方式

```bash
# 默认：groupId=15，获取 5 页（100 个地址）
python scripts/fetch_coinglass_addresses.py

# 指定 groupId
python scripts/fetch_coinglass_addresses.py --group 15

# 指定页数（每页 20 条，10 页 = 200 个地址）
python scripts/fetch_coinglass_addresses.py --pages 10

# 同时指定 groupId 和页数
python scripts/fetch_coinglass_addresses.py --group 15 --pages 10
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--group` | 15 | CoinGlass groupId（对应特定资产规模区间） |
| `--pages` | 5 | 获取页数，每页 20 条（5 页 = 100 个地址） |

### 执行流程

```
启动 Chromium（headless）
   ↓
访问 https://www.coinglass.com/zh/hl/range/{group_id}（等待 networkidle）
   ↓
注入 JS：并发调用 window.__req('94126').bSK() 获取多页数据
   ↓
解析 JSON 结果（address / margin / biasRemark 等字段）
   ↓
逐条检查 hl_address_list 是否已存在（按 address 去重）
   ↓
INSERT 新地址（source = 'coinglass_g{group_id}'）
   ↓
输出统计：新增 N 个 / 跳过 N 个
```

### 输出示例

```
2026-04-09 10:00:00 | INFO | 启动浏览器，访问: https://www.coinglass.com/zh/hl/range/15
2026-04-09 10:00:08 | INFO | 页面加载完成
2026-04-09 10:00:09 | INFO | 成功获取 100 个地址（总计: 3248）

=== 地址预览（前 5 个）===
  0xf7d48932f456e98d2ff824e38830e8f59de13f4a | margin: $20,019 | bias: 多
  0x697e38f69d0b7f253e50267c355177830bad6387 | margin: $15,432 | bias: 空
  ...

保存完成：新增 97 个，跳过 3 个（已存在）

============================================================
完成！新增: 97 | 跳过: 3
============================================================
```

### 写入字段说明

| 字段 | 值 | 说明 |
|------|----|------|
| `address` | 小写地址 | 统一转小写 |
| `label` | NULL | 暂不设置 |
| `source` | `coinglass_g{group_id}` | 来源标识 |
| `status` | `active` | 默认激活 |
| `first_seen_at` | 当前时间 | 首次发现时间 |
| `last_updated_at` | 当前时间 | 最后更新时间 |

### 地址过滤规则

只写入 `remark` 为以下值的地址，其余跳过：

| remark | label | 说明 |
|--------|-------|------|
| `14` | 割肉侠 | 频繁止损割肉 |
| `15` | 扛单狂人 | 长期持有亏损仓位 |
| `16` | 爆仓达人 | 历史多次爆仓 |

同时会将原始数据（所有 remark）保存为本地 JSON 文件（`data/coinglass_g{group_id}_{timestamp}.json`），方便离线分析。

### 注意事项

- ⚠️ 依赖 Playwright JSON.parse hook 拦截解密后的明文，CoinGlass 前端重构后可能失效，需重新验证
- 此脚本为**手动运行**，不建议放入 cron（页面结构可能随时变化）
- 建议定期（每周/每月）手动执行一次以补充新地址
- 如网络原因导致脚本中断，可用 `import_coinglass_from_json.py` 从已保存的 JSON 重新导入

---

## 2. import_coinglass_from_json.py（离线导入 CoinGlass 地址）

### 功能说明

当 `fetch_coinglass_addresses.py` 已保存了本地 JSON 但数据库写入中断时，用此脚本从 JSON 文件直接导入，无需重新抓取页面。

### 使用方式

```bash
python scripts/import_coinglass_from_json.py data/coinglass_g3_20260410_113305.json
```

### 过滤规则

与 `fetch_coinglass_addresses.py` 一致，只导入 remark 14/15/16，`source` 固定为 `coinglass`。

### 写入性能

使用单条 SQL 多 VALUES 批量插入（每批 500 条），1200+ 条地址约 10 秒完成。

---

## 3. fetch_address_fills_incremental.py（统一版 fills 采集）⭐ 日常使用

### 功能说明

统一处理交易历史（fills）的采集，**自动判断全量或增量**：

- **无历史数据**（新地址）→ `userFills`，获取最近 2000 条
- **有历史数据** → `userFillsByTime`，从上次最新时间开始增量拉取

均使用 `aggregateByTime=True`（合并同一笔订单的部分成交），UPSERT 保存（按 `tid` 去重）。

### 使用方式

```bash
# 批量模式：处理 hl_address_list 中所有 active 地址（推荐）
python scripts/fetch_address_fills_incremental.py

# 单地址模式
python scripts/fetch_address_fills_incremental.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
```

### 执行流程

```
读取所有 active 地址（hl_address_list）
   ↓ 对每个地址：
查询 MAX(time) FROM hl_fills WHERE address = ?
   ├── 无记录 → userFills（全量 2000 条）
   └── 有记录 → userFillsByTime（从最新时间开始）
   ↓
UPSERT 保存（ON DUPLICATE KEY UPDATE，按 tid 唯一键）
   ↓
更新 hl_address_list.last_updated_at
   ↓
地址间等待 1 秒（避免 API 限流）
```

### 输出示例

```
======================================================================
Hyperliquid 地址交易数据获取（批量模式）
======================================================================
📋 共找到 4 个活跃地址

======================================================================
[1/4] 处理地址: 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
======================================================================
📅 数据库中最新记录时间: 2026-04-08 15:59:08
   模式: 增量（起始时间: 2026-04-08 15:59:08）
✅ 成功获取 2 条 fills
✅ 保存完成! 总影响行数: 1

======================================================================
[2/4] 处理地址: 0x697e38f69d0b7f253e50267c355177830bad6387
======================================================================
📅 数据库中无该地址记录，将全量获取最近 2000 条
   模式: 全量获取（最近 2000 条）
✅ 成功获取 364 条 fills
✅ 保存完成! 总影响行数: 364

🎯 批量处理完成: 成功 4 / 失败 0 / 总计 4
```

### 技术细节

| 特性 | 说明 |
|------|------|
| API 接口 | 全量用 `userFills`，增量用 `userFillsByTime` |
| 聚合模式 | `aggregateByTime=True` |
| 存储策略 | `INSERT ... ON DUPLICATE KEY UPDATE`（按 `tid`） |
| 批量大小 | 每批 500 条 |
| 限流保护 | 地址间间隔 1 秒 |

---

## 4. fetch_address_fills_backfill.py（历史数据补采）

### 功能说明

专门用于**回溯超过 2000 条的历史数据**，按 30 天为一批次往前回溯，直到达到目标天数（默认 90 天）。

> ⚠️ **仅在以下场景手动执行一次**：
> - 新地址刚加入，需要补齐 90 天完整历史
> - `fetch_address_fills_incremental.py` 全量只能拿最近 2000 条，不足以覆盖 90 天时
> - **日常增量更新请使用 `fetch_address_fills_incremental.py`，不要用此脚本**

### 与 incremental 的区别

| 对比项 | incremental（日常） | backfill（补历史） |
|--------|--------------------|-----------------|
| 使用场景 | 每日 cron 定时运行 | 手动执行一次 |
| 数据范围 | 最近 2000 条 / 增量 | 往前回溯 90 天 |
| 批量模式 | ✅ 支持所有 active 地址 | ❌ 仅单地址 |
| 写入方式 | UPSERT（ON DUPLICATE KEY UPDATE） | INSERT IGNORE |

### 使用方式

```bash
# 补采单个地址（默认回溯 90 天）
python scripts/fetch_address_fills_backfill.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872

# 补采单个地址，指定回溯天数
python scripts/fetch_address_fills_backfill.py 0x020ca66c30bec2c4fe3861a94e4db4a498a35872 180
```

### 执行流程

```
查询数据库中最早的 fill 时间
   ↓
计算目标时间（当前时间 - 90 天）
   ↓
如果已有足够数据 → 直接退出
   ↓
按 30 天为一批次，往前回溯
   ├── userFillsByTime（按时间范围获取）
   ├── INSERT IGNORE 保存（按 tid 去重）
   └── 每批延迟 1 秒（避免 API 限流）
   ↓
输出最终数据范围（最早/最新/总条数）
```

---

## 5. fetch_all_position_snapshots.py（批量持仓快照）⭐

### 功能说明

批量获取所有 active 地址的当前持仓状态，同时拉取各时间维度 PnL，按 `snapshot_date` 归档。

**数据来源**：
- 持仓状态：Hyperliquid `clearinghouseState` 接口
- PnL 数据：Hyperliquid `portfolio` 接口（perpDay / perpWeek / perpMonth / perpAllTime）

**存储逻辑（Upsert by address + snapshot_date）**：
- 当日首次执行 → INSERT 快照 + INSERT 持仓明细
- 当日重复执行 → UPDATE 快照 + DELETE 旧明细 + INSERT 新明细

### snapshot_date 判断规则

| 执行时间 | snapshot_date | 说明 |
|---------|---------------|------|
| 北京时间 00:xx（定时任务） | 前一天 | 代表昨日收盘数据 |
| 其他时间（手动执行） | 当天 | 代表今日实时数据 |

> 例：00:03 执行，`snapshot_date = 2026-04-08`，代表 4 月 8 日的快照数据。

### 使用方式

```bash
# 批量处理所有 active 地址
python scripts/fetch_all_position_snapshots.py
```

### 输出示例

```
======================================================================
批量获取地址持仓快照
开始时间: 2026-04-08 17:26:27
======================================================================
📋 正在获取地址列表...
✅ 找到 4 个活跃地址

[1/4] 爆仓达人
   地址: 0xf7d48932f456e98d2ff824e38830e8f59de13f4a
   💰 账户价值: 20018.783317 USDC
   📊 持仓数量: 1 个
   📈 今日/周/月/历史 PnL: 12458.16 / -56135.89 / -99689.30 / -1597560.07
   📅 snapshot_date: 2026-04-08
   ✓ 新增快照（snapshot_date=2026-04-08, id=11）
   ✅ 保存成功

[4/4] 麻吉大哥
   地址: 0x020ca66c30bec2c4fe3861a94e4db4a498a35872
   💰 账户价值: 2545649.193248 USDC
   📊 持仓数量: 1 个
   📈 今日/周/月/历史 PnL: 1206846.60 / 1158615.05 / 467155.47 / -27825102.63
   📅 snapshot_date: 2026-04-08
   🔄 已更新当日快照（snapshot_date=2026-04-08, id=14）
   ✅ 保存成功

======================================================================
统计:
  ✅ 成功: 4 / ⚠️ 跳过: 0 / ❌ 失败: 0 / 📋 总计: 4
```

### 数据写入关系

```
每次执行写入：
  hl_position_snapshots（1 条/地址）
    ├── account_value、total_margin_used、withdrawable ...
    ├── pnl_day、pnl_week、pnl_month、pnl_all_time
    └── snapshot_date（归档日期）
         ↓ snapshot_id
  hl_position_details（N 条/地址，N = 持仓币种数）
    ├── coin、szi、entry_px、unrealized_pnl ...
    └── leverage_type、leverage_value、liquidation_px ...
```

### 技术细节

| 特性 | 说明 |
|------|------|
| 持仓接口 | Hyperliquid SDK `info.user_state()` |
| PnL 接口 | `POST /info { type: portfolio }` |
| Upsert 逻辑 | 按 `address + snapshot_date` 查重 |
| 持仓明细更新 | DELETE + INSERT（保证与快照一致） |

---

## 6. 定时任务配置（服务器部署）

> ⚠️ 详见 [CRON_JOBS.md](./CRON_JOBS.md)，以下为快速参考。

### 推荐定时安排

| 任务 | 时间（北京时间） | 说明 |
|------|----------------|------|
| 持仓快照 | 每天 00:03 | `snapshot_date` 自动归为前一天 |
| fills 增量更新 | 每天 00:05 | 获取前一天新增成交 |
| 特征计算 | 每天 00:30 | 依赖快照和 fills 数据 |
| 实时监控 | 每 5 分钟（后期） | 监控持仓变化，生成信号 |

### crontab 配置示例

```bash
# 编辑 crontab
crontab -e

# 添加以下内容（将 /path/to/CryptoAnalysis 替换为实际路径）
CRON_TZ=Asia/Shanghai

# 00:03 持仓快照（snapshot_date 自动归为前一天）
3 0 * * * /path/to/CryptoAnalysis/venv/bin/python /path/to/CryptoAnalysis/scripts/fetch_all_position_snapshots.py >> /path/to/CryptoAnalysis/logs/snapshot.log 2>&1

# 00:05 fills 增量更新
5 0 * * * /path/to/CryptoAnalysis/venv/bin/python /path/to/CryptoAnalysis/scripts/fetch_address_fills_incremental.py >> /path/to/CryptoAnalysis/logs/fills.log 2>&1
```

> ⚠️ 注意事项：
> - 使用 venv 的完整路径，**不要用 `source activate`**（cron 没有交互式 shell）
> - `CRON_TZ=Asia/Shanghai` 确保时区正确
> - 日志目录需提前创建：`mkdir -p /path/to/CryptoAnalysis/logs`
> - 服务器时区确认：`timedatectl | grep "Time zone"`

---

## 7. 常见问题排查

### ModuleNotFoundError: No module named 'hyperliquid'
```bash
# 确认使用 venv 的 python，而不是系统 python
/path/to/CryptoAnalysis/venv/bin/python scripts/xxx.py
```

### 数据库连接失败
```bash
# 检查配置文件
cat config/.env

# 测试连接
venv/bin/python -c "from utils.db_utils import get_connection; conn = get_connection(); print('连接成功')"
```

### 时区显示不对
确保使用 `utils.db_utils.get_connection()`，不要直接 `pymysql.connect()`，连接时会自动执行 `SET time_zone = '+08:00'`。

### cron 任务没执行
```bash
# 查看 cron 日志
grep CRON /var/log/syslog | tail -20    # Ubuntu/Debian
grep CRON /var/log/cron | tail -20      # CentOS/RHEL

# 检查 crontab 是否生效
crontab -l
```

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [DATABASE.md](./DATABASE.md) | 数据库表结构设计 |
| [HYPERLIQUID_API.md](./HYPERLIQUID_API.md) | API 接口详解 |
| [TIMEZONE_POLICY.md](./TIMEZONE_POLICY.md) | 时区策略（北京时间） |
| [CRON_JOBS.md](./CRON_JOBS.md) | 定时任务完整配置指南 |

---

**最后更新**: 2026-04-10（新增 import_coinglass_from_json.py；更新 fetch_coinglass_addresses.py 技术方案和过滤规则说明）
