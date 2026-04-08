-- =============================================
-- CryptoAnalysis 数据库表结构
-- 项目:Hyperliquid 反脆弱策略系统
-- 版本:v1.0
-- 创建时间:2026-04-03
-- =============================================

-- =============================================
-- 1. 地址列表表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_address_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL UNIQUE COMMENT '钱包地址',
    label VARCHAR(100) COMMENT '地址标签/别名',
    source VARCHAR(50) DEFAULT 'hyperbot' COMMENT '来源:hyperbot/manual',
    first_seen_at DATETIME NOT NULL COMMENT '首次发现时间',
    last_updated_at DATETIME NOT NULL COMMENT '最后更新时间',
    status ENUM('active', 'inactive', 'excluded') DEFAULT 'active' COMMENT '状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_last_updated (last_updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址列表';


-- =============================================
-- 2. 交易历史表(原始数据)
-- =============================================
CREATE TABLE IF NOT EXISTS hl_fills (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    sz DECIMAL(20, 8) NOT NULL COMMENT '成交数量',
    px DECIMAL(20, 6) NOT NULL COMMENT '成交价格',
    dir VARCHAR(20) NOT NULL COMMENT '方向:Open Long/Open Short/Close Long/Close Short/Liquidation',
    closed_pnl DECIMAL(20, 6) DEFAULT 0 COMMENT '已实现盈亏(平仓时)',
    fee DECIMAL(20, 6) DEFAULT 0 COMMENT '手续费',
    fee_token VARCHAR(10) DEFAULT 'USDC' COMMENT '手续费币种',
    time BIGINT NOT NULL COMMENT '成交时间戳(毫秒)',
    hash VARCHAR(100) NOT NULL COMMENT '订单哈希',
    tid BIGINT NOT NULL COMMENT '成交ID（唯一标识）',
    oid BIGINT NOT NULL COMMENT '订单ID',
    twap_id VARCHAR(100) COMMENT 'TWAP订单ID',
    side VARCHAR(5) COMMENT '主动方向:B=买入主动/A=卖出主动',
    start_position DECIMAL(20, 8) COMMENT '成交前持仓',
    crossed BOOLEAN DEFAULT TRUE COMMENT '是否全仓模式',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（北京时间）',

    UNIQUE KEY uk_tid (tid),
    INDEX idx_address_time (address, time DESC),
    INDEX idx_hash (hash),
    INDEX idx_oid (oid),
    INDEX idx_coin (coin),
    INDEX idx_dir (dir),
    INDEX idx_time (time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易历史(原始数据)';


-- =============================================
-- 3. 持仓快照表(账户级别)
-- =============================================
CREATE TABLE IF NOT EXISTS hl_position_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    snapshot_time BIGINT NOT NULL COMMENT '快照时间戳(毫秒)',
    account_value DECIMAL(20, 6) NOT NULL COMMENT '账户总价值',
    total_margin_used DECIMAL(20, 6) NOT NULL COMMENT '已用保证金',
    total_raw_usd DECIMAL(20, 6) COMMENT '钱包余额/USD净余额(可为负)',
    total_ntl_pos DECIMAL(20, 6) COMMENT '总名义持仓价值',
    withdrawable DECIMAL(20, 6) COMMENT '可提现金额',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（北京时间）',

    UNIQUE KEY uk_address_time (address, snapshot_time),
    INDEX idx_snapshot_time (snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持仓快照(账户级别)';


-- =============================================
-- 4. 持仓明细表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_position_details (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL COMMENT '关联 hl_position_snapshots.id',
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    szi DECIMAL(20, 8) NOT NULL COMMENT '持仓数量(正=多,负=空)',
    entry_px DECIMAL(20, 6) NOT NULL COMMENT '开仓均价',
    position_value DECIMAL(20, 6) NOT NULL COMMENT '仓位价值',
    unrealized_pnl DECIMAL(20, 6) DEFAULT 0 COMMENT '未实现盈亏',
    return_on_equity DECIMAL(10, 6) DEFAULT 0 COMMENT 'ROE(回报率)',
    liquidation_px DECIMAL(20, 6) COMMENT '清算价(null=无风险)',
    margin_used DECIMAL(20, 6) COMMENT '占用保证金',
    leverage_type VARCHAR(20) COMMENT '杠杆类型:cross/isolated',
    leverage_value INT COMMENT '实际杠杆倍数',
    max_leverage INT COMMENT '最大允许杠杆',
    cum_funding_all_time DECIMAL(20, 6) COMMENT '历史累计资金费',
    cum_funding_since_open DECIMAL(20, 6) COMMENT '开仓后累计资金费',

    FOREIGN KEY (snapshot_id) REFERENCES hl_position_snapshots(id) ON DELETE CASCADE,
    INDEX idx_snapshot_coin (snapshot_id, coin),
    INDEX idx_coin (coin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持仓明细(每个快照的持仓列表)';


-- =============================================
-- 5. 地址特征表(计算结果)
-- =============================================
CREATE TABLE IF NOT EXISTS hl_address_features (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    calculated_at DATETIME NOT NULL COMMENT '计算时间',
    data_period_start BIGINT COMMENT '数据起始时间戳(ms)',
    data_period_end BIGINT COMMENT '数据结束时间戳(ms)',

    -- 基础统计(从 hl_fills 计算)
    total_trades INT NOT NULL DEFAULT 0 COMMENT '总交易次数',
    win_rate DECIMAL(5, 2) COMMENT '胜率(%)',
    avg_win_pnl DECIMAL(20, 6) COMMENT '平均盈利',
    avg_loss_pnl DECIMAL(20, 6) COMMENT '平均亏损',
    profit_loss_ratio DECIMAL(10, 2) COMMENT '盈亏比',
    total_realized_pnl DECIMAL(20, 6) COMMENT '总已实现盈亏',
    total_fee DECIMAL(20, 6) COMMENT '总手续费',

    -- 风险指标(从 hl_position_snapshots 计算)
    avg_leverage DECIMAL(10, 2) COMMENT '平均实际杠杆',
    max_leverage DECIMAL(10, 2) COMMENT '最大实际杠杆',
    avg_margin_utilization DECIMAL(5, 2) COMMENT '平均保证金使用率(%)',
    max_margin_utilization DECIMAL(5, 2) COMMENT '最大保证金使用率(%)',
    coin_concentration DECIMAL(5, 2) COMMENT '单币种集中度(%)',

    -- 亏损特征
    liquidation_count INT DEFAULT 0 COMMENT '清算次数',
    max_drawdown DECIMAL(5, 2) COMMENT '最大回撤(%)',

    -- 心态特征(从 hl_fills 分析)
    loss_add_ratio DECIMAL(5, 2) COMMENT '浮亏加仓率(%)',
    hold_loss_ratio DECIMAL(10, 2) COMMENT '死扛指数(亏损持仓时间/盈利持仓时间)',
    chase_ratio DECIMAL(5, 2) COMMENT '追涨杀跌率(%)',

    -- 持仓时间统计(秒级别)
    total_loss_holding_seconds BIGINT COMMENT '亏损持仓总时长(秒)',
    total_profit_holding_seconds BIGINT COMMENT '盈利持仓总时长(秒)',
    avg_loss_holding_seconds DECIMAL(20, 2) COMMENT '平均亏损持仓时长(秒)',
    avg_profit_holding_seconds DECIMAL(20, 2) COMMENT '平均盈利持仓时长(秒)',

    -- 活跃度
    active_days INT COMMENT '活跃天数',
    avg_trades_per_day DECIMAL(10, 2) COMMENT '日均交易次数',
    last_trade_time BIGINT COMMENT '最后一笔交易时间戳(ms)',

    INDEX idx_address_time (address, calculated_at DESC),
    INDEX idx_calculated_at (calculated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地址特征(计算结果)';


-- =============================================
-- 6. 脆弱地址评分表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_fragile_scores (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    feature_id BIGINT COMMENT '关联 hl_address_features.id',
    scored_at DATETIME NOT NULL COMMENT '评分时间',

    -- 评分详情
    risk_behavior_score INT NOT NULL COMMENT '风险行为评分 /40',
    loss_feature_score INT NOT NULL COMMENT '亏损特征评分 /35',
    mentality_score INT NOT NULL COMMENT '心态特征评分 /25',
    total_score INT NOT NULL COMMENT '总分 /100',

    -- 分级
    fragile_level ENUM('L1', 'L2', 'L3', 'L4') COMMENT '脆弱等级',

    -- 池子管理
    in_pool BOOLEAN DEFAULT FALSE COMMENT '是否入池',
    pool_weight DECIMAL(5, 4) DEFAULT 0 COMMENT '池子权重',
    pool_entry_date DATE COMMENT '入池日期',
    pool_exit_date DATE COMMENT '出池日期',

    FOREIGN KEY (feature_id) REFERENCES hl_address_features(id) ON DELETE SET NULL,
    INDEX idx_address_time (address, scored_at DESC),
    INDEX idx_level_score (fragile_level, total_score DESC),
    INDEX idx_in_pool (in_pool, fragile_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='脆弱地址评分';


-- =============================================
-- 7. 脆弱地址池(实时监控)
-- =============================================
CREATE TABLE IF NOT EXISTS hl_fragile_pool (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL UNIQUE COMMENT '钱包地址',
    label VARCHAR(100) COMMENT '地址标签',
    fragile_level ENUM('L1', 'L2', 'L3', 'L4') NOT NULL COMMENT '脆弱等级',
    pool_weight DECIMAL(5, 4) NOT NULL DEFAULT 0 COMMENT '池子权重(0-1)',

    -- 监控状态
    monitor_status ENUM('active', 'paused', 'stopped') DEFAULT 'active' COMMENT '监控状态',
    last_monitored_at DATETIME COMMENT '最后监控时间',
    last_fill_time BIGINT COMMENT '最后一笔 fill 时间戳(ms,用于增量获取)',

    -- 统计信息
    total_signals INT DEFAULT 0 COMMENT '生成信号总数',
    total_trades INT DEFAULT 0 COMMENT '跟单交易总数',

    -- 入池信息
    entry_date DATE NOT NULL COMMENT '入池日期',
    entry_score INT COMMENT '入池时的评分',
    exit_date DATE COMMENT '出池日期(NULL=仍在池中)',
    exit_reason VARCHAR(100) COMMENT '出池原因',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_monitor_status (monitor_status, last_monitored_at),
    INDEX idx_level (fragile_level),
    INDEX idx_entry_date (entry_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='脆弱地址池(实时监控)';


-- =============================================
-- 8. 反向跟单信号表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_reverse_signals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    signal_id VARCHAR(50) NOT NULL UNIQUE COMMENT '信号ID(防重复)',
    source_address VARCHAR(66) NOT NULL COMMENT '脆弱地址',
    signal_type ENUM('new_position', 'add_position', 'close_position', 'liquidation') NOT NULL COMMENT '信号类型',

    -- 原始操作信息
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    original_direction VARCHAR(20) NOT NULL COMMENT '脆弱地址的操作方向',
    original_size DECIMAL(20, 8) NOT NULL COMMENT '脆弱地址的操作数量',
    original_price DECIMAL(20, 6) NOT NULL COMMENT '脆弱地址的成交价',
    original_fill_time BIGINT NOT NULL COMMENT '脆弱地址的成交时间戳(ms)',

    -- 反向操作建议
    reverse_direction VARCHAR(20) NOT NULL COMMENT '反向操作方向',
    reverse_size DECIMAL(20, 8) NOT NULL COMMENT '反向操作建议数量',
    reverse_weight DECIMAL(5, 4) NOT NULL COMMENT '信号权重(基于地址权重)',

    -- 信号状态
    signal_status ENUM('pending', 'executed', 'cancelled', 'expired') DEFAULT 'pending' COMMENT '信号状态',
    generated_at DATETIME NOT NULL COMMENT '生成时间',
    executed_at DATETIME COMMENT '执行时间',
    cancel_reason VARCHAR(200) COMMENT '取消原因',

    -- 执行结果(如果执行了)
    executed_price DECIMAL(20, 6) COMMENT '实际成交价',
    executed_size DECIMAL(20, 8) COMMENT '实际成交量',
    slippage DECIMAL(10, 6) COMMENT '滑点(%)',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_source_address (source_address, generated_at DESC),
    INDEX idx_signal_status (signal_status, generated_at DESC),
    INDEX idx_coin (coin),
    INDEX idx_generated_at (generated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='反向跟单信号';


-- =============================================
-- 9. 跟单交易记录表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_follow_trades (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trade_id VARCHAR(50) NOT NULL UNIQUE COMMENT '交易ID',
    signal_id VARCHAR(50) NOT NULL COMMENT '关联信号ID',
    source_address VARCHAR(66) NOT NULL COMMENT '脆弱地址',

    -- 交易信息
    coin VARCHAR(20) NOT NULL COMMENT '币种',
    direction VARCHAR(20) NOT NULL COMMENT '方向:Long/Short',
    action ENUM('open', 'add', 'reduce', 'close') NOT NULL COMMENT '操作:开仓/加仓/减仓/平仓',
    size DECIMAL(20, 8) NOT NULL COMMENT '数量',
    entry_price DECIMAL(20, 6) NOT NULL COMMENT '开仓价',
    close_price DECIMAL(20, 6) COMMENT '平仓价(如果已平仓)',

    -- 成本与收益
    fee DECIMAL(20, 6) NOT NULL COMMENT '手续费',
    realized_pnl DECIMAL(20, 6) COMMENT '已实现盈亏(平仓后)',

    -- 状态
    trade_status ENUM('open', 'closed') DEFAULT 'open' COMMENT '交易状态',
    opened_at DATETIME NOT NULL COMMENT '开仓时间',
    closed_at DATETIME COMMENT '平仓时间',

    -- 关联信息
    original_fill_hash VARCHAR(100) COMMENT '脆弱地址的原始 fill hash',
    our_fill_hash VARCHAR(100) COMMENT '我们的成交 hash',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (signal_id) REFERENCES hl_reverse_signals(signal_id),
    INDEX idx_source_address (source_address),
    INDEX idx_trade_status (trade_status, coin),
    INDEX idx_opened_at (opened_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='跟单交易记录';


-- =============================================
-- 10. 实时监控日志表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_monitor_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '监控地址',
    check_time DATETIME NOT NULL COMMENT '检查时间',

    -- 检查结果
    has_new_fills BOOLEAN NOT NULL COMMENT '是否有新 fills',
    new_fills_count INT DEFAULT 0 COMMENT '新 fills 数量',
    signals_generated INT DEFAULT 0 COMMENT '生成信号数量',

    -- 执行时间
    execution_time_ms INT COMMENT '执行耗时(ms)',

    -- 错误信息
    error_occurred BOOLEAN DEFAULT FALSE COMMENT '是否发生错误',
    error_message TEXT COMMENT '错误信息',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_address_time (address, check_time DESC),
    INDEX idx_check_time (check_time DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实时监控日志';


-- =============================================
-- 11. 回测结果表
-- =============================================
CREATE TABLE IF NOT EXISTS hl_backtest_results (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(66) NOT NULL COMMENT '钱包地址',
    backtest_name VARCHAR(100) COMMENT '回测名称/批次',
    backtest_date DATE NOT NULL COMMENT '回测日期',
    period_start BIGINT NOT NULL COMMENT '回测期起始时间戳(ms)',
    period_end BIGINT NOT NULL COMMENT '回测期结束时间戳(ms)',

    -- 回测指标
    reverse_trade_count INT COMMENT '反向交易次数',
    reverse_win_rate DECIMAL(5, 2) COMMENT '反向胜率(%)',
    reverse_total_pnl DECIMAL(20, 6) COMMENT '反向总盈亏',
    reverse_profit_loss_ratio DECIMAL(10, 2) COMMENT '反向盈亏比',
    max_drawdown DECIMAL(5, 2) COMMENT '最大回撤(%)',
    sharpe_ratio DECIMAL(10, 2) COMMENT '夏普比率',

    -- 稳定性
    classification_stable BOOLEAN COMMENT '分类是否稳定',
    avg_score DECIMAL(10, 2) COMMENT '期间平均评分',
    score_volatility DECIMAL(10, 2) COMMENT '评分波动率',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_address (address),
    INDEX idx_backtest_name (backtest_name),
    INDEX idx_backtest_date (backtest_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测结果';


-- =============================================
-- 视图：订单汇总（v_order_summary）
-- =============================================
CREATE OR REPLACE VIEW v_order_summary AS
SELECT 
    address,
    oid,
    hash,
    coin,
    dir,
    COUNT(*) as fill_count,
    SUM(sz) as total_sz,
    AVG(px) as avg_px,
    SUM(fee) as total_fee,
    SUM(closed_pnl) as total_pnl,
    MIN(time) as first_fill_time,
    MAX(time) as last_fill_time,
    MIN(start_position) as start_position,
    MIN(start_position) + (CASE 
        WHEN dir LIKE '%Long' THEN SUM(sz)
        WHEN dir LIKE '%Short' THEN -SUM(sz)
        ELSE 0
    END) as end_position,
    MAX(crossed) as is_crossed
FROM hl_fills
GROUP BY address, oid, hash, coin, dir;


-- =============================================
-- 完成提示
-- =============================================
-- 建表完成!
--
-- 表结构:
--   - 11 张数据表
--   - 1 个视图（v_order_summary）
--
-- 下一步:
-- 1. 在目标数据库执行此 SQL 文件: mysql -h <host> -u <user> -p <database> < sql/schema.sql
-- 2. 验证表结构: SHOW TABLES;
-- 3. 配置 config/.env 文件
-- 4. 开始数据采集: python scripts/fetch_address_fills.py <address>
-- =============================================
