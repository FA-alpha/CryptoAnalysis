"""
计算脆弱地址评分并保存到 hl_fragile_scores 表
基于 hl_address_features 的数据进行评分
"""
import sys
import os
from typing import Dict, Optional, Tuple
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_utils import get_connection


def get_latest_features(address: str = None) -> list:
    """
    获取最新的特征数据
    
    Args:
        address: 可选，指定地址。不指定则获取所有
        
    Returns:
        特征记录列表 [(feature_id, address, features_dict), ...]
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if address:
            # 获取指定地址的最新特征
            cursor.execute('''
                SELECT id, address, 
                       win_rate, avg_leverage, liquidation_count,
                       avg_margin_utilization, max_margin_utilization,
                       total_trades, profit_loss_ratio, max_drawdown,
                       coin_concentration
                FROM hl_address_features
                WHERE address = %s
                ORDER BY calculated_at DESC
                LIMIT 1
            ''', (address,))
        else:
            # 获取所有地址的最新特征
            cursor.execute('''
                SELECT f.id, f.address,
                       f.win_rate, f.avg_leverage, f.liquidation_count,
                       f.avg_margin_utilization, f.max_margin_utilization,
                       f.total_trades, f.profit_loss_ratio, f.max_drawdown,
                       f.coin_concentration
                FROM hl_address_features f
                INNER JOIN (
                    SELECT address, MAX(calculated_at) as max_time
                    FROM hl_address_features
                    GROUP BY address
                ) latest ON f.address = latest.address 
                        AND f.calculated_at = latest.max_time
            ''')
        
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            feature_id, addr, *values = row
            features = {
                'win_rate': float(values[0] or 0),
                'avg_leverage': float(values[1] or 0),
                'liquidation_count': int(values[2] or 0),
                'avg_margin_utilization': float(values[3] or 0),
                'max_margin_utilization': float(values[4] or 0),
                'total_trades': int(values[5] or 0),
                'profit_loss_ratio': float(values[6] or 0),
                'max_drawdown': float(values[7] or 0),
                'coin_concentration': float(values[8] or 0)
            }
            result.append((feature_id, addr, features))
        
        return result
        
    finally:
        cursor.close()
        conn.close()


def calculate_risk_behavior_score(features: Dict) -> Tuple[int, str]:
    """
    计算风险行为评分（满分 40 分）
    
    指标：
    - 平均杠杆（15分）
    - 保证金使用率（15分）
    - 单币种集中度（10分）
    
    Returns:
        (评分, 评分详情)
    """
    score = 0
    details = []
    
    # 1. 平均杠杆（15分）
    avg_lev = features['avg_leverage']
    if avg_lev >= 20:
        lev_score = 15
        details.append(f"杠杆{avg_lev:.1f}x(极高)")
    elif avg_lev >= 15:
        lev_score = 12
        details.append(f"杠杆{avg_lev:.1f}x(很高)")
    elif avg_lev >= 10:
        lev_score = 8
        details.append(f"杠杆{avg_lev:.1f}x(高)")
    elif avg_lev >= 5:
        lev_score = 4
        details.append(f"杠杆{avg_lev:.1f}x(中)")
    else:
        lev_score = 0
        details.append(f"杠杆{avg_lev:.1f}x(低)")
    score += lev_score
    
    # 2. 保证金使用率（15分）
    margin_util = features['avg_margin_utilization']
    if margin_util >= 70:
        margin_score = 15
        details.append(f"保证金{margin_util:.1f}%(极高)")
    elif margin_util >= 60:
        margin_score = 12
        details.append(f"保证金{margin_util:.1f}%(很高)")
    elif margin_util >= 50:
        margin_score = 8
        details.append(f"保证金{margin_util:.1f}%(高)")
    elif margin_util >= 30:
        margin_score = 4
        details.append(f"保证金{margin_util:.1f}%(中)")
    else:
        margin_score = 0
        details.append(f"保证金{margin_util:.1f}%(低)")
    score += margin_score
    
    # 3. 单币种集中度（10分）
    concentration = features['coin_concentration']
    if concentration >= 90:
        conc_score = 10
        details.append(f"集中度{concentration:.1f}%(极高)")
    elif concentration >= 80:
        conc_score = 7
        details.append(f"集中度{concentration:.1f}%(高)")
    elif concentration >= 60:
        conc_score = 4
        details.append(f"集中度{concentration:.1f}%(中)")
    else:
        conc_score = 0
        details.append(f"集中度{concentration:.1f}%(低)")
    score += conc_score
    
    return score, " | ".join(details)


def calculate_loss_feature_score(features: Dict) -> Tuple[int, str]:
    """
    计算亏损特征评分（满分 35 分）
    
    指标：
    - 胜率（15分）
    - 清算次数（10分）
    - 最大回撤（10分）
    
    Returns:
        (评分, 评分详情)
    """
    score = 0
    details = []
    
    # 1. 胜率（15分，低=差）
    win_rate = features['win_rate']
    if win_rate < 20:
        wr_score = 15
        details.append(f"胜率{win_rate:.1f}%(极低)")
    elif win_rate < 30:
        wr_score = 12
        details.append(f"胜率{win_rate:.1f}%(很低)")
    elif win_rate < 40:
        wr_score = 8
        details.append(f"胜率{win_rate:.1f}%(低)")
    elif win_rate < 50:
        wr_score = 4
        details.append(f"胜率{win_rate:.1f}%(中)")
    else:
        wr_score = 0
        details.append(f"胜率{win_rate:.1f}%(正常)")
    score += wr_score
    
    # 2. 清算次数（10分）
    liq_count = features['liquidation_count']
    if liq_count >= 10:
        liq_score = 10
        details.append(f"清算{liq_count}次(极多)")
    elif liq_count >= 5:
        liq_score = 7
        details.append(f"清算{liq_count}次(多)")
    elif liq_count >= 2:
        liq_score = 4
        details.append(f"清算{liq_count}次(中)")
    elif liq_count >= 1:
        liq_score = 2
        details.append(f"清算{liq_count}次")
    else:
        liq_score = 0
        details.append("无清算")
    score += liq_score
    
    # 3. 最大回撤（10分）
    max_dd = features['max_drawdown']
    if max_dd >= 80:
        dd_score = 10
        details.append(f"回撤{max_dd:.1f}%(极大)")
    elif max_dd >= 60:
        dd_score = 7
        details.append(f"回撤{max_dd:.1f}%(大)")
    elif max_dd >= 40:
        dd_score = 4
        details.append(f"回撤{max_dd:.1f}%(中)")
    elif max_dd >= 20:
        dd_score = 2
        details.append(f"回撤{max_dd:.1f}%(小)")
    else:
        dd_score = 0
        details.append(f"回撤{max_dd:.1f}%")
    score += dd_score
    
    return score, " | ".join(details)


def calculate_mentality_score(features: Dict) -> Tuple[int, str]:
    """
    计算心态特征评分（满分 25 分）
    
    指标：
    - 盈亏比（15分，低=差）
    - 交易频率（10分，可能过度交易）
    
    Returns:
        (评分, 评分详情)
    """
    score = 0
    details = []
    
    # 1. 盈亏比（15分，低=差）
    pl_ratio = features['profit_loss_ratio']
    if pl_ratio < 0.5:
        pl_score = 15
        details.append(f"盈亏比{pl_ratio:.2f}(极差)")
    elif pl_ratio < 1.0:
        pl_score = 10
        details.append(f"盈亏比{pl_ratio:.2f}(差)")
    elif pl_ratio < 1.5:
        pl_score = 5
        details.append(f"盈亏比{pl_ratio:.2f}(中)")
    else:
        pl_score = 0
        details.append(f"盈亏比{pl_ratio:.2f}(好)")
    score += pl_score
    
    # 2. 交易次数（样本充足性）
    total_trades = features['total_trades']
    if total_trades < 10:
        trade_score = 10
        details.append(f"交易{total_trades}次(样本不足)")
    elif total_trades < 50:
        trade_score = 0
        details.append(f"交易{total_trades}次")
    else:
        trade_score = 0
        details.append(f"交易{total_trades}次(充足)")
    score += trade_score
    
    return score, " | ".join(details)


def determine_fragile_level(total_score: int) -> str:
    """
    根据总分确定脆弱等级
    
    Args:
        total_score: 总分（0-100）
        
    Returns:
        'L1', 'L2', 'L3', 'L4'
    """
    if total_score >= 75:
        return 'L1'  # 极度脆弱
    elif total_score >= 60:
        return 'L2'  # 高度脆弱
    elif total_score >= 40:
        return 'L3'  # 中度脆弱
    else:
        return 'L4'  # 轻度脆弱


def calculate_score(features: Dict) -> Dict:
    """
    计算综合评分
    
    Returns:
        评分结果字典
    """
    # 1. 风险行为评分
    risk_score, risk_details = calculate_risk_behavior_score(features)
    
    # 2. 亏损特征评分
    loss_score, loss_details = calculate_loss_feature_score(features)
    
    # 3. 心态特征评分
    mentality_score, mentality_details = calculate_mentality_score(features)
    
    # 4. 总分
    total_score = risk_score + loss_score + mentality_score
    
    # 5. 脆弱等级
    fragile_level = determine_fragile_level(total_score)
    
    return {
        'risk_behavior_score': risk_score,
        'loss_feature_score': loss_score,
        'mentality_score': mentality_score,
        'total_score': total_score,
        'fragile_level': fragile_level,
        'risk_details': risk_details,
        'loss_details': loss_details,
        'mentality_details': mentality_details
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
            ) VALUES (
                %s, %s, NOW(),
                %s, %s, %s,
                %s, %s
            )
        ''', (
            address,
            feature_id,
            score_result['risk_behavior_score'],
            score_result['loss_feature_score'],
            score_result['mentality_score'],
            score_result['total_score'],
            score_result['fragile_level']
        ))
        
        conn.commit()
        score_id = cursor.lastrowid
        
        return score_id
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 保存评分失败: {e}")
        raise
        
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("=" * 70)
    print("脆弱地址评分计算")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 获取最新特征数据
    print("\n📊 正在获取特征数据...")
    features_list = get_latest_features()
    
    if not features_list:
        print("❌ 没有找到特征数据")
        print("请先运行: python scripts/calculate_address_features.py")
        return
    
    print(f"✅ 找到 {len(features_list)} 个地址的特征\n")
    
    # 2. 逐个计算评分
    success_count = 0
    fail_count = 0
    
    for i, (feature_id, address, features) in enumerate(features_list, 1):
        print(f"\n[{i}/{len(features_list)}] {address[:10]}...")
        
        try:
            # 计算评分
            score_result = calculate_score(features)
            
            # 保存评分
            score_id = save_score(feature_id, address, score_result)
            
            # 显示结果
            print(f"   📊 总分: {score_result['total_score']}/100 (等级: {score_result['fragile_level']})")
            print(f"   - 风险行为: {score_result['risk_behavior_score']}/40")
            print(f"     {score_result['risk_details']}")
            print(f"   - 亏损特征: {score_result['loss_feature_score']}/35")
            print(f"     {score_result['loss_details']}")
            print(f"   - 心态特征: {score_result['mentality_score']}/25")
            print(f"     {score_result['mentality_details']}")
            print(f"   💾 评分已保存（ID: {score_id}）")
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ 评分失败: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
    
    # 3. 统计结果
    print("\n" + "=" * 70)
    print("执行完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n统计:")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 失败: {fail_count}")
    print(f"  📋 总计: {len(features_list)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
