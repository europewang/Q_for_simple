# 实时量化交易系统 (Live Trading System)

## 📋 项目概述

这是一个完整的实时量化交易系统，支持多种交易策略、风险管理、实时数据处理和自动化交易执行。系统采用模块化设计，支持模拟交易和实盘交易。

## 🚀 主要功能

### 核心功能
- ✅ **实时数据处理**: 支持多种数据源（Binance、模拟数据等）
- ✅ **策略引擎**: 内置EMA策略，支持自定义策略扩展
- ✅ **风险管理**: 完整的风险控制和仓位管理
- ✅ **订单执行**: 自动化订单执行和管理
- ✅ **日志系统**: 详细的日志记录和监控
- ✅ **配置管理**: 灵活的配置系统

### 交易功能
- 支持现货和期货交易
- 多种订单类型（市价单、限价单等）
- 止损止盈功能
- 仓位管理和风险控制
- 实时PnL计算

## 🏗️ 系统架构

```
live_trading/
├── config/                 # 配置文件
├── data/                   # 数据模块
├── execution/              # 交易执行模块
├── risk_management/        # 风险管理模块
├── strategies/             # 交易策略模块
├── shared/                 # 共享模块
├── logs/                   # 日志文件
└── start_trading.py        # 主启动文件
```

## 📦 安装和配置

### 环境要求
- Python 3.7+
- 依赖包：aiohttp, websockets, pandas, numpy等

### 安装步骤
1. 创建Python虚拟环境：
```bash
conda create -n myquant python=3.7
conda activate myquant
```

2. 安装依赖包：
```bash
pip install aiohttp websockets pandas numpy python-dateutil
```

3. 配置交易参数：
编辑 `config/live_trading_config.json` 文件

## 🎯 快速开始

### 1. 配置验证
```bash
python start_trading.py --check-config
```

### 2. 演示模式（推荐新手）
```bash
python start_trading.py --mode demo
```

### 3. 实盘交易（需要API密钥）
```bash
python start_trading.py --mode live
```

## ⚙️ 配置说明

### 主要配置项
```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "initial_balance": 10000.0,
    "max_position_ratio": 0.95,
    "stop_loss_ratio": 0.02,
    "take_profit_ratio": 0.06
  },
  "strategy": {
    "name": "SimpleEMAStrategy",
    "fast_ema": 12,
    "slow_ema": 26
  },
  "data_source": {
    "source": "mock",
    "update_interval": 1
  },
  "exchange": {
    "name": "mock",
    "api_key": "",
    "api_secret": ""
  }
}
```

## 📊 策略说明

### 内置策略

#### SimpleEMA策略
- **原理**: 基于快慢EMA均线交叉
- **买入信号**: 快线上穿慢线
- **卖出信号**: 快线下穿慢线
- **参数**: 
  - `fast_ema`: 快速EMA周期（默认12）
  - `slow_ema`: 慢速EMA周期（默认26）

### 自定义策略
可以继承 `BaseStrategy` 类来实现自定义策略：

```python
from strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, symbol: str, config: Dict[str, Any]):
        super().__init__(symbol, config)
    
    def generate_signal(self, market_data: MarketData) -> TradingSignal:
        # 实现你的策略逻辑
        pass
```

## 🛡️ 风险管理

### 风险控制功能
- **仓位限制**: 最大仓位比例控制
- **止损止盈**: 自动止损止盈
- **资金管理**: 可用资金检查
- **风险监控**: 实时风险指标监控

### 风险参数
- `max_position_ratio`: 最大仓位比例（0-1）
- `stop_loss_ratio`: 止损比例
- `take_profit_ratio`: 止盈比例
- `max_daily_loss`: 最大日损失限制

## 📈 监控和日志

### 日志系统
- **位置**: `logs/` 目录
- **级别**: DEBUG, INFO, WARNING, ERROR
- **格式**: 时间戳 + 模块名 + 级别 + 消息

### 监控指标
- 实时PnL
- 仓位状态
- 订单执行情况
- 风险指标
- 系统性能

## 🔧 故障排除

### 常见问题

1. **配置文件错误**
   - 检查JSON格式是否正确
   - 验证所有必需字段是否存在

2. **网络连接问题**
   - 检查网络连接
   - 验证API密钥和权限

3. **策略执行异常**
   - 查看日志文件
   - 检查策略参数配置

### 调试模式
```bash
python start_trading.py --mode demo --debug
```

## 📝 更新日志

### v1.0.0 (2024-10-12)
- ✅ 修复setup_logging函数参数不匹配问题
- ✅ 修复create_market_data_feed函数source参数问题
- ✅ 修复LiveSimpleEMAStrategy初始化缺少symbol参数问题
- ✅ 为MarketDataFeed基类添加set_callback方法
- ✅ 修复异步回调函数_on_market_data的调用问题
- ✅ 修复data_feed.start()和stop()方法的异步调用问题
- ✅ 修复AccountInfo实例化缺少必需参数问题
- ✅ 系统现已稳定运行，支持demo和live模式

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持

如有问题或建议，请：
1. 查看文档和FAQ
2. 检查日志文件
3. 提交Issue
4. 联系开发团队

---

**⚠️ 风险提示**: 量化交易存在风险，请在充分了解和测试后再进行实盘交易。建议先使用demo模式熟悉系统。