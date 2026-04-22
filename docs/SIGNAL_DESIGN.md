# 交易信号生成设计文档

> 状态：草稿（待 Aylwin 确认后开始编码）  
> 更新：2026-04-22

---

## 一、整体逻辑

```
监控地址表（hl_monitor_addresses）
        ↓  每分钟轮询
  ① 拉取挂单（openOrders）
  ② 拉取最新 fills（userFillsByTime，增量）
        ↓
  判断信号类型：开仓 / 平仓
        ↓
  写入信号表（hl_trade_signals）
        ↓
  推送通知（Telegram / 飞书）
```

---

## 二、新建表：hl_monitor_addresses（监控地址表）

```sql
CREATE TABLE `hl_monitor_addresses` (
  `id`              bigint       NOT NULL AUTO_INCREMENT,
  `address`         varchar(66)  NOT NULL COMMENT '监控的钱包地址',
  `coin`            varchar(20)  NOT NULL COMMENT '监控的币种（如 BTC、ETH）',
  `label`           varchar(100) DEFAULT NULL COMMENT '备注标签',
  `status`          enum('active','paused') NOT NULL DEFAULT 'active' COMMENT '监控状态',
  `last_fill_time`  bigint       DEFAULT NULL COMMENT '上次已处理的最新 fill 时间戳(ms)，用于增量拉取',
  `created_at`      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_address_coin` (`address`, `coin`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='跟单监控地址表';
```

**说明：**
- 同一个地址可以监控多个币种，每行一个 address + coin 组合
- `last_fill_time` 记录上次已处理的最新 fill 时间戳，每次轮询后更新，用于增量拉取避免重复
- `status = paused` 时跳过该地址的轮询

---

## 三、新建表：hl_trade_signals（信号表）

```sql
CREATE TABLE `hl_trade_signals` (
  `id`              bigint       NOT NULL AUTO_INCREMENT,
  `signal_id`       varchar(100) NOT NULL COMMENT '信号唯一ID（防重复）',
  `address`         varchar(66)  NOT NULL COMMENT '来源地址',
  `coin`            varchar(20)  NOT NULL COMMENT '币种',
  `signal_source`   enum('fill','order') NOT NULL COMMENT '信号来源：fill成交 / order挂单',
  `action`          enum('open_long','open_short','close_long','close_short') NOT NULL COMMENT '动作',
  `price`           decimal(20,6) NOT NULL COMMENT '触发价格',
  `size`            decimal(20,8) NOT NULL COMMENT '原始数量',
  `fill_hash`       varchar(100) DEFAULT NULL COMMENT '来源 fill 的 hash（fill信号用）',
  `fill_time`       bigint       DEFAULT NULL COMMENT '来源 fill 时间戳(ms)',
  `order_id`        varchar(100) DEFAULT NULL COMMENT '来源挂单 ID（order信号用）',
  `raw_direction`   varchar(10)  DEFAULT NULL COMMENT '原始方向：A=Buy/B=Sell',
  `status`          enum('pending','notified','executed','cancelled') NOT NULL DEFAULT 'pending',
  `created_at`      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_signal_id` (`signal_id`),
  KEY `idx_address_coin` (`address`, `coin`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='跟单信号表';
```

---

## 四、信号判断逻辑

### 4.1 Fill 信号（已成交）

每次轮询对每个 `address + coin`：

```
userFillsByTime(address, startTime=last_fill_time)
        ↓
过滤出当前 coin 的 fills
        ↓
遍历每条 fill：
  dir 包含 "Open"  →  开仓信号
  dir 包含 "Close" →  平仓信号
        ↓
判断方向（通过 startPosition / side 字段）：
  side = "B"(Buy)  + Open  → open_long
  side = "A"(Ask/Sell) + Open  → open_short
  side = "B" + Close → close_short（平空）
  side = "A" + Close → close_long（平多）
        ↓
生成 signal_id = hash(address + fill_hash)，防重复
写入 hl_trade_signals
更新 last_fill_time
```

### 4.2 Order 信号（挂单）

```
openOrders(address)
        ↓
过滤出当前 coin 的挂单
        ↓
对每个挂单：
  生成 signal_id = hash(address + coin + order_id)，防重复
  已存在 → 跳过（挂单未变化）
  不存在 → 写入信号（signal_source = 'order'）
```

> ⚠️ 挂单信号仅代表"有意图"，可能不会成交。优先级低于 fill 信号。

### 4.3 信号优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 高 | fill | 已实际成交，确定性强 |
| 低 | order | 仅挂单，存在撤单风险 |

---

## 五、轮询流程

```
每 60 秒执行一次：

FOR EACH active address+coin IN hl_monitor_addresses:
  1. 拉取挂单 openOrders(address) → 过滤 coin → 生成 order 信号
  2. 拉取新 fills userFillsByTime(address, last_fill_time) → 过滤 coin → 生成 fill 信号
  3. 更新 last_fill_time = MAX(fill.time) + 1
  4. 地址间间隔 0.5 秒（避免限流）
```

---

## 六、通知格式（Telegram / 飞书）

### Fill 信号通知

```
🚨 跟单信号 [BTC]

来源地址：0xabc...def（割肉侠）
动作：开多（Open Long）
价格：$93,500
数量：0.05 BTC
时间：2026-04-22 15:30:00

来源：成交记录（fill）
```

### Order 信号通知

```
📋 挂单信号 [ETH]

来源地址：0xabc...def
动作：开空（Open Short）
挂单价：$3,200
数量：1.0 ETH
时间：2026-04-22 15:30:00

来源：挂单（order）⚠️ 可能撤单
```

---

## 七、脚本规划

| 脚本 | 说明 |
|------|------|
| `scripts/monitor_signals.py` | 主监控脚本，轮询生成信号 + 推送通知 |
| `scripts/manage_monitor_addresses.py` | 管理监控地址（增删改查） |

---

## 八、已确认配置

| 项目 | 确认值 |
|------|--------|
| 挂单信号 | ✅ 需要，提前跟单减少滑点 |
| 通知方式 | 飞书 Webhook：`https://open.larksuite.com/open-apis/bot/v2/hook/b820bda8-4d32-4f11-8530-2dc37bcdcaad` |
| 轮询频率 | 60 秒 |
| 数量分配 | 按初始投资金额比例分配（与回测一致），需配置 `total_capital` 总资金 |
| 地址来源 | 从 `hl_address_list` 筛选后手动加入 `hl_monitor_addresses` |
| 新地址初始化 | `last_fill_time = 当前时间戳`，不追历史记录 |

---

## 九、后续扩展（暂不实现）

- 自动下单执行（Phase 5）
- 信号胜率统计
- 止损/止盈规则
