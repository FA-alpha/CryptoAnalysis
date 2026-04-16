# 脚本使用说明

## 📂 脚本目录

```
scripts/
├── fetch_coinglass_addresses.py         # 从 CoinGlass 抓取 Hyperliquid 地址写入 DB（Playwright）⭐ 地址来源
├── import_coinglass_from_json.py        # 从本地 JSON 批量导入 CoinGlass 地址（离线导入）
├── fetch_hyperbot_fragile_addresses.py  # 从 HyperBot discover 发现脆弱地址并入库（分片抓取，支持几千条）
├── fetch_address_fills_incremental.py   # 统一版 fills 采集（全量/增量自动判断）⭐ 日常使用
├── fetch_address_fills_backfill.py      # 历史 fills 补采（仅在需要补超过2000条历史时手动执行一次）
├── fetch_ledger_updates.py              # 充提记录采集（全量/增量自动判断）⭐ 日常使用
├── fetch_all_position_snapshots.py      # 批量获取持仓快照（含 PnL）⭐
├── fetch_position_snapshots.py          # 单地址持仓快照
├── calculate_address_features_v2.py     # 地址特征计算 v2（当前使用）⭐
├── calculate_fragile_scores_v2.py       # 脆弱地址评分 v2（当前使用）⭐
├── calculate_address_features.py        # 地址特征计算 v1（已废弃）
└── calculate_fragile_scores.py          # 脆弱地址评分 v1（已废弃）
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

## 2.5 fetch_hyperbot_fragile_addresses.py（HyperBot 脆弱地址发现）

### 功能说明

通过 `POST /api/upgrade/v2/hl/traders/discover` 自动筛选“低胜率 + 高杠杆 + 大亏损 + 足够样本”的地址，并写入 `hl_address_list`。

为突破 discover 单次分页上限，脚本采用 **方案1：按 totalPnl 分片 + 每片分页**：

- 先把 `totalPnl` 按亏损区间切成多个分片（如：`(-1e12,-1000000)`、`(-1000000,-500000)` ... `(-20000,-10000)`）
- 每个分片最多抓 `--pages` 页（默认 20 页，每页 25 条）
- 合并后按地址去重，再批量入库

### 环境变量（config/.env）

```ini
HYPERBOT_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
HYPERBOT_ACCESS_KEY_SECRET=YOUR_ACCESS_KEY_SECRET
HYPERBOT_BASE_URL=https://openapi.hyperbot.network
```

### 使用方式

```bash
# 默认抓取（30天周期，分片抓取，每片最多20页）
python scripts/fetch_hyperbot_fragile_addresses.py

# 先预览，不写入数据库
python scripts/fetch_hyperbot_fragile_addresses.py --dry-run

# 鉴权自检（先测 tickers，再测 discover）
python scripts/fetch_hyperbot_fragile_addresses.py --auth-check

# 提高抓取量（每片20页，每页25条；总量可到几千，取决于筛选结果）
python scripts/fetch_hyperbot_fragile_addresses.py --pages 20 --page-size 25

# 调整筛选阈值
python scripts/fetch_hyperbot_fragile_addresses.py \
  --period 30 \
  --win-rate-lt 40 \
  --avg-leverage-gt 10 \
  --total-pnl-lt -10000 \
  --position-count-gt 20 \
  --avg-duration-min-lt 60 \
  --margin-used-gt 0.8
```

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--period` | 30 | 统计周期（天） |
| `--pages` | 20 | 每个 PnL 分片最大页数 |
| `--page-size` | 25 | 每页条数（接口上限25） |
| `--win-rate-lt` | 40 | 胜率阈值：小于该值 |
| `--avg-leverage-gt` | 10 | 平均杠杆阈值：大于该值 |
| `--total-pnl-lt` | -10000 | 总盈亏阈值：小于该值（亏损） |
| `--position-count-gt` | 20 | 开仓次数阈值：大于该值 |
| `--avg-duration-min-lt` | 无 | 可选：平均持仓分钟数上限 |
| `--margin-used-gt` | 无 | 可选：保证金占用率下限 |
| `--source` | hyperbot | 入库来源字段 |
| `--dry-run` | false | 仅打印，不写库 |
| `--auth-check` | false | 鉴权诊断：检查全局鉴权与 discover 接口权限 |

### 入库规则

- 表：`hl_address_list`
- 写入字段：
  - `address`：小写地址
  - `source`：默认 `hyperbot`
  - `label`：自动生成中文条件串（如 `脆弱候选(period=30, winRate<40.0, lev>10.0, pnl<-10000.0, pos>20.0)`）
  - `status`：`active`
  - `first_seen_at` / `last_updated_at`：当前北京时间
- 去重策略：按 `address` 查重，`INSERT IGNORE`

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

---

## 8. fetch_ledger_updates.py（充提记录采集）⭐

### 功能说明

采集地址的充提记录（`userNonFundingLedgerUpdates`），用于识别**追加保证金行为**（`accountClassTransfer + to_perp=1`）。

- **无历史数据**（新地址）→ 不传任何时间参数，拉取全量历史
- **有历史数据** → 从 `MAX(time)` 往后增量拉取

### 使用方式

```bash
# 批量模式：处理所有 active 地址
python scripts/fetch_ledger_updates.py

# 单地址模式
python scripts/fetch_ledger_updates.py 0xdeeacd0aaffb70edd79f410a37c8b20e0a7fcd65
```

### 关键字段

| type | to_perp | 含义 |
|------|---------|------|
| `accountClassTransfer` | 1 | 从现货转入合约 → **追加保证金** |
| `accountClassTransfer` | 0 | 从合约转出到现货 |
| `deposit` | - | 外部充值 |
| `withdraw` | - | 提现 |

---

## 9. calculate_address_features_v2.py（特征计算 v2）⭐

### 功能说明

基于 `hl_fills`、`hl_position_snapshots`、`hl_ledger_updates` 计算地址特征，保存到 `hl_address_features`。

**仅统计主流币种**：BTC/ETH/SOL/DOGE/XRP/ADA/HYPE/BCH/BNB（剔除小币种）

### 计算的特征

| 特征 | 说明 |
|------|------|
| `win_rate` | 胜率 |
| `profit_loss_ratio` | 盈亏比 |
| `avg_leverage` | 平均杠杆（快照） |
| `liquidation_per_month` | 清算次数/月 |
| `consecutive_loss_add_count` | 连续亏损后加仓次数 |
| `max_consecutive_loss_count` | 最长连续亏损笔数 |
| `avg_refill_count` | 平均补仓次数 |
| `chase_rate` | 追涨杀跌率 |
| `loss_concentration` | 亏损集中度 |
| `avg_holding_hours` | 平均持仓时长 |
| `margin_call_count` | 追加保证金次数 |

### 使用方式

```bash
# 批量模式
python scripts/calculate_address_features_v2.py

# 单地址模式
python scripts/calculate_address_features_v2.py 0xdeeacd0aaffb70edd79f410a37c8b20e0a7fcd65
```

---

## 10. calculate_fragile_scores_v2.py（评分 v2）⭐

### 功能说明

基于 `hl_address_features` 计算脆弱评分，保存到 `hl_fragile_scores`。

### 评分体系（总分 105 分）

| 因子 | 满分 | 说明 |
|------|------|------|
| 因子一：补仓模式 | 15 | 平均补仓次数 |
| 因子二：综合盈亏 | 20 | 胜率 + 盈亏比 |
| 因子三：清算 | 25 | 清算次数/月 + 历史清算总次数 |
| 因子四：追涨+集中度 | 20 | 追涨杀跌率 + 亏损集中度 |
| 因子五：追加保证金 | 20 | margin_call_count |
| 因子六：持仓时长 | 5 | avg_holding_hours |

### 等级划分

| 等级 | 分数 | 说明 |
|------|------|------|
| L1 | ≥85 | 极度脆弱，重点监控 |
| L2 | ≥70 | 高度脆弱 |
| L3 | ≥50 | 中度脆弱 |
| L4 | <50 | 低风险 |

### 使用方式

```bash
# 批量模式
python scripts/calculate_fragile_scores_v2.py

# 单地址模式
python scripts/calculate_fragile_scores_v2.py 0xdeeacd0aaffb70edd79f410a37c8b20e0a7fcd65
```

---

**最后更新**: 2026-04-16（新增 fetch_ledger_updates.py；更新特征计算和评分为 v2；主流币种过滤；追加保证金因子五实现）
