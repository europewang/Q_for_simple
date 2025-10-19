# API 参考文档

本文档详细介绍了MyQuant量化交易系统的API接口和核心类。

## 📚 目录

- [策略开发API](#策略开发api)
- [数据处理API](#数据处理api)
- [风险管理API](#风险管理api)
- [交易执行API](#交易执行api)
- [监控API](#监控api)
- [配置API](#配置api)

## 🎯 策略开发API

### BaseStrategy 基础策略类

所有策略都应继承此基类。

```python
from strategies.base_strategy import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        # 初始化策略参数
    
    def generate_signal(self, data):
        # 实现信号生成逻辑
        return Signal(...)
```

#### 方法说明

##### `__init__(self, config)`
- **参数**: `config` - 策略配置字典
- **说明**: 初始化策略，设置参数

##### `generate_signal(self, data)`
- **参数**: `data` - 市场数据DataFrame
- **返回**: `Signal` 对象或 `None`
- **说明**: 根据市场数据生成交易信号

##### `update_parameters(self, **kwargs)`
- **参数**: `**kwargs` - 要更新的参数
- **说明**: 动态更新策略参数

##### `get_strategy_info(self)`
- **返回**: 策略信息字典
- **说明**: 获取策略状态和统计信息

### Signal 信号类

```python
from strategies.base_strategy import Signal, SignalType

# 创建买入信号
signal = Signal(
    signal_type=SignalType.BUY,
    strength=0.8,
    price=50000.0,
    timestamp=datetime.now(),
    metadata={'reason': 'EMA交叉'}
)
```

#### 属性

- `signal_type`: 信号类型 (`SignalType.BUY`, `SignalType.SELL`, `SignalType.HOLD`)
- `strength`: 信号强度 (0.0-1.0)
- `price`: 信号价格
- `timestamp`: 信号时间戳
- `metadata`: 额外信息字典

### SimpleEMAStrategy 示例策略

```python
from strategies.simple_ema_strategy import SimpleEMAStrategy

# 创建EMA策略
strategy = SimpleEMAStrategy({
    'fast_ema_period': 12,
    'slow_ema_period': 26,
    'signal_threshold': 0.001
})

# 生成信号
signal = strategy.generate_signal(market_data)
```

## 📊 数据处理API

### DataFeed 数据源类

```python
from shared.data_feed import DataFeed

# 创建数据源
data_feed = DataFeed(config)

# 获取历史数据
historical_data = await data_feed.get_historical_data(
    symbol='BTCUSDT',
    interval='1m',
    limit=1000
)

# 获取实时数据
current_data = await data_feed.get_current_data('BTCUSDT')
```

#### 方法说明

##### `get_historical_data(symbol, interval, limit)`
- **参数**:
  - `symbol`: 交易对符号
  - `interval`: 时间间隔 ('1m', '5m', '1h', '1d')
  - `limit`: 数据条数
- **返回**: DataFrame格式的历史数据
- **说明**: 获取历史K线数据

##### `get_current_data(symbol)`
- **参数**: `symbol` - 交易对符号
- **返回**: 当前价格数据字典
- **说明**: 获取实时价格数据

##### `subscribe_to_updates(callback)`
- **参数**: `callback` - 回调函数
- **说明**: 订阅实时数据更新

### 数据格式

#### K线数据格式
```python
# DataFrame列名
columns = [
    'timestamp',    # 时间戳
    'open',        # 开盘价
    'high',        # 最高价
    'low',         # 最低价
    'close',       # 收盘价
    'volume'       # 成交量
]
```

#### 实时数据格式
```python
current_data = {
    'symbol': 'BTCUSDT',
    'price': 50000.0,
    'timestamp': 1640995200,
    'volume': 1000.0,
    'bid': 49999.0,
    'ask': 50001.0
}
```

## 🛡️ 风险管理API

### RiskManager 风险管理器

```python
from live_trading.risk_management.risk_manager import RiskManager

# 创建风险管理器
risk_manager = RiskManager(config)

# 验证交易信号
is_valid = risk_manager.validate_signal(signal, current_price, account_info)

# 计算仓位大小
position_size = risk_manager.calculate_position_size(
    signal, current_price, account_balance
)

# 计算止损价格
stop_loss_price = risk_manager.calculate_stop_loss_price(
    signal, entry_price
)
```

#### 方法说明

##### `validate_signal(signal, current_price, account_info)`
- **参数**:
  - `signal`: 交易信号
  - `current_price`: 当前价格
  - `account_info`: 账户信息
- **返回**: 布尔值，表示信号是否有效
- **说明**: 验证交易信号是否符合风险控制要求

##### `calculate_position_size(signal, current_price, account_balance)`
- **参数**:
  - `signal`: 交易信号
  - `current_price`: 当前价格
  - `account_balance`: 账户余额
- **返回**: 建议的仓位大小
- **说明**: 根据风险参数计算合适的仓位大小

##### `update_account_info(account_info)`
- **参数**: `account_info` - 账户信息字典
- **说明**: 更新账户信息用于风险计算

##### `check_risk_limits()`
- **返回**: 风险检查结果字典
- **说明**: 检查是否触发风险限制

### PositionManager 仓位管理器

```python
from live_trading.risk_management.position_manager import PositionManager

# 创建仓位管理器
position_manager = PositionManager(config)

# 开仓
position_id = position_manager.open_position(
    symbol='BTCUSDT',
    side='buy',
    size=0.1,
    entry_price=50000.0
)

# 平仓
position_manager.close_position(position_id, exit_price=51000.0)

# 获取持仓信息
positions = position_manager.get_open_positions()
```

#### 方法说明

##### `open_position(symbol, side, size, entry_price, **kwargs)`
- **参数**:
  - `symbol`: 交易对
  - `side`: 方向 ('buy'/'sell')
  - `size`: 仓位大小
  - `entry_price`: 入场价格
- **返回**: 仓位ID
- **说明**: 开启新仓位

##### `close_position(position_id, exit_price, **kwargs)`
- **参数**:
  - `position_id`: 仓位ID
  - `exit_price`: 出场价格
- **说明**: 关闭指定仓位

##### `get_open_positions(symbol=None)`
- **参数**: `symbol` - 可选的交易对过滤
- **返回**: 开放仓位列表
- **说明**: 获取当前开放的仓位

## ⚡ 交易执行API

### OrderExecutor 订单执行器

```python
from live_trading.execution.order_executor import OrderExecutor

# 创建订单执行器
executor = OrderExecutor(exchange_connector, config)

# 执行交易信号
result = await executor.execute_signal(signal, current_price)

# 创建订单
order_id = await executor.create_order(
    symbol='BTCUSDT',
    side='buy',
    order_type='market',
    quantity=0.1
)

# 取消订单
await executor.cancel_order(order_id)
```

#### 方法说明

##### `execute_signal(signal, current_price)`
- **参数**:
  - `signal`: 交易信号
  - `current_price`: 当前价格
- **返回**: `ExecutionResult` 对象
- **说明**: 执行交易信号

##### `create_order(symbol, side, order_type, quantity, **kwargs)`
- **参数**:
  - `symbol`: 交易对
  - `side`: 方向 ('buy'/'sell')
  - `order_type`: 订单类型 ('market'/'limit')
  - `quantity`: 数量
- **返回**: 订单ID
- **说明**: 创建新订单

##### `get_order_status(order_id)`
- **参数**: `order_id` - 订单ID
- **返回**: 订单状态字典
- **说明**: 获取订单状态

### ExchangeConnector 交易所连接器

```python
from live_trading.execution.exchange_connector import create_exchange_connector

# 创建交易所连接器
connector = create_exchange_connector('binance', config)

# 获取账户信息
account_info = await connector.get_account_info()

# 获取持仓信息
positions = await connector.get_positions()

# 创建订单
order_result = await connector.create_order(
    symbol='BTCUSDT',
    side='buy',
    order_type='market',
    quantity=0.1
)
```

## 📈 监控API

### WebMonitor Web监控

```python
from live_trading.monitoring.web_monitor import WebMonitor

# 创建Web监控
monitor = WebMonitor(port=5000)

# 更新系统状态
monitor.update_system_status({
    'status': 'running',
    'uptime': 3600,
    'cpu_usage': 25.5
})

# 更新账户信息
monitor.update_account_info({
    'balance': 10000.0,
    'equity': 10500.0,
    'margin_used': 500.0
})

# 启动监控服务
monitor.start()
```

### StatusMonitor 状态监控

```python
from live_trading.monitoring.status_monitor import StatusMonitor

# 创建状态监控
status_monitor = StatusMonitor()

# 更新性能指标
status_monitor.update_performance_metrics({
    'cpu_usage': 25.5,
    'memory_usage': 60.2,
    'network_latency': 50
})

# 添加告警规则
status_monitor.add_alert_rule(
    name='high_cpu',
    condition=lambda metrics: metrics.get('cpu_usage', 0) > 80,
    message='CPU使用率过高'
)

# 设置告警回调
status_monitor.set_alert_callback(lambda alert: print(f"告警: {alert}"))
```

## ⚙️ 配置API

### ConfigLoader 配置加载器

```python
from live_trading.config.config_loader import ConfigLoader, load_live_trading_config

# 加载配置
config = load_live_trading_config('config/live_trading_config.json')

# 创建配置加载器
loader = ConfigLoader()

# 验证配置
is_valid, errors = loader.validate_config(config_dict)

# 保存配置
loader.save_config(config, 'config/new_config.json')

# 创建默认配置
default_config = loader.create_default_config()
```

#### 配置结构

```python
# 完整配置结构
config = {
    'trading': {
        'symbol': 'BTCUSDT',
        'simulation_mode': True,
        'initial_balance': 10000.0,
        'leverage': 1
    },
    'strategy': {
        'name': 'SimpleEMAStrategy',
        'fast_ema_period': 12,
        'slow_ema_period': 26,
        'signal_threshold': 0.001
    },
    'risk_management': {
        'max_position_percentage': 0.1,
        'max_daily_loss_percentage': 0.05,
        'stop_loss_percentage': 0.02,
        'take_profit_percentage': 0.04
    },
    'execution': {
        'max_retries': 3,
        'retry_delay': 1.0,
        'order_timeout': 30
    },
    'monitoring': {
        'enable_web_interface': True,
        'web_port': 5000,
        'update_interval': 1
    }
}
```

## 🔧 工具函数

### 技术指标计算

```python
from shared.indicators import calculate_ema, calculate_rsi, calculate_macd

# 计算EMA
ema_values = calculate_ema(prices, period=20)

# 计算RSI
rsi_values = calculate_rsi(prices, period=14)

# 计算MACD
macd_line, signal_line, histogram = calculate_macd(prices)
```

### 数据验证

```python
from shared.validators import validate_signal, validate_config

# 验证信号
is_valid = validate_signal(signal)

# 验证配置
is_valid, errors = validate_config(config_dict)
```

### 日志记录

```python
from shared.logger import get_logger

# 获取日志记录器
logger = get_logger('strategy')

# 记录日志
logger.info('策略初始化完成')
logger.warning('检测到异常信号')
logger.error('订单执行失败')
```

## 📝 使用示例

### 完整策略示例

```python
import asyncio
from datetime import datetime
from strategies.base_strategy import BaseStrategy, Signal, SignalType
from shared.indicators import calculate_ema

class CustomStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.fast_period = config.get('fast_period', 12)
        self.slow_period = config.get('slow_period', 26)
        self.threshold = config.get('threshold', 0.001)
        
    def generate_signal(self, data):
        if len(data) < self.slow_period:
            return None
            
        # 计算EMA
        fast_ema = calculate_ema(data['close'], self.fast_period)
        slow_ema = calculate_ema(data['close'], self.slow_period)
        
        # 获取最新值
        current_fast = fast_ema.iloc[-1]
        current_slow = slow_ema.iloc[-1]
        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]
        
        # 检测交叉
        if prev_fast <= prev_slow and current_fast > current_slow:
            # 金叉 - 买入信号
            strength = min((current_fast - current_slow) / current_slow, 1.0)
            return Signal(
                signal_type=SignalType.BUY,
                strength=strength,
                price=data['close'].iloc[-1],
                timestamp=datetime.now(),
                metadata={
                    'fast_ema': current_fast,
                    'slow_ema': current_slow,
                    'reason': 'EMA金叉'
                }
            )
        elif prev_fast >= prev_slow and current_fast < current_slow:
            # 死叉 - 卖出信号
            strength = min((current_slow - current_fast) / current_fast, 1.0)
            return Signal(
                signal_type=SignalType.SELL,
                strength=strength,
                price=data['close'].iloc[-1],
                timestamp=datetime.now(),
                metadata={
                    'fast_ema': current_fast,
                    'slow_ema': current_slow,
                    'reason': 'EMA死叉'
                }
            )
        
        return None

# 使用策略
async def main():
    config = {
        'fast_period': 12,
        'slow_period': 26,
        'threshold': 0.001
    }
    
    strategy = CustomStrategy(config)
    
    # 假设有市场数据
    signal = strategy.generate_signal(market_data)
    
    if signal:
        print(f"生成信号: {signal.signal_type}, 强度: {signal.strength}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 完整交易系统示例

```python
import asyncio
from live_trading.main import LiveTradingSystem
from live_trading.config.config_loader import load_live_trading_config

async def run_trading_system():
    # 加载配置
    config = load_live_trading_config('config/live_trading_config.json')
    
    # 创建交易系统
    trading_system = LiveTradingSystem(config)
    
    try:
        # 启动系统
        await trading_system.start()
        
        # 运行系统
        await trading_system.run()
        
    except KeyboardInterrupt:
        print("收到停止信号...")
    finally:
        # 停止系统
        await trading_system.stop()

if __name__ == "__main__":
    asyncio.run(run_trading_system())
```

## 🚨 错误处理

### 常见异常类型

```python
from shared.exceptions import (
    TradingSystemError,
    ConfigurationError,
    DataFeedError,
    OrderExecutionError,
    RiskManagementError
)

try:
    # 交易操作
    result = await executor.execute_signal(signal, price)
except OrderExecutionError as e:
    logger.error(f"订单执行失败: {e}")
except RiskManagementError as e:
    logger.warning(f"风险控制阻止交易: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
```

### 错误恢复

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def robust_order_execution(executor, signal, price):
    """带重试机制的订单执行"""
    return await executor.execute_signal(signal, price)
```

## 📚 更多资源

- [快速开始指南](quick_start.md)
- [策略开发指南](strategy_development.md)
- [配置说明](configuration.md)
- [常见问题](faq.md)

---

**注意**: 本API文档会随着系统更新而变化，请定期查看最新版本。