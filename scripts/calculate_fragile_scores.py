"""
计算脆弱地址评分并保存到 hl_fragile_scores 表
基于 hl_address_features 的最新数据进行评分

评分体系（总分 100 分）：
  风险行为（35分）：平均杠杆(15) + 保证金使用率(20)
  亏损特征（40分）：胜率(15) + 盈亏比(15) + 历史亏损倍数(10)
  行为模式（25分）：全仓止损次数(15) + 单币种集中度(10)

等级划分：L1≥75 / L2≥60 / L3≥40 / L4<40
"""
import sys
import os
from typing import Dict, Optional, Tuple, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection


def get_latest_features(address: str = None) -> List[tuple]:
    """
    获取最新的特征数据

    Args:
        address: 指定地址，None 则获取所有地址

    Returns:
        [(feature_id, address, features_dict), ...]
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if address:
            cursor.execute('''
                SELECT id, address,
                       win_rate, avg_leverage, liquidation_count,
                       avg_margin_utilization, max_margin_utilization,
                       total_trades, profit_loss_ratio, max_drawdown,
                       coin_concentration
                FROM hl_address_features
                WHERE address = %s
                ORDER BY calculated_at DESC LIMIT 1
            ''', (address,))
        else:
            cursor.execute('''
                SELECT f.id, f.address,
                       f.win_rate, f.avg_leverage, f.liquidation_count,
                       f.avg_margin_utilization, f.max_margin_utilization,
                       f.total_trades, f.profit_loss_ratio, f.max_drawdown,
                       f.coin_concentration
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
                'win_rate':               float(vals[0] or 0),   # 胜率（%）
                'avg_leverage':           float(vals[1] or 0),   # 平均杠杆
                'full_close_loss_count':  int(vals[2] or 0),     # 全仓止损次数（liquidation_count 字段）
                'avg_margin_utilization': float(vals[3] or 0),   # 平均保证金使用率（%）
                'max_margin_utilization': float(vals[4] or 0),
                'total_trades':           int(vals[5] or 0),
                'profit_loss_ratio':      float(vals[6] or 0),   # 盈亏比
                'pnl_loss_ratio':         float(vals[7] or 0),   # 历史亏损倍数（max_drawdown 字段）
                'coin_concentration':     float(vals[8] or 0),   # 单币种集中度（%）
            }
            result.append((feature_id, addr, features))

        return result

    finally:
        cursor.close()
        conn.close()


# ============================================================
# 评分函数：风险行为（35分）
# ============================================================

def score_avg_leverage(avg_leverage: float) -> Tuple[int, str]:
    """
    平均杠杆评分（15分）

    数据来源：hl_position_details.leverage_value AVG
    注意：快照数据积累越多越准确

    阈值依据（实测样本）：
      爆仓达人3: 40x / 爆仓达人2: 30x / 爆仓达人1: 25x / 麻吉大哥: 22x
    """
    if avg_leverage >= 35:
        return 15, f"平均杠杆{avg_leverage:.1f}x（极高）"
    elif avg_leverage >= 25:
        return 11, f"平均杠杆{avg_leverage:.1f}x（很高）"
    elif avg_leverage >= 15:
        return 7, f"平均杠杆{avg_leverage:.1f}x（高）"
    elif avg_leverage >= 5:
        return 3, f"平均杠杆{avg_leverage:.1f}x（中）"
    else:
        return 0, f"平均杠杆{avg_leverage:.1f}x（低）"


def score_margin_utilization(avg_margin: float) -> Tuple[int, str]:
    """
    平均保证金使用率评分（20分）

    数据来源：AVG(total_margin_used / account_value)
    阈值依据：
      爆仓达人1: 100% / 爆仓达人3: 71% / 麻吉大哥: 41% / 爆仓达人2: 34%
    """
    if avg_margin >= 90:
        return 20, f"保证金使用率{avg_margin:.1f}%（极高）"
    elif avg_margin >= 60:
        return 15, f"保证金使用率{avg_margin:.1f}%（很高）"
    elif avg_margin >= 40:
        return 8, f"保证金使用率{avg_margin:.1f}%（高）"
    elif avg_margin >= 20:
        return 3, f"保证金使用率{avg_margin:.1f}%（中）"
    else:
        return 0, f"保证金使用率{avg_margin:.1f}%（低）"


# ============================================================
# 评分函数：亏损特征（40分）
# ============================================================

def score_win_rate(win_rate: float) -> Tuple[int, str]:
    """
    胜率评分（15分）

    数据来源：hl_fills Close记录中 closed_pnl > 0 的比例
    含义：每次平仓操作是否盈利（含分批减仓的每次操作）
    阈值依据：
      爆仓达人3: 30% / 爆仓达人1: 37% / 爆仓达人2: 79% / 麻吉大哥: 82%
    注意：高胜率未必是好事，需结合盈亏比综合判断
    """
    if win_rate < 30:
        return 15, f"胜率{win_rate:.1f}%（极低）"
    elif win_rate < 40:
        return 11, f"胜率{win_rate:.1f}%（很低）"
    elif win_rate < 50:
        return 6, f"胜率{win_rate:.1f}%（低）"
    elif win_rate < 60:
        return 2, f"胜率{win_rate:.1f}%（中）"
    else:
        return 0, f"胜率{win_rate:.1f}%（正常）"


def score_profit_loss_ratio(pl_ratio: float) -> Tuple[int, str]:
    """
    盈亏比评分（15分）

    数据来源：AVG(closed_pnl>0) / |AVG(closed_pnl<0)|
    含义：平均每次盈利 / 平均每次亏损，越低说明输大赢小
    阈值依据：
      爆仓达人2: 0.07 / 麻吉大哥: 0.15 / 爆仓达人1: 0.78 / 爆仓达人3: 1.35
    关键洞察：麻吉大哥胜率82%但盈亏比0.15，典型"赢多次小利、输一次大亏"
    """
    if pl_ratio < 0.1:
        return 15, f"盈亏比{pl_ratio:.2f}（极差，输大赢小）"
    elif pl_ratio < 0.3:
        return 11, f"盈亏比{pl_ratio:.2f}（很差）"
    elif pl_ratio < 0.6:
        return 7, f"盈亏比{pl_ratio:.2f}（差）"
    elif pl_ratio < 1.0:
        return 3, f"盈亏比{pl_ratio:.2f}（中）"
    else:
        return 0, f"盈亏比{pl_ratio:.2f}（正常）"


def score_pnl_loss_ratio(pnl_loss_ratio: float) -> Tuple[int, str]:
    """
    历史亏损倍数评分（10分）

    数据来源：|pnl_all_time| / 当前 account_value
    含义：历史总亏损是当前账户价值的多少倍，反映长期亏损严重程度
    阈值依据（实测）：
      爆仓达人3: 84x / 爆仓达人2: 48x / 爆仓达人1: 40x / 麻吉大哥: 11x
    """
    if pnl_loss_ratio >= 50:
        return 10, f"历史亏损{pnl_loss_ratio:.0f}倍账户（极严重）"
    elif pnl_loss_ratio >= 20:
        return 7, f"历史亏损{pnl_loss_ratio:.0f}倍账户（严重）"
    elif pnl_loss_ratio >= 10:
        return 4, f"历史亏损{pnl_loss_ratio:.0f}倍账户（较重）"
    elif pnl_loss_ratio >= 3:
        return 2, f"历史亏损{pnl_loss_ratio:.0f}倍账户（中）"
    else:
        return 0, f"历史亏损{pnl_loss_ratio:.1f}倍账户（轻）"


# ============================================================
# 评分函数：行为模式（25分）
# ============================================================

def score_full_close_loss_count(count: int) -> Tuple[int, str]:
    """
    全仓止损次数评分（15分）

    数据来源：hl_fills 中 sz ≈ start_position（差异<2%）+ Close + closed_pnl < 0
    含义：整体仓位一次性亏损平仓次数，包含爆仓、止损、强平等
    阈值依据：
      爆仓达人3: 99次 / 爆仓达人1: 40次 / 爆仓达人2: 31次 / 麻吉大哥: 5次
    """
    if count >= 50:
        return 15, f"全仓止损{count}次（极多）"
    elif count >= 20:
        return 11, f"全仓止损{count}次（多）"
    elif count >= 10:
        return 6, f"全仓止损{count}次（较多）"
    elif count >= 3:
        return 3, f"全仓止损{count}次（少）"
    else:
        return 0, f"全仓止损{count}次"


def score_coin_concentration(concentration: float) -> Tuple[int, str]:
    """
    单币种集中度评分（10分）

    数据来源：hl_fills 中交易量最多的币种 / 总交易笔数
    含义：交易越集中在单一币种，风险越集中
    """
    if concentration >= 95:
        return 10, f"单币种集中度{concentration:.1f}%（极高）"
    elif concentration >= 80:
        return 7, f"单币种集中度{concentration:.1f}%（高）"
    elif concentration >= 60:
        return 3, f"单币种集中度{concentration:.1f}%（中）"
    else:
        return 0, f"单币种集中度{concentration:.1f}%（分散）"


# ============================================================
# 综合评分
# ============================================================

def calculate_score(features: Dict) -> Dict:
    """
    计算综合脆弱评分

    Returns:
        包含各维度得分、总分、等级、详情的字典
    """
    # 风险行为（35分）
    lev_score, lev_detail = score_avg_leverage(features['avg_leverage'])
    margin_score, margin_detail = score_margin_utilization(features['avg_margin_utilization'])
    risk_score = lev_score + margin_score
    risk_detail = f"{lev_detail} | {margin_detail}"

    # 亏损特征（40分）
    wr_score, wr_detail = score_win_rate(features['win_rate'])
    pl_score, pl_detail = score_profit_loss_ratio(features['profit_loss_ratio'])
    pnl_score, pnl_detail = score_pnl_loss_ratio(features['pnl_loss_ratio'])
    loss_score = wr_score + pl_score + pnl_score
    loss_detail = f"{wr_detail} | {pl_detail} | {pnl_detail}"

    # 行为模式（25分）
    full_close_score, full_close_detail = score_full_close_loss_count(features['full_close_loss_count'])
    conc_score, conc_detail = score_coin_concentration(features['coin_concentration'])
    behavior_score = full_close_score + conc_score
    behavior_detail = f"{full_close_detail} | {conc_detail}"

    total_score = risk_score + loss_score + behavior_score

    # 等级划分
    if total_score >= 75:
        level = 'L1'  # 极度脆弱
    elif total_score >= 60:
        level = 'L2'  # 高度脆弱
    elif total_score >= 40:
        level = 'L3'  # 中度脆弱
    else:
        level = 'L4'  # 轻度脆弱

    return {
        'risk_behavior_score': risk_score,
        'loss_feature_score': loss_score,
        'mentality_score': behavior_score,       # 字段复用：行为模式
        'total_score': total_score,
        'fragile_level': level,
        'risk_details': risk_detail,
        'loss_details': loss_detail,
        'mentality_details': behavior_detail,
    }


def save_score(feature_id: int, address: str, score_result: Dict) -> int:
    """
    保存评分到 hl_fragile_scores 表

    Returns:
        插入的 score_id
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO hl_fragile_scores (
                address, feature_id, scored_at,
                risk_behavior_score, loss_feature_score, mentality_score,
                total_score, fragile_level
            ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
        ''', (
            address, feature_id,
            score_result['risk_behavior_score'],
            score_result['loss_feature_score'],
            score_result['mentality_score'],
            score_result['total_score'],
            score_result['fragile_level'],
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存评分失败: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    """
    主函数

    用法：
        python calculate_fragile_scores.py              # 计算所有地址
        python calculate_fragile_scores.py <address>   # 计算单个地址
    """
    print("=" * 70)
    print("脆弱地址评分计算")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if len(sys.argv) > 1:
        address_filter = sys.argv[1]
    else:
        address_filter = None

    print("\n📊 正在获取特征数据...")
    features_list = get_latest_features(address_filter)

    if not features_list:
        print("❌ 没有找到特征数据，请先运行 calculate_address_features.py")
        return

    print(f"✅ 找到 {len(features_list)} 个地址的特征\n")

    success_count = fail_count = 0

    for i, (feature_id, address, features) in enumerate(features_list, 1):
        print(f"\n[{i}/{len(features_list)}] {address}")

        try:
            result = calculate_score(features)
            score_id = save_score(feature_id, address, result)

            level_emoji = {'L1': '🔴', 'L2': '🟠', 'L3': '🟡', 'L4': '🟢'}
            emoji = level_emoji.get(result['fragile_level'], '⚪')

            print(f"   {emoji} 总分: {result['total_score']}/100  等级: {result['fragile_level']}")
            print(f"   ├ 风险行为:  {result['risk_behavior_score']:>2}/35  {result['risk_details']}")
            print(f"   ├ 亏损特征:  {result['loss_feature_score']:>2}/40  {result['loss_details']}")
            print(f"   └ 行为模式:  {result['mentality_score']:>2}/25  {result['mentality_details']}")
            print(f"   💾 评分已保存（ID: {score_id}）")

            success_count += 1

        except Exception as e:
            print(f"   ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"执行完成! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ 成功: {success_count} | ❌ 失败: {fail_count} | 总计: {len(features_list)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
