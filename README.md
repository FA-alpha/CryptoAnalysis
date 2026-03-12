# CryptoAnalysis - Hyperliquid 交易策略分析系统

基于 Hyperliquid 链上透明数据的量化交易策略研究项目。

## 📋 策略概览

本项目包含四套核心策略，利用 DEX 链上数据透明的特性：

| 策略 | 预估胜率 | 技术难度 | 说明 |
|------|----------|----------|------|
| [多空比极端反向](docs/strategy-01-long-short-ratio.md) | 65-70% | ⭐ | 散户共识反向 |
| [清算密集区反向](docs/strategy-02-liquidation-zone.md) | 70-75% | ⭐⭐⭐ | 清算瀑布后抄底 |
| [亏损地址反向](docs/strategy-03-loser-reverse.md) | 60-65% | ⭐⭐⭐⭐ | 跟踪韭菜反向操作 |
| [聪明钱跟单](docs/strategy-04-smart-money.md) | 60-70% | ⭐⭐⭐⭐ | 跟随盈利地址 |

## 🏗️ 项目结构

```
CryptoAnalysis/
├── docs/                       # 策略文档
│   ├── strategy-01-long-short-ratio.md
│   ├── strategy-02-liquidation-zone.md
│   ├── strategy-03-loser-reverse.md
│   └── strategy-04-smart-money.md
├── src/                        # 源代码
│   ├── data/                   # 数据采集
│   ├── strategies/             # 策略实现
│   ├── backtest/               # 回测引擎
│   └── utils/                  # 工具函数
├── config/                     # 配置文件
│   └── config.example.yaml
├── tests/                      # 测试
└── notebooks/                  # Jupyter 分析
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

```bash
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入 Coinglass API Key
```

### 3. 运行回测

```bash
python -m src.backtest.run --strategy long_short_ratio --symbol BTC
```

## 📊 数据源

| 来源 | 用途 | 备注 |
|------|------|------|
| **Hyperliquid API** | 实时数据、链上持仓 | 免费 |
| **Coinglass API** | 多空比、清算数据、历史回测 | 需要 API Key |

## ⚠️ 风险提示

- 本项目仅供研究学习，不构成投资建议
- 回测结果不代表未来收益
- 实盘前请充分测试并控制仓位

## 📝 开发计划

- [ ] 多空比策略回测
- [ ] 清算密集区策略回测
- [ ] 韭菜反向策略实现
- [ ] 聪明钱跟单策略实现
- [ ] 实盘交易模块
- [ ] 风控系统

## 📄 License

MIT
