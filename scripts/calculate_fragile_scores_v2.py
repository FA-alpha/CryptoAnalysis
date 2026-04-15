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
        if address:
            cursor.execute('''
                SELECT id, address,
                       win_rate, avg_leverage, liquidation_per_month,
                       avg_margin_utilization, has_refill_behavior,
                       consecutive_loss_add_count, max_consecutive_loss_count,
                       add_position_score, scalping_score,
                       total_realized_pnl, coin_concentration
                FROM hl_address_features
                WHERE address = %s
                ORDER BY calculated_at DESC LIMIT 1
            ''', (address,))
        else:
            cursor.execute('''
                SELECT f.id, f.address,
                       f.win_rate, f.avg_leverage, f.liquidation_per_month,
                       f.avg_margin_utilization, f.has_refill_behavior,
                       f.consecutive_loss_add_count, f.max_consecutive_loss_count,
                       f.add_position_score, f.scalping_score,
                       f.total_realized_pnl, f.coin_concentration
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
    """胜率评分（15分）"""
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


def score_liquidation_per_month(liq_per_month: float) -> tuple:
    """清算次数/月评分（10分）"""
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
    """计算综合脆弱评分"""
    # 风险行为（35分）
    lev_score, lev_detail = score_leverage(features['avg_leverage'])
    margin_score, margin_detail = score_margin_utilization(
        features['avg_margin_utilization'],
        features['has_refill_behavior']
    )
    risk_score = lev_score + margin_score
    risk_detail = f"{lev_detail} | {margin_detail}"

    # 亏损特征（30分）
    wr_score, wr_detail = score_win_rate(features['win_rate'])
    liq_score, liq_detail = score_liquidation_per_month(features['liquidation_per_month'])
    pnl_score, pnl_detail = score_total_pnl_pct(features['total_realized_pnl'])
    loss_score = wr_score + liq_score + pnl_score
    loss_detail = f"{wr_detail} | {liq_detail} | {pnl_detail}"

    # 心态特征（25分）
    loss_add_score, loss_add_detail = score_consecutive_loss_add(features['consecutive_loss_add_count'])
    chase_score, chase_detail = score_chase_ratio(features['coin_concentration'])
    max_loss_score, max_loss_detail = score_max_consecutive_loss(features['max_consecutive_loss_count'])
    mentality_score = loss_add_score + chase_score + max_loss_score
    mentality_detail = f"{loss_add_detail} | {chase_detail} | {max_loss_detail}"

    # 加仓/做T（±15分）
    trading_score, trading_detail = score_trading_behavior(
        features['add_position_score'],
        features['scalping_score']
    )

    total_score = risk_score + loss_score + mentality_score + trading_score

    # 等级划分
    if total_score >= 80:
        level = 'L1'  # 极高风险
    elif total_score >= 60:
        level = 'L2'  # 高风险
    elif total_score >= 40:
        level = 'L3'  # 中等风险
    else:
        level = 'L4'  # 低风险（含负分）

    return {
        'risk_behavior_score': int(risk_score),
        'loss_feature_score': int(loss_score),
        'mentality_score': int(mentality_score),
        'trading_behavior_score': round(trading_score, 2),
        'total_score': round(total_score, 2),
        'fragile_level': level,
        'risk_details': risk_detail,
        'loss_details': loss_detail,
        'mentality_details': mentality_detail,
        'trading_details': trading_detail,
    }


def save_score(feature_id: int, address: str, score_result: Dict) -> int:
    """保存评分到 hl_fragile_scores 表"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO hl_fragile_scores (
                address, feature_id, scored_at,
                risk_behavior_score, loss_feature_score, mentality_score,
                trading_behavior_score, total_score, fragile_level
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
        ''', (
            address, feature_id,
            score_result['risk_behavior_score'],
            score_result['loss_feature_score'],
            score_result['mentality_score'],
            score_result['trading_behavior_score'],
            score_result['total_score'],
            score_result['fragile_level'],
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

            print(f"   {emoji} 总分: {result['total_score']}/~100  等级: {result['fragile_level']}")
            print(f"   ├ 风险行为:  {result['risk_behavior_score']:>2}/35   {result['risk_details']}")
            print(f"   ├ 亏损特征:  {result['loss_feature_score']:>2}/30   {result['loss_details']}")
            print(f"   ├ 心态特征:  {result['mentality_score']:>2}/20   {result['mentality_details']}")
            print(f"   └ 加仓/做T:  {result['trading_behavior_score']:>5.1f}/±15  {result['trading_details']}")
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
