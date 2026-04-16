"""
计算脆弱地址评分并保存到 hl_fragile_scores 表（v2 新评分模型）

评分体系（总分动态，理论120分）：
  风险行为（35分）：账户整体杠杆(15) + 仓位利用率(10)
  亏损特征（30分）：胜率(15) + 清算次数/月(10) + 总PnL%(5)
  心态特征（20分）：连续亏损后加仓(10) + 追涨杀跌(5) + 死扛指数(5)
  加仓/做T（±15分）：加仓效果(-6~+8) + 做T频率+盈亏修正(-3~+7)

等级划分：≥80=L1 / ≥60=L2 / ≥40=L3 / <40=L4 / 负分=策略型
"""
import sys
import os
from typing import Dict, Optional, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection


def get_latest_features(address: str = None) -> List[tuple]:
    """获取最新特征数据"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        sql = '''
                SELECT id, address,
                       win_rate, avg_leverage, liquidation_per_month,
                       avg_margin_utilization, has_refill_behavior,
                       consecutive_loss_add_count, max_consecutive_loss_count,
                       add_position_score, scalping_score,
                       total_realized_pnl, coin_concentration,
                       profit_loss_ratio, liquidation_count,
                       avg_refill_count, scalping_count, is_excluded,
                       chase_rate, loss_concentration, avg_holding_hours, margin_call_count
                FROM hl_address_features
            '''
        if address:
            cursor.execute(sql + ' WHERE address = %s ORDER BY calculated_at DESC LIMIT 1', (address,))
        else:
            cursor.execute('''
                SELECT f.id, f.address,
                       f.win_rate, f.avg_leverage, f.liquidation_per_month,
                       f.avg_margin_utilization, f.has_refill_behavior,
                       f.consecutive_loss_add_count, f.max_consecutive_loss_count,
                       f.add_position_score, f.scalping_score,
                       f.total_realized_pnl, f.coin_concentration,
                       f.profit_loss_ratio, f.liquidation_count,
                       f.avg_refill_count, f.scalping_count, f.is_excluded,
                       f.chase_rate, f.loss_concentration, f.avg_holding_hours, f.margin_call_count
                FROM hl_address_features f
                INNER JOIN (
                    SELECT address, MAX(calculated_at) as max_time
                    FROM hl_address_features GROUP BY address
                ) latest ON f.address = latest.address
                         AND f.calculated_at = latest.max_time
            ''')

        rows = cursor.fetchall()
        result = []
        for row in rows:
            feature_id, addr, *vals = row
            features = {
                'win_rate':                     float(vals[0] or 0),
                'avg_leverage':                 float(vals[1] or 0),
                'liquidation_per_month':        float(vals[2] or 0),
                'avg_margin_utilization':       float(vals[3] or 0),
                'has_refill_behavior':          bool(vals[4]),
                'consecutive_loss_add_count':   int(vals[5] or 0),
                'max_consecutive_loss_count':   int(vals[6] or 0),
                'add_position_score':           float(vals[7] or 0),
                'scalping_score':               float(vals[8] or 0),
                'total_realized_pnl':           float(vals[9] or 0),
                'coin_concentration':           float(vals[10] or 0),
                'profit_loss_ratio':            float(vals[11] or 0),
                'liquidation_count':            int(vals[12] or 0),
                'avg_refill_count':             float(vals[13] or 0),
                'scalping_count':               int(vals[14] or 0),
                'is_excluded':                  int(vals[15] or 0),
                'chase_rate':                   float(vals[16] or 0),
                'loss_concentration':           float(vals[17] or 0),
                'avg_holding_hours':            float(vals[18] or 0),
                'margin_call_count':            int(vals[19] or 0),
            }
            result.append((feature_id, addr, features))

        return result

    finally:
        cursor.close()
        conn.close()


# ============================================================
# 评分函数：风险行为（35分）
# ============================================================

def score_leverage(avg_leverage: float) -> tuple:
    """账户整体杠杆评分（15分）"""
    if avg_leverage >= 10:
        return 15, f"杠杆{avg_leverage:.1f}x（极高）"
    elif avg_leverage >= 5:
        return 10, f"杠杆{avg_leverage:.1f}x（高）"
    elif avg_leverage >= 3:
        return 6, f"杠杆{avg_leverage:.1f}x（中）"
    elif avg_leverage >= 2:
        return 3, f"杠杆{avg_leverage:.1f}x（低）"
    else:
        return 0, f"杠杆{avg_leverage:.1f}x（很低）"


def score_margin_utilization(avg_margin: float, has_refill: bool) -> tuple:
    """
    仓位利用率评分（10分，含补仓修正）
    
    有补仓空间且实际补过仓 → 得分降低
    """
    base_score = 0
    if avg_margin >= 90:
        base_score = 10
    elif avg_margin >= 80:
        base_score = 7
    elif avg_margin >= 60:
        base_score = 4
    elif avg_margin >= 40:
        base_score = 2

    # 补仓修正
    if has_refill and avg_margin >= 80:
        base_score = max(0, base_score - 3)
    elif has_refill and avg_margin >= 60:
        base_score = max(0, base_score - 2)

    detail = f"仓位{avg_margin:.1f}%{'(有补仓)' if has_refill else ''}"
    return base_score, detail


# ============================================================
# 评分函数：亏损特征（30分）
# ============================================================

def score_win_rate(win_rate: float) -> tuple:
    """胜率评分（15分）- 保留旧版，兼容v2"""
    if win_rate < 30:
        return 15, f"胜率{win_rate:.1f}%（极低）"
    elif win_rate < 35:
        return 12, f"胜率{win_rate:.1f}%（很低）"
    elif win_rate < 40:
        return 8, f"胜率{win_rate:.1f}%（低）"
    elif win_rate < 45:
        return 4, f"胜率{win_rate:.1f}%（中）"
    else:
        return 0, f"胜率{win_rate:.1f}%"


def score_综合盈亏_v3(win_rate: float, profit_loss_ratio: float) -> tuple:
    """
    因子二：综合盈亏特征（V3，满分20分，联合查表）

    盈亏比 = 平均盈利 / 平均亏损绝对值
    - 盈亏比 > 1.0 → 亏得少（得分低）
    - 盈亏比 ≤ 1.0 → 亏得多（得分高）
    """
    is_lose_more = profit_loss_ratio <= 1.0

    if win_rate < 35:
        score = 18 if is_lose_more else 15
    elif win_rate < 40:
        score = 14 if is_lose_more else 10
    elif win_rate < 45:
        score = 10 if is_lose_more else 6
    elif win_rate < 50:
        score = 6 if is_lose_more else 2
    else:
        score = 2 if is_lose_more else 0

    detail = f"胜率{win_rate:.1f}% | 盈亏比{profit_loss_ratio:.2f}({'亏更多' if is_lose_more else '亏更少'})"
    return score, detail


def score_liquidation_per_month(liq_per_month: float) -> tuple:
    """清算次数/月评分（10分）- 保留旧版，兼容v2"""
    if liq_per_month >= 3:
        return 10, f"清算{liq_per_month:.1f}/月（极高）"
    elif liq_per_month >= 2:
        return 7, f"清算{liq_per_month:.1f}/月（高）"
    elif liq_per_month >= 1:
        return 4, f"清算{liq_per_month:.1f}/月（中）"
    elif liq_per_month > 0:
        return 2, f"清算{liq_per_month:.2f}/月"
    else:
        return 0, "无清算"


def score_liquidation_v3(liquidation_count: int) -> tuple:
    """因子三：清算得分（V3，满分25分，按历史总次数）"""
    if liquidation_count >= 3:
        return 25, f"历史清算{liquidation_count}次（极高）"
    elif liquidation_count == 2:
        return 18, f"历史清算{liquidation_count}次（高）"
    elif liquidation_count == 1:
        return 12, f"历史清算{liquidation_count}次"
    else:
        return 0, "无清算记录"


def score_total_pnl_pct(total_pnl: float) -> tuple:
    """总PnL%评分（5分，需结合账户价值，此处简化按绝对值）"""
    if total_pnl < -100000:
        return 5, f"总亏{abs(total_pnl)/10000:.1f}万（严重）"
    elif total_pnl < -50000:
        return 4, f"总亏{abs(total_pnl)/10000:.1f}万"
    elif total_pnl < -10000:
        return 2, f"总亏{abs(total_pnl)/10000:.1f}万"
    elif total_pnl < 0:
        return 1, f"总亏{abs(total_pnl):.0f}"
    else:
        return 0, f"总盈{total_pnl:.0f}"


# ============================================================
# 评分函数：心态特征（20分）
# ============================================================

def score_consecutive_loss_add(count: int) -> tuple:
    """连续亏损后加仓评分（10分）"""
    if count >= 3:
        return 10, f"连亏后加仓{count}次（极高）"
    elif count >= 2:
        return 6, f"连亏后加仓{count}次（高）"
    elif count >= 1:
        return 3, f"连亏后加仓{count}次"
    else:
        return 0, "无连亏加仓"


def score_chase_ratio(coin_concentration: float) -> tuple:
    """
    追涨杀跌率评分（5分）
    
    简化版：用币种集中度替代（集中度高 → 追单一标的）
    """
    if coin_concentration >= 90:
        return 5, f"币种集中{coin_concentration:.0f}%（追单标）"
    elif coin_concentration >= 70:
        return 3, f"币种集中{coin_concentration:.0f}%"
    else:
        return 0, f"币种分散{coin_concentration:.0f}%"


def score_max_consecutive_loss(count: int) -> tuple:
    """
    最长连续亏损笔数评分（5分）
    
    反映心态崩溃程度
    """
    if count >= 10:
        return 5, f"连续亏损{count}笔（极高）"
    elif count >= 7:
        return 3, f"连续亏损{count}笔（高）"
    elif count >= 5:
        return 1, f"连续亏损{count}笔"
    else:
        return 0, f"连续亏损{count}笔"


# ============================================================
# 评分函数：加仓/做T（±15分）
# ============================================================

def score_refill_v3(avg_refill_count: float, scalping_count: int, is_excluded: int) -> tuple:
    """因子一：补仓模式得分（V3，满分15分）"""
    if is_excluded:
        return 0, f'剔除(做T={scalping_count}次或等差补仓)'
    count = int(round(avg_refill_count))
    if count == 0:
        return 15, '无补仓'
    elif count <= 4:
        return 11, f'平均补仓{count}次'
    elif count <= 9:
        return 7, f'平均补仓{count}次'
    elif count <= 15:
        return 4, f'平均补仓{count}次'
    else:
        return 2, f'平均补仓{count}次(高频)'


def score_holding_hours_v3(avg_holding_hours: float) -> tuple:
    """因子六：平均持仓时长得分（V3，满分5分）"""
    if avg_holding_hours > 168:  # > 7天
        return 5, f"平均持仓{avg_holding_hours:.1f}h（>7天）"
    elif avg_holding_hours >= 72:  # 72h~7天
        return 4, f"平均持仓{avg_holding_hours:.1f}h（3~7天）"
    elif avg_holding_hours >= 24:  # 24~72h
        return 3, f"平均持仓{avg_holding_hours:.1f}h（1~3天）"
    elif avg_holding_hours >= 6:   # 6~24h
        return 1, f"平均持仓{avg_holding_hours:.1f}h（6~24h）"
    else:                          # < 6h
        return 0, f"平均持仓{avg_holding_hours:.1f}h（<6h）"


def score_chase_rate_v3(chase_rate: float) -> tuple:
    """因子四-1：追涨杀跌率得分（V3，满分15分）"""
    if chase_rate > 55:
        return 20, f"追涨杀跌率{chase_rate:.1f}%"
    elif chase_rate >= 45:
        return 16, f"追涨杀跌率{chase_rate:.1f}%"
    elif chase_rate >= 35:
        return 12, f"追涨杀跌率{chase_rate:.1f}%"
    elif chase_rate >= 20:
        return 6, f"追涨杀跌率{chase_rate:.1f}%"
    else:
        return 0, f"追涨杀跌率{chase_rate:.1f}%"


def score_loss_concentration_v3(loss_concentration: float) -> tuple:
    """因子四-2：亏损集中度得分（V3，满分5分）"""
    if loss_concentration > 70:
        return 5, f"亏损集中度{loss_concentration:.1f}%"
    elif loss_concentration >= 30:
        return 2, f"亏损集中度{loss_concentration:.1f}%"
    else:
        return 0, f"亏损集中度{loss_concentration:.1f}%"


def score_trading_behavior(add_score: float, scalping_score: float) -> tuple:
    """
    加仓/做T行为得分（-6~+15）
    
    直接使用特征计算的得分
    """
    total = add_score + scalping_score
    if total >= 10:
        detail = f"加仓/做T{total:+.1f}分（极差）"
    elif total >= 5:
        detail = f"加仓/做T{total:+.1f}分（差）"
    elif total > 0:
        detail = f"加仓/做T{total:+.1f}分"
    elif total < -3:
        detail = f"加仓/做T{total:+.1f}分（有效策略）"
    else:
        detail = f"加仓/做T{total:+.1f}分"

    return total, detail


# ============================================================
# 综合评分
# ============================================================

def calculate_score(features: Dict) -> Dict:
    """计算综合脆弱评分（V3）"""
    # 因子一：补仓模式（15分）
    f1_score, f1_detail = score_refill_v3(
        features.get('avg_refill_count', 0),
        features.get('scalping_count', 0),
        features.get('is_excluded', 0)
    )

    # 因子二：综合盈亏（20分）
    f2_score, f2_detail = score_综合盈亏_v3(
        features['win_rate'],
        features['profit_loss_ratio']
    )

    # 因子三：清算得分（25分）
    f3_score, f3_detail = score_liquidation_v3(features['liquidation_count'])

    # 因子四：追涨杀跌率(15) + 亏损集中度(5) = 20分
    chase_score, chase_detail = score_chase_rate_v3(features.get('chase_rate', 0))
    loss_conc_score, loss_conc_detail = score_loss_concentration_v3(features.get('loss_concentration', 0))
    f4_score = min(chase_score + loss_conc_score, 20)
    f4_detail = f"{chase_detail} | {loss_conc_detail}"

    # 因子五：追加保证金次数（20分）
    margin_call_count = features.get('margin_call_count', 0)
    if margin_call_count >= 10:
        f5_score = 20
        f5_detail = f'追加保证金{margin_call_count}次（极度依赖）'
    elif margin_call_count >= 5:
        f5_score = 15
        f5_detail = f'追加保证金{margin_call_count}次（频繁）'
    elif margin_call_count >= 3:
        f5_score = 10
        f5_detail = f'追加保证金{margin_call_count}次'
    elif margin_call_count >= 1:
        f5_score = 5
        f5_detail = f'追加保证金{margin_call_count}次'
    else:
        f5_score = 0
        f5_detail = '无追加保证金记录（或数据不足）'

    # 因子六：平均持仓时长（5分）
    f6_score, f6_detail = score_holding_hours_v3(features.get('avg_holding_hours', 0))

    total_score = f1_score + f2_score + f3_score + f4_score + f5_score + f6_score

    # 等级划分（基于105分满分，70分以上重点监控）
    if total_score >= 85:
        level = 'L1'
    elif total_score >= 70:
        level = 'L2'
    elif total_score >= 50:
        level = 'L3'
    else:
        level = 'L4'  # 低风险（含负分）

    return {
        'factor1_score': round(f1_score, 2),
        'factor2_score': round(f2_score, 2),
        'factor3_score': round(f3_score, 2),
        'factor4_score': round(f4_score, 2),
        'factor5_score': round(f5_score, 2),
        'factor6_score': round(f6_score, 2),
        'total_score': round(total_score, 2),
        'fragile_level': level,
        'f1_detail': f1_detail,
        'f2_detail': f2_detail,
        'f3_detail': f3_detail,
        'f4_detail': f4_detail,
        'f5_detail': f5_detail,
        'f6_detail': f6_detail,
    }


def save_score(feature_id: int, address: str, score_result: Dict) -> int:
    """保存评分到 hl_fragile_scores 表"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO hl_fragile_scores (
                address, feature_id, scored_at,
                total_score, fragile_level,
                factor1_score, factor2_score, factor3_score,
                factor4_score, factor5_score, factor6_score
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            address, feature_id,
            score_result['total_score'],
            score_result['fragile_level'],
            score_result['factor1_score'],
            score_result['factor2_score'],
            score_result['factor3_score'],
            score_result['factor4_score'],
            score_result['factor5_score'],
            score_result['factor6_score'],
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存失败: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    print("=" * 70)
    print("脆弱地址评分计算 v2（新评分模型）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if len(sys.argv) > 1:
        address_filter = sys.argv[1]
    else:
        address_filter = None

    print("\n📊 获取特征数据...")
    features_list = get_latest_features(address_filter)

    if not features_list:
        print("❌ 无特征数据，请先运行 calculate_address_features_v2.py")
        return

    print(f"✅ {len(features_list)} 个地址\n")

    success_count = fail_count = 0

    for i, (feature_id, address, features) in enumerate(features_list, 1):
        print(f"\n[{i}/{len(features_list)}] {address}")

        try:
            result = calculate_score(features)
            score_id = save_score(feature_id, address, result)

            level_emoji = {'L1': '🔴', 'L2': '🟠', 'L3': '🟡', 'L4': '🟢'}
            emoji = level_emoji.get(result['fragile_level'], '⚪')

            print(f"   {emoji} 总分: {result['total_score']}/105  等级: {result['fragile_level']}")
            print(f"   ├ 因子一(补仓):     {result['factor1_score']:>4}/15   {result['f1_detail']}")
            print(f"   ├ 因子二(盈亏):     {result['factor2_score']:>4}/20   {result['f2_detail']}")
            print(f"   ├ 因子三(清算):     {result['factor3_score']:>4}/25   {result['f3_detail']}")
            print(f"   ├ 因子四(追涨+集中):{result['factor4_score']:>4}/20   {result['f4_detail']}")
            print(f"   ├ 因子五(追加保证金):{result['factor5_score']:>4}/20   {result['f5_detail']}")
            print(f"   └ 因子六(持仓时长): {result['factor6_score']:>4}/5    {result['f6_detail']}")
            print(f"   💾 已保存（ID: {score_id}）")

            success_count += 1

        except Exception as e:
            print(f"   ❌ {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"完成! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ {success_count} | ❌ {fail_count} | 总计: {len(features_list)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
