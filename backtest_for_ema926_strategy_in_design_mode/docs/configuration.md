# 配置说明文档

本文档详细说明MyQuant量化交易系统的所有配置选项。

## 📋 目录

- [配置文件结构](#配置文件结构)
- [交易配置](#交易配置)
- [策略配置](#策略配置)
- [风险管理配置](#风险管理配置)
- [仓位管理配置](#仓位管理配置)
- [执行配置](#执行配置)
- [交易所配置](#交易所配置)
- [数据源配置](#数据源配置)
- [日志配置](#日志配置)
- [监控配置](#监控配置)
- [环境变量](#环境变量)
- [配置验证](#配置验证)

## 📁 配置文件结构

主配置文件位于 `live_trading/config/live_trading_config.json`，采用JSON格式：

```json
{
  "trading": { ... },
  "strategy": { ... },
  "risk_management": { ... },
  "position_management": { ... },
  "execution": { ... },
  "exchange": { ... },
  "data_feed": { ... },
  "logging": { ... },
  "monitoring": { ... }
}
```

## 💰 交易配置

### trading 部分

```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "simulation_mode": true,
    "initial_balance": 10000.0,
    "leverage": 1,
    "trading_hours": {
      "enabled": false,
      "start_time": "09:00",
      "end_time": "17:00",
      "timezone": "UTC"
    }
  }
}
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbol` | string | "BTCUSDT" | 交易对符号 |
| `simulation_mode` | boolean | true | 是否启用模拟模式 |
| `initial_balance` | number | 10000.0 | 初始余额（USDT） |
| `leverage` | number | 1 | 杠杆倍数（1-125） |
| `trading_hours.enabled` | boolean | false | 是否启用交易时间限制 |
| `trading_hours.start_time` | string | "09:00" | 交易开始时间 |
| `trading_hours.end_time` | string | "17:00" | 交易结束时间 |
| `trading_hours.timezone` | string | "UTC" | 时区设置 |

#### 支持的交易对

- **现货**: BTCUSDT, ETHUSDT, ADAUSDT, DOTUSDT 等
- **期货**: BTCUSDT, ETHUSDT (需要期货账户)

#### 杠杆设置

- **现货交易**: 固定为 1
- **期货交易**: 1-125 (根据交易所规则)

## 🎯 策略配置

### strategy 部分

```json
{
  "strategy": {
    "name": "SimpleEMAStrategy",
    "parameters": {
      "fast_ema_period": 12,
      "slow_ema_period": 26,
      "signal_threshold": 0.001,
      "min_signal_strength": 0.3
    },
    "optimization": {
      "enabled": false,
      "parameters_to_optimize": ["fast_ema_period", "slow_ema_period"],
      "optimization_period": 30
    }
  }
}
```

#### 通用参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | "SimpleEMAStrategy" | 策略名称 |
| `parameters` | object | {} | 策略特定参数 |
| `optimization.enabled` | boolean | false | 是否启用参数优化 |

#### SimpleEMAStrategy 参数

| 参数 | 类型 | 范围 | 默认值 | 说明 |
|------|------|------|--------|------|
| `fast_ema_period` | integer | 5-50 | 12 | 快速EMA周期 |
| `slow_ema_period` | integer | 20-200 | 26 | 慢速EMA周期 |
| `signal_threshold` | number | 0.0001-0.01 | 0.001 | 信号阈值 |
| `min_signal_strength` | number | 0.1-1.0 | 0.3 | 最小信号强度 |

#### 自定义策略参数

```json
{
  "strategy": {
    "name": "CustomStrategy",
    "parameters": {
      "rsi_period": 14,
      "rsi_overbought": 70,
      "rsi_oversold": 30,
      "macd_fast": 12,
      "macd_slow": 26,
      "macd_signal": 9
    }
  }
}
```

## 🛡️ 风险管理配置

### risk_management 部分

```json
{
  "risk_management": {
    "max_position_percentage": 0.1,
    "max_daily_loss_percentage": 0.05,
    "max_drawdown_percentage": 0.15,
    "stop_loss_percentage": 0.02,
    "take_profit_percentage": 0.04,
    "min_position_size": 10.0,
    "max_leverage": 3,
    "max_trades_per_day": 10,
    "cooling_period": 300,
    "risk_free_rate": 0.02,
    "var_confidence": 0.95,
    "stress_test": {
      "enabled": true,
      "scenarios": ["market_crash", "flash_crash", "high_volatility"]
    }
  }
}
```

#### 参数说明

| 参数 | 类型 | 范围 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_position_percentage` | number | 0.01-1.0 | 0.1 | 单笔交易最大仓位比例 |
| `max_daily_loss_percentage` | number | 0.01-0.5 | 0.05 | 每日最大亏损比例 |
| `max_drawdown_percentage` | number | 0.05-0.5 | 0.15 | 最大回撤比例 |
| `stop_loss_percentage` | number | 0.005-0.1 | 0.02 | 止损比例 |
| `take_profit_percentage` | number | 0.01-0.2 | 0.04 | 止盈比例 |
| `min_position_size` | number | 1.0-1000.0 | 10.0 | 最小仓位大小（USDT） |
| `max_leverage` | number | 1-10 | 3 | 最大杠杆倍数 |
| `max_trades_per_day` | integer | 1-100 | 10 | 每日最大交易次数 |
| `cooling_period` | integer | 60-3600 | 300 | 冷却期（秒） |

#### 风险指标计算

- **VaR (Value at Risk)**: 在给定置信度下的最大可能损失
- **夏普比率**: 风险调整后收益率
- **最大回撤**: 从峰值到谷值的最大跌幅
- **胜率**: 盈利交易占总交易的比例

## 📊 仓位管理配置

### position_management 部分

```json
{
  "position_management": {
    "max_open_positions": 3,
    "position_timeout": 3600,
    "auto_close_on_signal": true,
    "partial_close": {
      "enabled": true,
      "profit_threshold": 0.02,
      "close_percentage": 0.5
    },
    "trailing_stop": {
      "enabled": false,
      "trail_percentage": 0.01,
      "min_profit_threshold": 0.005
    },
    "position_sizing": {
      "method": "fixed_percentage",
      "base_percentage": 0.1,
      "kelly_criterion": false,
      "volatility_adjustment": true
    }
  }
}
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_open_positions` | integer | 3 | 最大同时持仓数量 |
| `position_timeout` | integer | 3600 | 仓位超时时间（秒） |
| `auto_close_on_signal` | boolean | true | 收到反向信号时自动平仓 |
| `partial_close.enabled` | boolean | true | 是否启用部分平仓 |
| `trailing_stop.enabled` | boolean | false | 是否启用移动止损 |

#### 仓位大小计算方法

1. **固定比例** (`fixed_percentage`): 固定使用账户余额的一定比例
2. **凯利公式** (`kelly_criterion`): 根据历史胜率和盈亏比计算
3. **波动率调整** (`volatility_adjustment`): 根据市场波动率调整仓位

## ⚡ 执行配置

### execution 部分

```json
{
  "execution": {
    "max_retries": 3,
    "retry_delay": 1.0,
    "order_timeout": 30,
    "slippage_tolerance": 0.001,
    "execution_delay": 0.1,
    "order_type": "market",
    "price_improvement": {
      "enabled": true,
      "max_wait_time": 5,
      "price_threshold": 0.0005
    },
    "smart_routing": {
      "enabled": false,
      "exchanges": ["binance", "okx", "bybit"]
    }
  }
}
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_retries` | integer | 3 | 最大重试次数 |
| `retry_delay` | number | 1.0 | 重试延迟（秒） |
| `order_timeout` | integer | 30 | 订单超时时间（秒） |
| `slippage_tolerance` | number | 0.001 | 滑点容忍度 |
| `execution_delay` | number | 0.1 | 执行延迟（秒） |
| `order_type` | string | "market" | 订单类型 |

#### 订单类型

- **market**: 市价单，立即执行
- **limit**: 限价单，指定价格执行
- **stop**: 止损单
- **stop_limit**: 止损限价单

## 🏦 交易所配置

### exchange 部分

```json
{
  "exchange": {
    "name": "binance",
    "api_key": "",
    "api_secret": "",
    "testnet": true,
    "sandbox": false,
    "rate_limit": {
      "requests_per_minute": 1200,
      "orders_per_second": 10
    },
    "fees": {
      "maker": 0.001,
      "taker": 0.001
    },
    "connection": {
      "timeout": 10,
      "max_connections": 10,
      "retry_on_failure": true
    }
  }
}
```

#### 支持的交易所

| 交易所 | 名称 | 现货 | 期货 | 测试网 |
|--------|------|------|------|--------|
| Binance | "binance" | ✅ | ✅ | ✅ |
| OKX | "okx" | ✅ | ✅ | ✅ |
| Bybit | "bybit" | ✅ | ✅ | ✅ |
| Mock | "mock" | ✅ | ✅ | ✅ |

#### API密钥配置

**安全建议**:
1. 使用环境变量存储API密钥
2. 启用IP白名单
3. 限制API权限
4. 定期更换密钥

```bash
# .env 文件
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

## 📡 数据源配置

### data_feed 部分

```json
{
  "data_feed": {
    "source": "binance",
    "update_interval": 1,
    "websocket_url": "wss://stream.binance.com:9443/ws/",
    "rest_api_url": "https://api.binance.com",
    "backup_sources": ["okx", "bybit"],
    "data_validation": {
      "enabled": true,
      "max_price_change": 0.1,
      "min_volume": 1000
    },
    "caching": {
      "enabled": true,
      "cache_size": 10000,
      "cache_ttl": 300
    },
    "mock_data": {
      "enabled": false,
      "volatility": 0.02,
      "trend": 0.0001,
      "base_price": 50000
    }
  }
}
```

#### 数据源类型

1. **实时数据源**:
   - `binance`: Binance WebSocket
   - `okx`: OKX WebSocket
   - `bybit`: Bybit WebSocket

2. **模拟数据源**:
   - `mock`: 模拟价格数据
   - `historical`: 历史数据回放

#### 数据验证规则

- **价格变化检查**: 防止异常价格跳跃
- **成交量检查**: 确保数据质量
- **时间戳检查**: 防止延迟数据

## 📝 日志配置

### logging 部分

```json
{
  "logging": {
    "level": "INFO",
    "enable_file_logging": true,
    "log_directory": "logs",
    "max_file_size": 10485760,
    "backup_count": 5,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "modules": {
      "strategy": "DEBUG",
      "execution": "INFO",
      "risk_management": "WARNING",
      "data_feed": "ERROR"
    },
    "performance_logging": {
      "enabled": true,
      "log_trades": true,
      "log_signals": true,
      "log_performance_metrics": true
    }
  }
}
```

#### 日志级别

| 级别 | 数值 | 说明 |
|------|------|------|
| DEBUG | 10 | 详细调试信息 |
| INFO | 20 | 一般信息 |
| WARNING | 30 | 警告信息 |
| ERROR | 40 | 错误信息 |
| CRITICAL | 50 | 严重错误 |

#### 日志文件管理

- **自动轮转**: 文件大小超过限制时自动创建新文件
- **压缩存储**: 旧日志文件自动压缩
- **定期清理**: 自动删除过期日志文件

## 📊 监控配置

### monitoring 部分

```json
{
  "monitoring": {
    "enable_web_interface": true,
    "web_port": 5000,
    "web_host": "0.0.0.0",
    "update_interval": 1,
    "save_state_interval": 60,
    "alerts": {
      "enabled": true,
      "email_notifications": false,
      "webhook_url": "",
      "alert_rules": [
        {
          "name": "high_drawdown",
          "condition": "drawdown > 0.1",
          "cooldown": 3600
        }
      ]
    },
    "metrics": {
      "track_performance": true,
      "track_system_resources": true,
      "track_network_latency": true,
      "export_prometheus": false
    }
  }
}
```

#### Web界面功能

- **实时监控**: 系统状态、账户信息、持仓情况
- **图表展示**: 价格走势、PnL曲线、信号历史
- **告警管理**: 实时告警显示和历史记录
- **性能分析**: 交易统计、风险指标

#### 告警规则

```json
{
  "alert_rules": [
    {
      "name": "high_cpu_usage",
      "condition": "cpu_usage > 80",
      "message": "CPU使用率过高: {cpu_usage}%",
      "cooldown": 300
    },
    {
      "name": "large_loss",
      "condition": "daily_pnl < -500",
      "message": "当日亏损过大: {daily_pnl} USDT",
      "cooldown": 3600
    }
  ]
}
```

## 🌍 环境变量

### .env 文件配置

```bash
# 交易所API密钥
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
BINANCE_TESTNET=true

OKX_API_KEY=your_okx_api_key
OKX_API_SECRET=your_okx_api_secret
OKX_PASSPHRASE=your_okx_passphrase

# 数据库配置
DATABASE_URL=sqlite:///trading.db
REDIS_URL=redis://localhost:6379

# 监控配置
WEBHOOK_URL=https://hooks.slack.com/services/...
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# 代理配置
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=https://proxy:port

# 调试配置
DEBUG_MODE=false
LOG_LEVEL=INFO
```

### 环境变量优先级

1. 系统环境变量
2. .env 文件
3. 配置文件默认值

## ✅ 配置验证

### 自动验证

系统启动时会自动验证配置：

```python
from live_trading.config.config_loader import load_live_trading_config

# 加载并验证配置
config = load_live_trading_config('config/live_trading_config.json')
```

### 手动验证

```bash
# 检查配置文件
python start_trading.py --check-config

# 验证特定配置
python -c "
from live_trading.config.config_loader import ConfigLoader
loader = ConfigLoader()
is_valid, errors = loader.validate_config_file('config/live_trading_config.json')
print(f'配置有效: {is_valid}')
if errors:
    for error in errors:
        print(f'错误: {error}')
"
```

### 常见配置错误

1. **API密钥格式错误**
   ```
   错误: API密钥长度不正确
   解决: 检查API密钥是否完整复制
   ```

2. **数值范围错误**
   ```
   错误: max_position_percentage 必须在 0.01-1.0 之间
   解决: 调整参数值到有效范围
   ```

3. **依赖关系错误**
   ```
   错误: slow_ema_period 必须大于 fast_ema_period
   解决: 确保慢速EMA周期大于快速EMA周期
   ```

## 🔧 配置模板

### 保守型配置

```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "simulation_mode": true,
    "initial_balance": 10000.0,
    "leverage": 1
  },
  "risk_management": {
    "max_position_percentage": 0.05,
    "max_daily_loss_percentage": 0.02,
    "stop_loss_percentage": 0.015,
    "take_profit_percentage": 0.03
  },
  "strategy": {
    "name": "SimpleEMAStrategy",
    "parameters": {
      "fast_ema_period": 20,
      "slow_ema_period": 50,
      "signal_threshold": 0.002
    }
  }
}
```

### 激进型配置

```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "simulation_mode": true,
    "initial_balance": 10000.0,
    "leverage": 3
  },
  "risk_management": {
    "max_position_percentage": 0.2,
    "max_daily_loss_percentage": 0.1,
    "stop_loss_percentage": 0.03,
    "take_profit_percentage": 0.06
  },
  "strategy": {
    "name": "SimpleEMAStrategy",
    "parameters": {
      "fast_ema_period": 8,
      "slow_ema_period": 21,
      "signal_threshold": 0.0005
    }
  }
}
```

### 测试配置

```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "simulation_mode": true,
    "initial_balance": 1000.0,
    "leverage": 1
  },
  "data_feed": {
    "source": "mock",
    "mock_data": {
      "enabled": true,
      "volatility": 0.05,
      "trend": 0.001
    }
  },
  "monitoring": {
    "enable_web_interface": true,
    "update_interval": 0.5
  }
}
```

## 📚 相关文档

- [快速开始指南](quick_start.md)
- [API参考文档](api_reference.md)
- [策略开发指南](strategy_development.md)
- [常见问题](faq.md)

---

**注意**: 配置参数会影响系统性能和风险水平，请根据实际情况谨慎调整。