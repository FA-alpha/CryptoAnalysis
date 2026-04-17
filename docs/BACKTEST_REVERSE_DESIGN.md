# 反向跟单回测脚本设计文档

> 目标：基于 `hl_fills` 中脆弱地址的真实交易记录，模拟反向开单，接入 fourieralpha_strategy 现有回测平台展示结果。

---

## 一、核心逻辑

### 反向规则

| 脆弱地址操作 | 我们的操作 |
|---|---|
| Open Long | Open Short |
| Open Short | Open Long |
| Close Long | Close Short（平我们的空单） |
| Close Short | Close Long（平我们的多单） |
| Liquidation | 强制全平 |

- **跟单价格**：直接用脆弱地址的成交价 `px`
- **跟单数量**：固定每次开仓金额（`order_size`），不跟仓位大小
- **平仓比例**：按对方平仓比例等比平（`sz / abs(start_position)`）

---

## 二、与现有框架的集成方式

现有框架是**K 线时间步驱动**的，我们的回测是**fills 事件驱动**的，两者驱动方式不同，**不能复用 BacktestEngine**。

但输出格式必须与现有框架完全一致，这样可以直接复用平台的展示逻辑。

### 集成方案

在 `fourieralpha_strategy` 项目下新增：

```
fourieralpha_strategy/
├── strategy/
│   └── hl_reverse_strategy.py      # 新增：反向跟单策略类（实现 trades/daily_trades 输出）
├── backtest/
│   └── hl_reverse_backtest_engine.py  # 新增：反向跟单回测引擎（不依赖 K 线）
└── backtrack.py                     # 新增一个路由 /hl_reverse_backtest
```

数据库连接新增一个指向 `fourieralpha_hl` 的配置，与现有 `DB_CONFIG` 并列：

```python
# config/settings.py 新增
HL_DB_CONFIG = {
    'host': 'fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com',
    'port': 3306,
    'user': 'admin',
    'password': 'XFGAd9wJYMJqSD7C',
    'database': 'fourieralpha_hl',
    'charset': 'utf8mb4',
}
```

---

## 三、API 接口

在 `backtrack.py` 新增一个路由：

### POST `/hl_reverse_backtest`

**请求体：**

```json
{
  "targets": [
    {"address": "0xaa08...", "coin": "BTC"},
    {"address": "0xbb09...", "coin": "ETH"},
    {"address": "0xaa08...", "coin": "SOL"}
  ],
  "start_date": "2025-01-01",
  "end_date":   "2025-12-31",
  "initial_capital": 10000,
  "order_size": 1000,
  "leverage": 1.0,
  "fee_rate": 0.0005,
  "backtest_token": "xxx"
}
```

**返回体**（与现有 `/backtest` 完全一致）：

```json
{
  "status": 1,
  "statement_url": "xxx.xlsx",
  "trade_detail_url": "xxx.csv",
  "metrics": { ... }
}
```

---

## 四、`hl_reverse_backtest_engine.py` 设计

### 核心流程

```
1. 批量加载所有目标地址+币种的 fills（一次查库）
2. 将所有 fills 合并，按 time 升序排列
3. 遍历每一条 fill，维护每个 (address, coin) 的持仓状态
4. 每日结束时汇总当日盈亏，生成 daily_trades
5. 全部完成后计算 metrics
6. 输出 trades / daily_trades / metrics（格式与现有框架一致）
```

### 数据加载（SQL）

```sql
SELECT address, coin, dir, sz, px, closed_pnl, fee, time, start_position
FROM hl_fills
WHERE (address, coin) IN (
    ('0xaa08...', 'BTC'),
    ('0xbb09...', 'ETH')
)
AND dir IN ('Open Long','Open Short','Close Long','Close Short','Liquidation Long','Liquidation Short')
AND time BETWEEN {start_ms} AND {end_ms}
ORDER BY time ASC
```

### 持仓状态机（每个 target 独立维护）

```python
# key = (address, coin)
positions = {
    ('0xaa08...', 'BTC'): {
        'side': 'short',   # 我们持仓方向（与对方相反）
        'size': 0.0,       # 持仓数量
        'avg_price': 0.0,  # 持仓均价
        'margin': 0.0,     # 占用保证金
    }
}
```

### 开仓逻辑

```python
if 'Open Long' in fill['dir']:
    our_side = 'short'
elif 'Open Short' in fill['dir']:
    our_side = 'long'

size = order_size * leverage / fill['px']
margin = order_size
fee = order_size * fee_rate

# 若已有同向持仓 → 加仓（更新均价）
# 若已有反向持仓 → 先平再开（不允许双向持仓）
```

### 平仓逻辑

```python
# 按对方平仓比例等比平
close_ratio = fill['sz'] / abs(fill['start_position'])  # 0~1，取 min(1.0)
close_size = position['size'] * close_ratio

if our_side == 'short':
    pnl = (position['avg_price'] - fill['px']) * close_size  # 空单盈利=价格下跌
else:
    pnl = (fill['px'] - position['avg_price']) * close_size  # 多单盈利=价格上涨

net_pnl = pnl - close_size * fill['px'] * fee_rate
capital += net_pnl
```

### Liquidation 处理

```python
# 强制全平，close_ratio = 1.0
```

---

## 五、trades 格式（与现有框架一致）

```python
{
    'date':        '2025-01-01',
    'time':        '2025-01-01_10:30:00',
    'symbol':      'BTC',
    'action':      'BUY' / 'SELL',        # 开仓=BUY，平仓=SELL
    'price':       106000.0,
    'quantity':    0.01,
    'revenue':     1060.0,
    'amount':      9800.0,                 # 当前剩余资金
    'amount_change': -200.0,
    'position':    1060.0,                 # 当前持仓价值
    'avg_price':   106000.0,
    'grids':       0,
    'profit':      50.0,                   # 本笔盈亏（开仓为0）
    'reason':      'HL反向跟单 0xaa08.../BTC',
    'grid_level':  0,
    'is_stop_loss': '否',
    'fee_amt':     0.5,
    # 扩展字段（不影响现有展示）
    'source_address': '0xaa08...',
    'source_dir':     'Open Long',
}
```

## 六、daily_trades 格式（与现有框架一致）

```python
{
    '日期':       '2025-01-01',
    '当日净资产':  10050.0,
    '单位净值':    1.005,
    # 各 target 的当日净资产（前缀区分）
    '0_BTC_当日净资产':  5025.0,
    '1_ETH_当日净资产':  5025.0,
}
```

## 七、metrics 格式（与现有框架一致）

```python
{
    'total': {
        'last_amt':         11500.0,   # 最终净值
        'profit':           1500.0,    # 总盈亏
        'profit_rate':      15.0,      # 收益率(%)
        'win_rate':         0.62,      # 胜率
        'profit_loss_ratio': 1.8,      # 盈亏比
        'max_drawdown':     0.12,      # 最大回撤
        'sharpe_ratio':     1.3,       # 夏普比率
        'trade_count':      45,        # 总交易次数
        'total_fee':        22.5,      # 总手续费
    }
}
```

---

## 八、开发步骤（给 Agent 的实现顺序）

1. **`config/settings.py`**：新增 `HL_DB_CONFIG`

2. **`hl_reverse_backtest_engine.py`**：
   - `load_fills(targets, start_date, end_date) -> List[dict]`：查库
   - `run_backtest(config) -> (trades, daily_trades, metrics)`：主循环
   - `_open_position(fill, target, config)`
   - `_close_position(fill, target, config, ratio)`
   - `_calculate_metrics(trades, daily_trades, initial_capital) -> dict`

3. **`backtrack.py`**：
   - 新增 `HLReverseBacktestRequest` Pydantic 模型
   - 新增路由 `POST /hl_reverse_backtest`
   - 调用 engine，保存 Excel/CSV，返回结果（复用现有保存逻辑）

4. **注意事项**：
   - `start_position` 为 0 或 NULL 时，按全仓平仓处理（ratio=1.0）
   - 回测结束时有未平仓位，按最后一条 fill 的 `px` 强制平仓，`reason='强制平仓（回测结束）'`
   - 多个 target 的资金共享同一个 `capital` 池，任意一个亏完则停止回测
   - `daily_trades` 每日结算时间以北京时间 00:00 为界

---

## 九、不需要实现的部分（现有框架已有）

- Excel / CSV 保存逻辑 → 复用 `backtrack.py` 现有代码
- 结果保存到数据库 → 复用 `db_four_service.save_backtest_result()`
- 前端展示 → 不需要改，格式对齐即可
