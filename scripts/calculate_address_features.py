"""
计算地址特征并保存到 hl_address_features 表（v2 新评分模型）
基于 hl_fills 和 hl_position_snapshots 计算各项指标

新增特征：
  - liquidation_per_month: 清算次数/月（官方清算 + 近似清算）
  - has_refill_behavior: 是否有后续补仓行为
  - consecutive_loss_add_count: 连续亏损后加仓次数
  - add_position_score: 加仓效果得分（双向±分）
  - scalping_score: 做T行为得分（双向±分）
"""
import sys
import os
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection

# 清算识别阈值
FULL_CLOSE_DIFF_THRESHOLD = 0.02  # sz 与 start_position 差异 < 2%
NEAR_LIQUIDATION_LOSS_PCT = 0.5   # 亏损占名义价值 >= 50%

# 纳入分析的币种白名单（剔除小币种）
TARGET_COINS = ('BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'HYPE', 'BCH', 'BNB')
TARGET_COINS_PLACEHOLDER = ','.join(['%s'] * len(TARGET_COINS))


def purge_address(address: str, reason: str = '无主流币种交易数据') -> None:
    """
    删除指定地址的所有相关数据
    触发条件：该地址在主流币种下无平仓数据
    删除顺序：先删子表，再删主表
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. 找到该地址的所有 snapshot_id
        cursor.execute(
            'SELECT id FROM hl_position_snapshots WHERE address = %s', (address,)
        )
        snapshot_ids = [row[0] for row in cursor.fetchall()]

        # 2. 删除 hl_position_details
        if snapshot_ids:
            placeholders = ','.join(['%s'] * len(snapshot_ids))
            cursor.execute(
                f'DELETE FROM hl_position_details WHERE snapshot_id IN ({placeholders})',
                snapshot_ids
            )
            print(f"   🗑️ 删除 hl_position_details: {cursor.rowcount} 条")

        # 3. 删除其他表（hl_address_features/hl_fragile_scores 保留供分析）
        for table in [
            'hl_position_snapshots',
            'hl_fills',
            'hl_ledger_updates',
        ]:
            cursor.execute(f'DELETE FROM {table} WHERE address = %s', (address,))
            print(f"   🗑️ 删除 {table}: {cursor.rowcount} 条")

        # 4. hl_address_list 不删除，改为 excluded 状态并记录原因
        cursor.execute(
            """UPDATE hl_address_list
               SET status = 'excluded', excluded_reason = %s
               WHERE address = %s""",
            (reason, address)
        )
        print(f"   📝 hl_address_list 状态已改为 excluded")

        conn.commit()
        print(f"   ✅ 地址 {address} 已清除（地址保留，状态=excluded）")

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 清除失败: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def get_active_addresses() -> List[str]:
    """获取所有活跃地址"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT address FROM hl_address_list
            WHERE status = 'active'
            ORDER BY last_updated_at DESC
        ''')
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def calculate_basic_stats(address: str, cursor) -> Optional[Dict]:
    """计算基础统计指标（胜率/盈亏比/交易频率，仅统计主流币种）"""
    print(f"   📊 基础统计...")

    cursor.execute('''
        SELECT
            COUNT(*) as total_close,
            SUM(CASE WHEN closed_pnl > 0 THEN 1 ELSE 0 END) as win_count,
            AVG(CASE WHEN closed_pnl > 0 THEN closed_pnl END) as avg_win_pnl,
            AVG(CASE WHEN closed_pnl < 0 THEN closed_pnl END) as avg_loss_pnl,
            SUM(closed_pnl) as total_realized_pnl,
            SUM(fee) as total_fee,
            MIN(time) as data_start,
            MAX(time) as data_end
        FROM hl_fills
        WHERE address = %s AND dir LIKE 'Close%%'
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))

    row = cursor.fetchone()
    if not row or not row[0]:
        print(f"   ⚠️ 无平仓数据")
        return None

    total_close, win_count, avg_win, avg_loss, total_pnl, total_fee, data_start, data_end = row
    win_rate = float(win_count) / float(total_close) * 100 if total_close else 0
    profit_loss_ratio = abs(float(avg_win or 0)) / abs(float(avg_loss or 1)) if avg_loss and avg_loss < 0 else 0
    days = (data_end - data_start) / 1000 / 86400 if data_end and data_start else 0
    avg_trades_per_day = total_close / days if days >= 1 else 0  # days < 1 时不计算，避免异常值

    return {
        'total_trades': int(total_close),
        'win_rate': Decimal(str(round(win_rate, 2))),
        'avg_win_pnl': Decimal(str(round(float(avg_win or 0), 6))),
        'avg_loss_pnl': Decimal(str(round(float(avg_loss or 0), 6))),
        'profit_loss_ratio': Decimal(str(round(profit_loss_ratio, 2))),
        'total_realized_pnl': Decimal(str(round(float(total_pnl or 0), 6))),
        'total_fee': Decimal(str(round(float(total_fee or 0), 6))),
        'data_period_start': int(data_start) if data_start else 0,
        'data_period_end': int(data_end) if data_end else 0,
        'active_days': int(days),
        'avg_trades_per_day': Decimal(str(round(avg_trades_per_day, 2))),
        'last_trade_time': int(data_end) if data_end else 0,
    }


def calculate_leverage_from_snapshots(address: str, cursor) -> Dict:
    """从快照计算账户整体杠杆（total_ntl_pos / account_value）"""
    print(f"   ⚙️ 账户杠杆（快照）...")

    cursor.execute('''
        SELECT
            AVG(total_ntl_pos / NULLIF(account_value, 0)) as avg_leverage,
            MAX(total_ntl_pos / NULLIF(account_value, 0)) as max_leverage,
            AVG(total_margin_used / NULLIF(account_value, 0) * 100) as avg_margin_util,
            MAX(total_margin_used / NULLIF(account_value, 0) * 100) as max_margin_util
        FROM hl_position_snapshots
        WHERE address = %s AND account_value > 0 AND total_ntl_pos > 0
    ''', (address,))

    row = cursor.fetchone()
    if not row or row[0] is None:
        return {
            'avg_leverage': Decimal('0'),
            'max_leverage': Decimal('0'),
            'avg_margin_utilization': Decimal('0'),
            'max_margin_utilization': Decimal('0'),
        }

    return {
        'avg_leverage': Decimal(str(round(float(row[0] or 0), 2))),
        'max_leverage': Decimal(str(round(float(row[1] or 0), 2))),
        'avg_margin_utilization': Decimal(str(round(float(row[2] or 0), 2))),
        'max_margin_utilization': Decimal(str(round(float(row[3] or 0), 2))),
    }


def calculate_liquidation_stats(address: str, cursor) -> Dict:
    """
    计算清算统计（官方清算 + 近似清算）
    
    近似清算定义：
      - sz ≈ |start_position|（全仓平）
      - closed_pnl < 0
      - |closed_pnl| / (sz × px) >= 50%
    """
    print(f"   🔥 清算统计...")

    # 官方清算
    cursor.execute('''
        SELECT COUNT(*) FROM hl_fills
        WHERE address = %s AND dir LIKE 'Liquidat%%'
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))
    official_liq = cursor.fetchone()[0] or 0

    # 近似清算
    cursor.execute('''
        SELECT COUNT(*) FROM hl_fills
        WHERE address = %s
          AND dir LIKE 'Close%%'
          AND closed_pnl < 0
          AND start_position > 0
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
          AND ABS(sz - ABS(start_position)) / NULLIF(ABS(start_position), 0) < %s
          AND ABS(closed_pnl) / NULLIF(ABS(sz * px), 0) >= %s
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS, FULL_CLOSE_DIFF_THRESHOLD, NEAR_LIQUIDATION_LOSS_PCT))
    near_liq = cursor.fetchone()[0] or 0

    total_liq = official_liq + near_liq

    # 活跃月数
    cursor.execute(
        'SELECT MIN(time), MAX(time) FROM hl_fills WHERE address = %s AND coin IN ({p})'.format(p=TARGET_COINS_PLACEHOLDER),
        (address, *TARGET_COINS)
    )
    row = cursor.fetchone()
    if row and row[0] and row[1]:
        days = (row[1] - row[0]) / 1000 / 86400
        months = days / 30 if days > 0 else 0
        liq_per_month = total_liq / months if months > 0 else 0
    else:
        liq_per_month = 0

    print(f"      官方清算: {official_liq} | 近似清算: {near_liq} | 清算/月: {liq_per_month:.2f}")

    return {
        'liquidation_count': int(total_liq),
        'liquidation_per_month': Decimal(str(round(liq_per_month, 2))),
    }


def calculate_refill_behavior(address: str, cursor) -> Dict:
    """
    是否有后续补仓行为
    
    识别：同 coin + 同方向，持仓未归零前再次 Open
    """
    print(f"   📈 补仓行为...")

    cursor.execute('''
        SELECT coin, dir, time, sz, start_position
        FROM hl_fills
        WHERE address = %s AND (dir LIKE 'Open%%' OR dir LIKE 'Close%%')
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        ORDER BY coin, time
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))

    fills = cursor.fetchall()
    has_refill = False

    # 简化判断：同一 coin，连续两次 Open 且中间没有归零
    by_coin = defaultdict(list)
    for coin, dir, time, sz, start_pos in fills:
        by_coin[coin].append((dir, time, float(sz), float(start_pos or 0)))

    for coin, trades in by_coin.items():
        for i in range(len(trades) - 1):
            curr_dir, curr_time, curr_sz, curr_start = trades[i]
            next_dir, next_time, next_sz, next_start = trades[i + 1]
            
            # 连续两次 Open
            if 'Open' in curr_dir and 'Open' in next_dir:
                has_refill = True
                break
        if has_refill:
            break

    return {'has_refill_behavior': int(has_refill)}


def calculate_consecutive_loss_add(address: str, cursor) -> Dict:
    """
    连续亏损后加仓次数 + 最长连续亏损笔数
    
    改进逻辑（方案D）：
      - 同 coin + 同方向 + 1小时内的连续 Close，算同一次亏损事件
      - 中间有盈利 Close，归零计数
      - 同时统计最长连续亏损笔数
    """
    print(f"   🎲 连续亏损分析...")

    cursor.execute('''
        SELECT dir, coin, closed_pnl, time
        FROM hl_fills
        WHERE address = %s
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        ORDER BY time
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))

    fills = cursor.fetchall()
    
    TIME_WINDOW_MS = 3600000  # 1小时
    consecutive_loss_count = 0
    consecutive_loss_add_count = 0
    max_consecutive_loss = 0
    
    last_close_coin = None
    last_close_dir = None
    last_close_time = 0

    for i, (dir, coin, pnl, time) in enumerate(fills):
        if 'Close' in dir:
            pnl_val = float(pnl or 0)
            
            # 判断是否同一持仓的分批平仓
            is_same_position = (
                coin == last_close_coin and
                ('Long' in dir and 'Long' in last_close_dir or 'Short' in dir and 'Short' in last_close_dir) and
                (time - last_close_time < TIME_WINDOW_MS)
            )
            
            if pnl_val < 0:
                if not is_same_position:
                    consecutive_loss_count += 1  # 新一轮亏损
                    max_consecutive_loss = max(max_consecutive_loss, consecutive_loss_count)
            else:
                consecutive_loss_count = 0  # 盈利归零
            
            last_close_coin = coin
            last_close_dir = dir
            last_close_time = time
            
        elif 'Open' in dir and consecutive_loss_count >= 2:
            consecutive_loss_add_count += 1
            # 注意：加仓后不归零 consecutive_loss_count，继续累计

    return {
        'consecutive_loss_add_count': int(consecutive_loss_add_count),
        'max_consecutive_loss_count': int(max_consecutive_loss),
    }


def calculate_refill_and_scalping(address: str, cursor) -> Dict:
    """
    因子一：补仓模式 + 做T识别

    逻辑：
    - 按 coin + 方向 遍历，找 start_position=0 的 Open 作为周期起点
    - Open 后无 Close → 补仓计数 +1
    - 遇到 Close → 重置补仓计数，检测是否做T
    - 做T：同周期内 Open→Close→Open
    - 等差规律性补仓：连续3次以上加仓价格间距相等
    """
    print(f"   🔄 补仓模式 + 做T...")

    cursor.execute('''
        SELECT coin, dir, time, sz, px, start_position
        FROM hl_fills
        WHERE address = %s AND (dir LIKE 'Open%%' OR dir LIKE 'Close%%')
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        ORDER BY coin, time
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))

    fills = cursor.fetchall()
    if not fills:
        return {'avg_refill_count': Decimal('0'), 'scalping_count': 0, 'is_excluded': 0}

    from collections import defaultdict
    by_coin_dir = defaultdict(list)
    for coin, direction, t, sz, px, start_pos in fills:
        key = (coin, 'Long' if 'Long' in direction else 'Short')
        by_coin_dir[key].append((direction, t, float(sz), float(px), float(start_pos or 0)))

    all_refill_counts = []
    total_scalping = 0

    for key, trades in by_coin_dir.items():
        i = 0
        while i < len(trades):
            direction, t, sz, px, start_pos = trades[i]
            # 找订单周期起点
            if 'Open' not in direction or start_pos != 0:
                i += 1
                continue

            # 周期开始
            open_prices = [px]  # 记录加仓价格（用于等差检测）
            refill_count = 0
            had_close = False
            i += 1

            while i < len(trades):
                d2, t2, sz2, px2, sp2 = trades[i]
                if 'Open' in d2:
                    if not had_close:
                        # 补仓
                        refill_count += 1
                        open_prices.append(px2)
                    else:
                        # Close 后再 Open = 做T
                        total_scalping += 1
                        had_close = False
                        open_prices.append(px2)
                    i += 1
                elif 'Close' in d2:
                    had_close = True
                    # 判断是否归零
                    if abs(sp2) <= sz2 * 1.05:
                        break
                    i += 1
                else:
                    i += 1

            all_refill_counts.append(refill_count)

    # 计算平均补仓次数
    avg_refill = round(sum(all_refill_counts) / len(all_refill_counts)) if all_refill_counts else 0

    # 判断是否剔除
    is_excluded = 0
    if total_scalping > 15:
        is_excluded = 1
    elif avg_refill > 15:
        # 检查等差规律性：取最后一个周期补仓价格列表判断
        # 简化：遍历所有周期，找到任意一个等差补仓周期即标记
        for key, trades in by_coin_dir.items():
            prices = []
            for d, t, sz, px, sp in trades:
                if 'Open' in d and sp > 0:
                    prices.append(px)
            if len(prices) >= 3:
                diffs = [abs(prices[j+1] - prices[j]) for j in range(len(prices)-1)]
                avg_diff = sum(diffs) / len(diffs)
                if avg_diff > 0 and all(abs(d - avg_diff) / avg_diff < 0.05 for d in diffs):
                    is_excluded = 1
                    break

    print(f"      平均补仓: {avg_refill}次 | 做T: {total_scalping}次 | 剔除: {'是' if is_excluded else '否'}")

    return {
        'avg_refill_count': Decimal(str(avg_refill)),
        'scalping_count': int(total_scalping),
        'is_excluded': int(is_excluded),
    }


def calculate_add_position_score(address: str, cursor) -> Dict:
    """
    加仓效果得分（双向±分）
    
    简化版本：按 coin 分组，统计加仓后最终盈亏
      - 加仓后亏损扩大 > 20% → +4分/次（上限+8分）
      - 加仓后成功减亏且最终盈利 → -3分/次（下限-6分）
    """
    print(f"   💰 加仓效果（简化）...")
    # TODO: 完整版需要持仓状态机，此处先返回 0
    return {'add_position_score': Decimal('0')}


def calculate_scalping_score(address: str, cursor) -> Dict:
    """
    做T行为得分（双向±分）
    
    识别：同 coin，持仓周期内 Open/Close 交替 >= 2次
    """
    print(f"   ⚡ 做T行为（简化）...")
    # TODO: 完整版需要精细识别，此处先返回 0
    return {'scalping_score': Decimal('0')}


def calculate_avg_holding_hours(address: str, cursor) -> Dict:
    """
    计算平均持仓时长（小时）

    逻辑：按 coin + 方向 识别订单周期
    - start_position = 0 的 Open 为起点
    - position 归零的 Close 为终点
    - 持仓时长 = 终点时间 - 起点时间
    - 取所有周期的算术平均值
    """
    print(f"   ⏱️ 平均持仓时长...")

    cursor.execute('''
        SELECT coin, dir, time, sz, start_position
        FROM hl_fills
        WHERE address = %s AND (dir LIKE 'Open%%' OR dir LIKE 'Close%%')
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        ORDER BY coin, time
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))

    fills = cursor.fetchall()
    if not fills:
        return {'avg_holding_hours': Decimal('0')}

    from collections import defaultdict
    by_coin_dir = defaultdict(list)
    for coin, direction, t, sz, start_pos in fills:
        key = (coin, 'Long' if 'Long' in direction else 'Short')
        by_coin_dir[key].append((direction, t, float(sz), float(start_pos or 0)))

    holding_durations = []

    for key, trades in by_coin_dir.items():
        i = 0
        while i < len(trades):
            direction, t, sz, start_pos = trades[i]
            # 找到订单周期起点：start_position = 0 的 Open
            if 'Open' in direction and start_pos == 0:
                open_time = t
                current_pos = sz
                i += 1
                # 往后找到 position 归零的 Close
                while i < len(trades):
                    d2, t2, sz2, sp2 = trades[i]
                    if 'Close' in d2:
                        current_pos = sp2 - sz2 if 'Long' in d2 else sp2 + sz2
                        if abs(sp2) <= sz2 * 1.05:  # position 归零
                            duration_ms = t2 - open_time
                            if duration_ms > 0:
                                holding_durations.append(duration_ms / 1000 / 3600)  # 转换为小时
                            break
                    i += 1
            else:
                i += 1

    if not holding_durations:
        return {'avg_holding_hours': Decimal('0')}

    avg_hours = sum(holding_durations) / len(holding_durations)
    print(f"      平均持仓时长: {avg_hours:.2f} 小时（样本数={len(holding_durations)}）")

    return {'avg_holding_hours': Decimal(str(round(avg_hours, 2)))}


def calculate_chase_rate_and_loss_concentration(address: str, cursor) -> Dict:
    """
    因子四特征计算：
    1. 追涨杀跌率：按订单周期，加仓价 > 持仓均价(多) 或 < 持仓均价(空) = 情绪化
    2. 亏损集中度：单一币种亏损占总亏损比例
    """
    print(f"   📊 追涨杀跌率 + 亏损集中度...")

    # --- 追涨杀跌率 ---
    cursor.execute('''
        SELECT coin, dir, time, sz, px, start_position
        FROM hl_fills
        WHERE address = %s AND (dir LIKE 'Open%%' OR dir LIKE 'Close%%')
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        ORDER BY coin, time
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))
    fills = cursor.fetchall()

    from collections import defaultdict
    by_coin_dir = defaultdict(list)
    for coin, direction, t, sz, px, start_pos in fills:
        key = (coin, 'Long' if 'Long' in direction else 'Short')
        by_coin_dir[key].append((direction, t, float(sz), float(px), float(start_pos or 0)))

    total_cycles = 0
    chase_cycles = 0

    for (coin, side), trades in by_coin_dir.items():
        i = 0
        while i < len(trades):
            direction, t, sz, px, start_pos = trades[i]
            if 'Open' not in direction or start_pos != 0:
                i += 1
                continue
            # 周期起点
            total_cycles += 1
            avg_price = px
            position = sz
            has_chase = False
            i += 1
            while i < len(trades):
                d2, t2, sz2, px2, sp2 = trades[i]
                if 'Open' in d2 and sp2 > 0:
                    # 判断追涨杀跌
                    if side == 'Long' and px2 > avg_price:
                        has_chase = True
                    elif side == 'Short' and px2 < avg_price:
                        has_chase = True
                    # 更新均价
                    avg_price = (position * avg_price + sz2 * px2) / (position + sz2)
                    position += sz2
                    i += 1
                elif 'Close' in d2:
                    if abs(sp2) <= sz2 * 1.05:
                        break
                    i += 1
                else:
                    i += 1
            if has_chase:
                chase_cycles += 1

    chase_rate = (chase_cycles / total_cycles * 100) if total_cycles > 0 else 0.0

    # --- 亏损集中度 ---
    cursor.execute(f'''
        SELECT coin, SUM(closed_pnl) as total_loss
        FROM hl_fills
        WHERE address = %s
          AND closed_pnl < 0
          AND dir LIKE 'Close%%'
          AND coin IN ({TARGET_COINS_PLACEHOLDER})
        GROUP BY coin
    '''.format(TARGET_COINS_PLACEHOLDER=TARGET_COINS_PLACEHOLDER), (address, *TARGET_COINS))
    rows = cursor.fetchall()

    loss_concentration = 0.0
    if rows:
        total_loss = sum(abs(float(r[1])) for r in rows)
        if total_loss > 0:
            max_coin_loss = max(abs(float(r[1])) for r in rows)
            loss_concentration = max_coin_loss / total_loss * 100

    print(f"      追涨杀跌率: {chase_rate:.1f}% | 亏损集中度: {loss_concentration:.1f}%")

    return {
        'chase_rate': Decimal(str(round(chase_rate, 2))),
        'loss_concentration': Decimal(str(round(loss_concentration, 2))),
    }


def calculate_margin_call_count(address: str, cursor) -> Dict:
    """
    追加保证金次数

    识别逻辑：
    - accountClassTransfer + to_perp=1（从现货转入合约）
    - 发生在有持仓期间（前一笔 fill 是 Open）
    - 且当时处于亏损状态（最近一笔 Close 的 PnL < 0，或无 Close 记录）
    """
    # 取所有 to_perp=1 的转账
    cursor.execute('''
        SELECT time FROM hl_ledger_updates
        WHERE address = %s AND type = 'accountClassTransfer' AND to_perp = 1
        ORDER BY time
    ''', (address,))
    transfers = [row[0] for row in cursor.fetchall()]

    if not transfers:
        return {'margin_call_count': 0}

    # 取全部 fills（不限币种，用于判断持仓状态）
    cursor.execute('''
        SELECT time, dir, closed_pnl
        FROM hl_fills
        WHERE address = %s
        ORDER BY time
    ''', (address,))
    fills = cursor.fetchall()

    margin_call_count = 0
    for t_time in transfers:
        before = [(f[0], f[1], f[2]) for f in fills if f[0] <= t_time][-10:]
        if not before:
            continue

        # 有未平仓的 Open
        has_open = any('Open' in f[1] for f in before)
        # 最近一笔 Close 是亏损（或没有 Close = 一直没平过）
        last_close_pnl = next(
            (float(f[2]) for f in reversed(before) if 'Close' in f[1] and f[2] is not None),
            None
        )
        losing = last_close_pnl is None or last_close_pnl < 0

        if has_open and losing:
            margin_call_count += 1

    print(f"      追加保证金: {margin_call_count}次 / 转入合约{len(transfers)}次")
    return {'margin_call_count': margin_call_count}


def calculate_other_features(address: str, cursor) -> Dict:
    """其他特征：币种集中度"""
    cursor.execute('''
        SELECT coin, COUNT(*) as cnt
        FROM hl_fills
        WHERE address = %s
        GROUP BY coin
        ORDER BY cnt DESC
        LIMIT 1
    ''', (address,))
    top_coin_row = cursor.fetchone()

    cursor.execute('SELECT COUNT(*) FROM hl_fills WHERE address = %s', (address,))
    total_count = cursor.fetchone()[0] or 1

    coin_concentration = 0.0
    if top_coin_row:
        coin_concentration = float(top_coin_row[1]) / float(total_count) * 100

    return {'coin_concentration': Decimal(str(round(coin_concentration, 2)))}


def calculate_features(address: str) -> Optional[Dict]:
    """计算单个地址的所有特征"""
    print(f"\n[计算特征] {address}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        basic = calculate_basic_stats(address, cursor)
        if not basic:
            return None

        leverage = calculate_leverage_from_snapshots(address, cursor)
        liquidation = calculate_liquidation_stats(address, cursor)
        refill = calculate_refill_behavior(address, cursor)
        consecutive_loss = calculate_consecutive_loss_add(address, cursor)
        add_score = calculate_add_position_score(address, cursor)
        scalping = calculate_scalping_score(address, cursor)
        other = calculate_other_features(address, cursor)
        holding = calculate_avg_holding_hours(address, cursor)
        refill_v3 = calculate_refill_and_scalping(address, cursor)
        chase_v3 = calculate_chase_rate_and_loss_concentration(address, cursor)
        margin_call = calculate_margin_call_count(address, cursor)

        features = {**basic, **leverage, **liquidation, **refill, **consecutive_loss, **add_score, **scalping, **other, **holding, **refill_v3, **chase_v3, **margin_call}

        print(f"   ✅ 完成")
        print(f"      胜率: {features['win_rate']}% | 杠杆: {features['avg_leverage']}x | 清算/月: {features['liquidation_per_month']}")
        print(f"      补仓: {'有' if features['has_refill_behavior'] else '无'} | 连亏后加仓: {features['consecutive_loss_add_count']}次")

        return features

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()


def save_features(address: str, features: Dict) -> int:
    """保存特征到 hl_address_features 表"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO hl_address_features (
                address, calculated_at,
                data_period_start, data_period_end,
                total_trades, win_rate, avg_win_pnl, avg_loss_pnl,
                profit_loss_ratio, total_realized_pnl, total_fee,
                avg_leverage, max_leverage,
                avg_margin_utilization, max_margin_utilization,
                coin_concentration, liquidation_count, liquidation_per_month,
                has_refill_behavior, consecutive_loss_add_count, max_consecutive_loss_count,
                add_position_score, scalping_score,
                active_days, avg_trades_per_day, last_trade_time,
                avg_holding_hours, avg_refill_count, scalping_count, is_excluded,
                chase_rate, loss_concentration, margin_call_count
            ) VALUES (
                %s, NOW(),
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        ''', (
            address,
            features['data_period_start'], features['data_period_end'],
            features['total_trades'], features['win_rate'], features['avg_win_pnl'], features['avg_loss_pnl'],
            features['profit_loss_ratio'], features['total_realized_pnl'], features['total_fee'],
            features['avg_leverage'], features['max_leverage'],
            features['avg_margin_utilization'], features['max_margin_utilization'],
            features['coin_concentration'], features['liquidation_count'], features['liquidation_per_month'],
            features['has_refill_behavior'], features['consecutive_loss_add_count'], features['max_consecutive_loss_count'],
            features['add_position_score'], features['scalping_score'],
            features['active_days'], features['avg_trades_per_day'], features['last_trade_time'],
            features.get('avg_holding_hours', Decimal('0')),
            features.get('avg_refill_count', Decimal('0')),
            features.get('scalping_count', 0),
            features.get('is_excluded', 0),
            features.get('chase_rate', Decimal('0')),
            features.get('loss_concentration', Decimal('0')),
            features.get('margin_call_count', 0),
        ))

        conn.commit()
        feature_id = cursor.lastrowid
        print(f"   💾 已保存（ID: {feature_id}）")
        return feature_id

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    print("=" * 70)
    print("地址特征计算 v2（新评分模型）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if len(sys.argv) > 1:
        addresses = [sys.argv[1]]
    else:
        print("\n📋 获取地址列表...")
        addresses = get_active_addresses()
        if not addresses:
            print("❌ 无活跃地址")
            return
        print(f"✅ {len(addresses)} 个地址")

    success_count = skip_count = fail_count = 0

    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}]")
        try:
            features = calculate_features(address)
            if not features:
                print(f"   ⚠️ 无主流币种数据，清除该地址...")
                purge_address(address, '无主流币种交易数据（仅交易非 BTC/ETH/SOL/DOGE/XRP/ADA/HYPE/BCH/BNB 币种）')
                skip_count += 1
                continue

            # 日均交易超过30笔判定为高频交易机器人，剔除
            avg_trades = float(features.get('avg_trades_per_day', 0))
            if avg_trades > 30:
                print(f"   ⚠️ 日均交易{avg_trades:.1f}笔 > 30，判定为高频机器人，剔除...")
                purge_address(address, f'高频交易（日均{avg_trades:.1f}笔 > 30）')
                skip_count += 1
                continue

            save_features(address, features)
            success_count += 1
        except Exception as e:
            print(f"   ❌ {e}")
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"完成! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ {success_count} | ⚠️ {skip_count} | ❌ {fail_count} | 总计: {len(addresses)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
