# 策略开发指南

本指南将帮助您在MyQuant系统中开发自定义量化交易策略。

## 📋 目录

- [策略基础概念](#策略基础概念)
- [策略开发框架](#策略开发框架)
- [创建第一个策略](#创建第一个策略)
- [技术指标使用](#技术指标使用)
- [信号生成机制](#信号生成机制)
- [策略参数优化](#策略参数优化)
- [回测与验证](#回测与验证)
- [风险控制集成](#风险控制集成)
- [性能优化](#性能优化)
- [策略示例](#策略示例)

## 🎯 策略基础概念

### 什么是量化交易策略？

量化交易策略是基于数学模型和统计分析的自动化交易规则，通过程序化方式执行买卖决策。

### 策略的核心要素

1. **信号生成**: 基于市场数据产生买卖信号
2. **风险控制**: 管理交易风险和资金安全
3. **仓位管理**: 决定交易数量和时机
4. **执行逻辑**: 将信号转化为实际交易

### 策略分类

- **趋势跟踪策略**: 跟随市场趋势方向
- **均值回归策略**: 利用价格回归均值的特性
- **套利策略**: 利用价格差异获利
- **高频策略**: 基于微观结构的短期交易

## 🏗️ 策略开发框架

### BaseStrategy 基类

所有策略都必须继承 `BaseStrategy` 基类：

```python
from strategies.base_strategy import BaseStrategy, Signal, SignalType
from datetime import datetime
import pandas as pd

class MyCustomStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        # 初始化策略参数
        self.setup_parameters(config)
        
    def setup_parameters(self, config):
        """设置策略参数"""
        self.param1 = config.get('param1', default_value)
        self.param2 = config.get('param2', default_value)
        
    def generate_signal(self, data):
        """生成交易信号"""
        # 实现信号生成逻辑
        return signal_or_none
        
    def update_parameters(self, **kwargs):
        """动态更新参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
```

### 必须实现的方法

#### `__init__(self, config)`
- **目的**: 初始化策略实例
- **参数**: `config` - 策略配置字典
- **实现**: 设置策略参数和状态变量

#### `generate_signal(self, data)`
- **目的**: 根据市场数据生成交易信号
- **参数**: `data` - 包含OHLCV数据的DataFrame
- **返回**: `Signal` 对象或 `None`
- **实现**: 核心策略逻辑

### 可选实现的方法

#### `update_parameters(self, **kwargs)`
- **目的**: 动态更新策略参数
- **用途**: 参数优化、实时调整

#### `get_strategy_info(self)`
- **目的**: 返回策略状态信息
- **返回**: 包含策略统计的字典

## 🚀 创建第一个策略

### 步骤1: 创建策略文件

在 `strategies/` 目录下创建新的策略文件：

```python
# strategies/my_rsi_strategy.py

from strategies.base_strategy import BaseStrategy, Signal, SignalType
from shared.indicators import calculate_rsi
from datetime import datetime
import pandas as pd

class RSIStrategy(BaseStrategy):
    """基于RSI指标的交易策略"""
    
    def __init__(self, config):
        super().__init__(config)
        self.setup_parameters(config)
        
    def setup_parameters(self, config):
        """设置RSI策略参数"""
        self.rsi_period = config.get('rsi_period', 14)
        self.overbought_level = config.get('overbought_level', 70)
        self.oversold_level = config.get('oversold_level', 30)
        self.min_signal_strength = config.get('min_signal_strength', 0.5)
        
    def generate_signal(self, data):
        """生成RSI交易信号"""
        # 检查数据长度
        if len(data) < self.rsi_period + 1:
            return None
            
        # 计算RSI指标
        rsi_values = calculate_rsi(data['close'], self.rsi_period)
        current_rsi = rsi_values.iloc[-1]
        prev_rsi = rsi_values.iloc[-2]
        
        current_price = data['close'].iloc[-1]
        
        # 生成买入信号（RSI从超卖区域向上突破）
        if (prev_rsi <= self.oversold_level and 
            current_rsi > self.oversold_level):
            
            # 计算信号强度
            strength = min((self.oversold_level - prev_rsi) / 10, 1.0)
            
            if strength >= self.min_signal_strength:
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=strength,
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={
                        'rsi': current_rsi,
                        'prev_rsi': prev_rsi,
                        'reason': 'RSI超卖反弹'
                    }
                )
        
        # 生成卖出信号（RSI从超买区域向下突破）
        elif (prev_rsi >= self.overbought_level and 
              current_rsi < self.overbought_level):
            
            # 计算信号强度
            strength = min((prev_rsi - self.overbought_level) / 10, 1.0)
            
            if strength >= self.min_signal_strength:
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=strength,
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={
                        'rsi': current_rsi,
                        'prev_rsi': prev_rsi,
                        'reason': 'RSI超买回调'
                    }
                )
        
        return None
        
    def get_strategy_info(self):
        """返回策略信息"""
        return {
            'name': 'RSI Strategy',
            'type': 'Mean Reversion',
            'parameters': {
                'rsi_period': self.rsi_period,
                'overbought_level': self.overbought_level,
                'oversold_level': self.oversold_level
            },
            'description': '基于RSI指标的均值回归策略'
        }
```

### 步骤2: 配置策略参数

在配置文件中添加策略配置：

```json
{
  "strategy": {
    "name": "RSIStrategy",
    "parameters": {
      "rsi_period": 14,
      "overbought_level": 70,
      "oversold_level": 30,
      "min_signal_strength": 0.5
    }
  }
}
```

### 步骤3: 注册策略

在 `strategies/__init__.py` 中注册新策略：

```python
from .my_rsi_strategy import RSIStrategy

STRATEGY_REGISTRY = {
    'SimpleEMAStrategy': SimpleEMAStrategy,
    'RSIStrategy': RSIStrategy,  # 添加新策略
}

def get_strategy_class(strategy_name):
    return STRATEGY_REGISTRY.get(strategy_name)
```

## 📊 技术指标使用

### 内置指标

系统提供了常用的技术指标：

```python
from shared.indicators import (
    calculate_ema,
    calculate_sma,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_stochastic,
    calculate_atr
)

# 使用示例
def generate_signal(self, data):
    # 移动平均线
    ema_20 = calculate_ema(data['close'], 20)
    sma_50 = calculate_sma(data['close'], 50)
    
    # RSI指标
    rsi = calculate_rsi(data['close'], 14)
    
    # MACD指标
    macd_line, signal_line, histogram = calculate_macd(data['close'])
    
    # 布林带
    upper_band, middle_band, lower_band = calculate_bollinger_bands(
        data['close'], 20, 2
    )
    
    # 随机指标
    k_percent, d_percent = calculate_stochastic(
        data['high'], data['low'], data['close'], 14
    )
    
    # 平均真实波幅
    atr = calculate_atr(data['high'], data['low'], data['close'], 14)
```

### 自定义指标

您也可以创建自定义技术指标：

```python
def calculate_custom_indicator(data, period=20):
    """自定义指标示例"""
    # 计算价格动量
    momentum = data['close'].pct_change(period)
    
    # 计算波动率
    volatility = data['close'].rolling(period).std()
    
    # 组合指标
    custom_indicator = momentum / volatility
    
    return custom_indicator

# 在策略中使用
def generate_signal(self, data):
    custom_values = calculate_custom_indicator(data, self.period)
    current_value = custom_values.iloc[-1]
    
    if current_value > self.threshold:
        return Signal(...)
```

### 多时间框架分析

```python
class MultiTimeframeStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.short_period = config.get('short_period', 5)
        self.long_period = config.get('long_period', 20)
        
    def generate_signal(self, data):
        # 短期趋势
        short_ema = calculate_ema(data['close'], self.short_period)
        
        # 长期趋势
        long_ema = calculate_ema(data['close'], self.long_period)
        
        # 趋势方向确认
        short_trend = short_ema.iloc[-1] > short_ema.iloc[-2]
        long_trend = long_ema.iloc[-1] > long_ema.iloc[-2]
        
        # 多时间框架确认
        if short_trend and long_trend:
            return Signal(SignalType.BUY, ...)
        elif not short_trend and not long_trend:
            return Signal(SignalType.SELL, ...)
            
        return None
```

## 🎯 信号生成机制

### Signal 类详解

```python
from strategies.base_strategy import Signal, SignalType

# 创建买入信号
buy_signal = Signal(
    signal_type=SignalType.BUY,      # 信号类型
    strength=0.8,                    # 信号强度 (0.0-1.0)
    price=50000.0,                   # 信号价格
    timestamp=datetime.now(),        # 信号时间
    metadata={                       # 额外信息
        'indicator_value': 75.5,
        'reason': '技术指标突破',
        'confidence': 0.85
    }
)
```

### 信号类型

```python
class SignalType(Enum):
    BUY = "buy"          # 买入信号
    SELL = "sell"        # 卖出信号
    HOLD = "hold"        # 持有信号
```

### 信号强度计算

信号强度应该反映信号的可靠性：

```python
def calculate_signal_strength(self, indicator_values):
    """计算信号强度"""
    # 方法1: 基于指标偏离程度
    deviation = abs(indicator_values['current'] - indicator_values['threshold'])
    max_deviation = indicator_values['max_range']
    strength = min(deviation / max_deviation, 1.0)
    
    # 方法2: 基于多个指标确认
    confirmations = 0
    total_indicators = len(self.indicators)
    
    for indicator in self.indicators:
        if indicator.confirm_signal():
            confirmations += 1
    
    strength = confirmations / total_indicators
    
    # 方法3: 基于历史成功率
    historical_success_rate = self.get_historical_success_rate()
    strength = historical_success_rate
    
    return strength
```

### 信号过滤

实现信号过滤机制以提高信号质量：

```python
def filter_signal(self, signal, data):
    """信号过滤器"""
    if signal is None:
        return None
    
    # 过滤器1: 最小强度要求
    if signal.strength < self.min_signal_strength:
        return None
    
    # 过滤器2: 市场状态检查
    if not self.is_market_suitable(data):
        return None
    
    # 过滤器3: 时间过滤
    if not self.is_trading_time():
        return None
    
    # 过滤器4: 波动率过滤
    volatility = self.calculate_volatility(data)
    if volatility > self.max_volatility:
        return None
    
    return signal

def is_market_suitable(self, data):
    """检查市场状态是否适合交易"""
    # 检查成交量
    avg_volume = data['volume'].rolling(20).mean().iloc[-1]
    current_volume = data['volume'].iloc[-1]
    
    if current_volume < avg_volume * 0.5:
        return False  # 成交量过低
    
    # 检查价格波动
    price_change = abs(data['close'].pct_change().iloc[-1])
    if price_change > 0.05:
        return False  # 价格波动过大
    
    return True
```

## 🔧 策略参数优化

### 参数网格搜索

```python
import itertools
from backtest.backtest_engine import BacktestEngine

class StrategyOptimizer:
    def __init__(self, strategy_class, data):
        self.strategy_class = strategy_class
        self.data = data
        
    def grid_search(self, param_grid):
        """网格搜索最优参数"""
        best_params = None
        best_performance = -float('inf')
        
        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        for combination in itertools.product(*param_values):
            params = dict(zip(param_names, combination))
            
            # 运行回测
            performance = self.evaluate_parameters(params)
            
            if performance > best_performance:
                best_performance = performance
                best_params = params
        
        return best_params, best_performance
    
    def evaluate_parameters(self, params):
        """评估参数组合"""
        strategy = self.strategy_class(params)
        engine = BacktestEngine(strategy, self.data)
        results = engine.run()
        
        # 返回评估指标（如夏普比率）
        return results['sharpe_ratio']

# 使用示例
optimizer = StrategyOptimizer(RSIStrategy, historical_data)

param_grid = {
    'rsi_period': [10, 14, 20],
    'overbought_level': [70, 75, 80],
    'oversold_level': [20, 25, 30]
}

best_params, best_score = optimizer.grid_search(param_grid)
print(f"最优参数: {best_params}")
print(f"最优得分: {best_score}")
```

### 贝叶斯优化

```python
from skopt import gp_minimize
from skopt.space import Real, Integer

def bayesian_optimization(self, n_calls=50):
    """贝叶斯优化"""
    
    # 定义参数空间
    space = [
        Integer(10, 30, name='rsi_period'),
        Real(65, 85, name='overbought_level'),
        Real(15, 35, name='oversold_level')
    ]
    
    def objective(params):
        """目标函数"""
        config = {
            'rsi_period': params[0],
            'overbought_level': params[1],
            'oversold_level': params[2]
        }
        
        performance = self.evaluate_parameters(config)
        return -performance  # 最小化负收益
    
    # 执行优化
    result = gp_minimize(objective, space, n_calls=n_calls)
    
    return result.x, -result.fun
```

### 动态参数调整

```python
class AdaptiveStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.performance_window = 100
        self.adjustment_threshold = 0.1
        
    def update_parameters_based_on_performance(self):
        """基于性能动态调整参数"""
        recent_performance = self.get_recent_performance()
        
        if recent_performance < self.adjustment_threshold:
            # 性能不佳，调整参数
            self.adjust_parameters()
    
    def adjust_parameters(self):
        """调整策略参数"""
        # 增加信号阈值以提高信号质量
        self.signal_threshold *= 1.1
        
        # 调整止损水平
        self.stop_loss_percentage *= 0.9
        
        # 记录调整
        self.log_parameter_adjustment()
```

## 📈 回测与验证

### 策略回测

```python
from backtest.backtest_engine import BacktestEngine
from backtest.performance_analyzer import PerformanceAnalyzer

def backtest_strategy(strategy_class, config, data):
    """回测策略"""
    # 创建策略实例
    strategy = strategy_class(config)
    
    # 创建回测引擎
    engine = BacktestEngine(
        strategy=strategy,
        data=data,
        initial_balance=10000,
        commission=0.001
    )
    
    # 运行回测
    results = engine.run()
    
    # 分析性能
    analyzer = PerformanceAnalyzer(results)
    performance_metrics = analyzer.calculate_metrics()
    
    return results, performance_metrics

# 使用示例
results, metrics = backtest_strategy(
    RSIStrategy,
    {'rsi_period': 14, 'overbought_level': 70, 'oversold_level': 30},
    historical_data
)

print(f"总收益率: {metrics['total_return']:.2%}")
print(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
print(f"最大回撤: {metrics['max_drawdown']:.2%}")
```

### 交叉验证

```python
def cross_validate_strategy(strategy_class, config, data, n_folds=5):
    """交叉验证策略"""
    fold_size = len(data) // n_folds
    performances = []
    
    for i in range(n_folds):
        # 分割数据
        start_idx = i * fold_size
        end_idx = (i + 1) * fold_size
        
        train_data = pd.concat([
            data[:start_idx],
            data[end_idx:]
        ])
        test_data = data[start_idx:end_idx]
        
        # 在训练集上优化参数（可选）
        # optimized_config = optimize_on_train_data(train_data)
        
        # 在测试集上评估
        results, metrics = backtest_strategy(strategy_class, config, test_data)
        performances.append(metrics['sharpe_ratio'])
    
    return {
        'mean_performance': np.mean(performances),
        'std_performance': np.std(performances),
        'all_performances': performances
    }
```

### 样本外测试

```python
def out_of_sample_test(strategy_class, config, data, split_ratio=0.7):
    """样本外测试"""
    split_point = int(len(data) * split_ratio)
    
    # 分割数据
    in_sample_data = data[:split_point]
    out_of_sample_data = data[split_point:]
    
    # 样本内回测
    in_sample_results, in_sample_metrics = backtest_strategy(
        strategy_class, config, in_sample_data
    )
    
    # 样本外回测
    out_of_sample_results, out_of_sample_metrics = backtest_strategy(
        strategy_class, config, out_of_sample_data
    )
    
    return {
        'in_sample': in_sample_metrics,
        'out_of_sample': out_of_sample_metrics,
        'performance_decay': (
            in_sample_metrics['sharpe_ratio'] - 
            out_of_sample_metrics['sharpe_ratio']
        )
    }
```

## 🛡️ 风险控制集成

### 策略级风险控制

```python
class RiskAwareStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.max_position_size = config.get('max_position_size', 0.1)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.max_daily_trades = config.get('max_daily_trades', 5)
        self.daily_trade_count = 0
        
    def generate_signal(self, data):
        # 检查日交易次数限制
        if self.daily_trade_count >= self.max_daily_trades:
            return None
        
        # 生成基础信号
        base_signal = self.generate_base_signal(data)
        
        if base_signal is None:
            return None
        
        # 应用风险控制
        risk_adjusted_signal = self.apply_risk_controls(base_signal, data)
        
        return risk_adjusted_signal
    
    def apply_risk_controls(self, signal, data):
        """应用风险控制"""
        # 调整仓位大小
        current_volatility = self.calculate_volatility(data)
        volatility_adjustment = min(1.0, 0.02 / current_volatility)
        
        adjusted_strength = signal.strength * volatility_adjustment
        
        # 更新信号
        signal.strength = adjusted_strength
        signal.metadata['volatility_adjustment'] = volatility_adjustment
        signal.metadata['stop_loss_price'] = self.calculate_stop_loss(signal)
        
        return signal
    
    def calculate_stop_loss(self, signal):
        """计算止损价格"""
        if signal.signal_type == SignalType.BUY:
            return signal.price * (1 - self.stop_loss_pct)
        else:
            return signal.price * (1 + self.stop_loss_pct)
```

### 组合风险管理

```python
class PortfolioRiskManager:
    def __init__(self, strategies, risk_config):
        self.strategies = strategies
        self.risk_config = risk_config
        self.position_correlations = {}
        
    def validate_portfolio_signal(self, new_signal, current_positions):
        """验证组合信号"""
        # 检查相关性风险
        if self.check_correlation_risk(new_signal, current_positions):
            return False
        
        # 检查集中度风险
        if self.check_concentration_risk(new_signal, current_positions):
            return False
        
        # 检查总风险敞口
        if self.check_total_exposure(new_signal, current_positions):
            return False
        
        return True
    
    def check_correlation_risk(self, signal, positions):
        """检查相关性风险"""
        for position in positions:
            correlation = self.get_correlation(signal.symbol, position.symbol)
            if correlation > self.risk_config['max_correlation']:
                return True
        return False
```

## ⚡ 性能优化

### 数据处理优化

```python
import numpy as np
from numba import jit

class OptimizedStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        # 预编译计算函数
        self.fast_ema = self.compile_ema_function()
        
    @staticmethod
    @jit(nopython=True)
    def fast_ema_calculation(prices, period):
        """使用Numba加速的EMA计算"""
        alpha = 2.0 / (period + 1)
        ema = np.empty_like(prices)
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def generate_signal(self, data):
        # 使用优化的计算函数
        prices = data['close'].values
        fast_ema = self.fast_ema_calculation(prices, self.fast_period)
        slow_ema = self.fast_ema_calculation(prices, self.slow_period)
        
        # 其余逻辑...
```

### 内存管理

```python
class MemoryEfficientStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.max_data_length = config.get('max_data_length', 1000)
        
    def generate_signal(self, data):
        # 限制数据长度以节省内存
        if len(data) > self.max_data_length:
            data = data.tail(self.max_data_length)
        
        # 使用视图而不是复制
        close_prices = data['close'].values  # 避免DataFrame开销
        
        # 及时清理不需要的变量
        del data  # 如果不再需要
        
        return self.compute_signal(close_prices)
```

### 并行处理

```python
import concurrent.futures
from multiprocessing import Pool

class ParallelStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.n_workers = config.get('n_workers', 4)
        
    def generate_signals_batch(self, data_list):
        """批量生成信号"""
        with Pool(self.n_workers) as pool:
            signals = pool.map(self.generate_signal, data_list)
        return signals
    
    def parallel_indicator_calculation(self, data):
        """并行计算多个指标"""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # 提交计算任务
            ema_future = executor.submit(calculate_ema, data['close'], 20)
            rsi_future = executor.submit(calculate_rsi, data['close'], 14)
            macd_future = executor.submit(calculate_macd, data['close'])
            
            # 获取结果
            ema = ema_future.result()
            rsi = rsi_future.result()
            macd = macd_future.result()
            
        return ema, rsi, macd
```

## 📚 策略示例

### 1. 双均线策略

```python
class DualMovingAverageStrategy(BaseStrategy):
    """双均线交叉策略"""
    
    def __init__(self, config):
        super().__init__(config)
        self.fast_period = config.get('fast_period', 10)
        self.slow_period = config.get('slow_period', 30)
        self.signal_threshold = config.get('signal_threshold', 0.001)
        
    def generate_signal(self, data):
        if len(data) < self.slow_period + 1:
            return None
            
        # 计算移动平均线
        fast_ma = calculate_ema(data['close'], self.fast_period)
        slow_ma = calculate_ema(data['close'], self.slow_period)
        
        # 获取当前和前一个值
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        current_price = data['close'].iloc[-1]
        
        # 检测金叉
        if prev_fast <= prev_slow and current_fast > current_slow:
            spread = (current_fast - current_slow) / current_slow
            if spread > self.signal_threshold:
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=min(spread * 10, 1.0),
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={'fast_ma': current_fast, 'slow_ma': current_slow}
                )
        
        # 检测死叉
        elif prev_fast >= prev_slow and current_fast < current_slow:
            spread = (current_slow - current_fast) / current_fast
            if spread > self.signal_threshold:
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=min(spread * 10, 1.0),
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={'fast_ma': current_fast, 'slow_ma': current_slow}
                )
        
        return None
```

### 2. 布林带策略

```python
class BollingerBandsStrategy(BaseStrategy):
    """布林带均值回归策略"""
    
    def __init__(self, config):
        super().__init__(config)
        self.period = config.get('period', 20)
        self.std_dev = config.get('std_dev', 2)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_threshold = config.get('rsi_threshold', 30)
        
    def generate_signal(self, data):
        if len(data) < max(self.period, self.rsi_period) + 1:
            return None
            
        # 计算布林带
        upper_band, middle_band, lower_band = calculate_bollinger_bands(
            data['close'], self.period, self.std_dev
        )
        
        # 计算RSI确认
        rsi = calculate_rsi(data['close'], self.rsi_period)
        
        current_price = data['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        
        # 价格触及下轨且RSI超卖
        if (current_price <= lower_band.iloc[-1] and 
            current_rsi <= self.rsi_threshold):
            
            distance_to_middle = (middle_band.iloc[-1] - current_price) / current_price
            strength = min(distance_to_middle * 5, 1.0)
            
            return Signal(
                signal_type=SignalType.BUY,
                strength=strength,
                price=current_price,
                timestamp=datetime.now(),
                metadata={
                    'bb_position': 'lower_band',
                    'rsi': current_rsi,
                    'distance_to_middle': distance_to_middle
                }
            )
        
        # 价格触及上轨且RSI超买
        elif (current_price >= upper_band.iloc[-1] and 
              current_rsi >= (100 - self.rsi_threshold)):
            
            distance_to_middle = (current_price - middle_band.iloc[-1]) / current_price
            strength = min(distance_to_middle * 5, 1.0)
            
            return Signal(
                signal_type=SignalType.SELL,
                strength=strength,
                price=current_price,
                timestamp=datetime.now(),
                metadata={
                    'bb_position': 'upper_band',
                    'rsi': current_rsi,
                    'distance_to_middle': distance_to_middle
                }
            )
        
        return None
```

### 3. 多因子策略

```python
class MultiFactorStrategy(BaseStrategy):
    """多因子量化策略"""
    
    def __init__(self, config):
        super().__init__(config)
        self.factors = config.get('factors', {
            'momentum': {'weight': 0.3, 'period': 20},
            'mean_reversion': {'weight': 0.3, 'period': 10},
            'volatility': {'weight': 0.2, 'period': 14},
            'volume': {'weight': 0.2, 'period': 20}
        })
        
    def generate_signal(self, data):
        if len(data) < 50:  # 需要足够的历史数据
            return None
            
        # 计算各个因子得分
        factor_scores = {}
        
        # 动量因子
        momentum_score = self.calculate_momentum_factor(data)
        factor_scores['momentum'] = momentum_score
        
        # 均值回归因子
        mean_reversion_score = self.calculate_mean_reversion_factor(data)
        factor_scores['mean_reversion'] = mean_reversion_score
        
        # 波动率因子
        volatility_score = self.calculate_volatility_factor(data)
        factor_scores['volatility'] = volatility_score
        
        # 成交量因子
        volume_score = self.calculate_volume_factor(data)
        factor_scores['volume'] = volume_score
        
        # 计算综合得分
        total_score = 0
        for factor_name, score in factor_scores.items():
            weight = self.factors[factor_name]['weight']
            total_score += score * weight
        
        # 生成信号
        if total_score > 0.6:
            return Signal(
                signal_type=SignalType.BUY,
                strength=min(total_score, 1.0),
                price=data['close'].iloc[-1],
                timestamp=datetime.now(),
                metadata={'factor_scores': factor_scores, 'total_score': total_score}
            )
        elif total_score < -0.6:
            return Signal(
                signal_type=SignalType.SELL,
                strength=min(abs(total_score), 1.0),
                price=data['close'].iloc[-1],
                timestamp=datetime.now(),
                metadata={'factor_scores': factor_scores, 'total_score': total_score}
            )
        
        return None
    
    def calculate_momentum_factor(self, data):
        """计算动量因子"""
        period = self.factors['momentum']['period']
        returns = data['close'].pct_change(period).iloc[-1]
        # 标准化到[-1, 1]
        return np.tanh(returns * 10)
    
    def calculate_mean_reversion_factor(self, data):
        """计算均值回归因子"""
        period = self.factors['mean_reversion']['period']
        ma = data['close'].rolling(period).mean()
        deviation = (data['close'].iloc[-1] - ma.iloc[-1]) / ma.iloc[-1]
        # 均值回归信号与偏离方向相反
        return -np.tanh(deviation * 20)
    
    def calculate_volatility_factor(self, data):
        """计算波动率因子"""
        period = self.factors['volatility']['period']
        volatility = data['close'].rolling(period).std().iloc[-1]
        avg_volatility = data['close'].rolling(period * 3).std().mean()
        vol_ratio = volatility / avg_volatility
        # 低波动率时给正分，高波动率时给负分
        return np.tanh((1 - vol_ratio) * 5)
    
    def calculate_volume_factor(self, data):
        """计算成交量因子"""
        period = self.factors['volume']['period']
        volume_ma = data['volume'].rolling(period).mean()
        volume_ratio = data['volume'].iloc[-1] / volume_ma.iloc[-1]
        # 成交量放大给正分
        return np.tanh((volume_ratio - 1) * 2)
```

## 🎓 最佳实践

### 1. 策略设计原则

- **简单性**: 从简单策略开始，逐步增加复杂性
- **鲁棒性**: 策略应在不同市场条件下表现稳定
- **可解释性**: 策略逻辑应清晰可理解
- **可扩展性**: 设计时考虑未来的扩展需求

### 2. 代码质量

```python
# 好的实践
class WellDesignedStrategy(BaseStrategy):
    """文档完整的策略类"""
    
    def __init__(self, config):
        """
        初始化策略
        
        Args:
            config (dict): 策略配置参数
        """
        super().__init__(config)
        self._validate_config(config)
        self._setup_parameters(config)
        
    def _validate_config(self, config):
        """验证配置参数"""
        required_params = ['period', 'threshold']
        for param in required_params:
            if param not in config:
                raise ValueError(f"缺少必需参数: {param}")
    
    def _setup_parameters(self, config):
        """设置策略参数"""
        self.period = config['period']
        self.threshold = config['threshold']
        
        # 参数验证
        if self.period <= 0:
            raise ValueError("period 必须大于 0")
        if not 0 < self.threshold < 1:
            raise ValueError("threshold 必须在 0 和 1 之间")
```

### 3. 测试策略

```python
import unittest

class TestMyStrategy(unittest.TestCase):
    def setUp(self):
        self.config = {
            'period': 20,
            'threshold': 0.02
        }
        self.strategy = MyStrategy(self.config)
        
    def test_signal_generation(self):
        """测试信号生成"""
        # 创建测试数据
        test_data = self.create_test_data()
        
        # 生成信号
        signal = self.strategy.generate_signal(test_data)
        
        # 验证信号
        self.assertIsNotNone(signal)
        self.assertIn(signal.signal_type, [SignalType.BUY, SignalType.SELL])
        self.assertTrue(0 <= signal.strength <= 1)
    
    def test_parameter_validation(self):
        """测试参数验证"""
        with self.assertRaises(ValueError):
            MyStrategy({'period': -1, 'threshold': 0.02})
```

### 4. 性能监控

```python
import time
import functools

def performance_monitor(func):
    """性能监控装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        if execution_time > 0.1:  # 超过100ms记录警告
            print(f"警告: {func.__name__} 执行时间过长: {execution_time:.3f}s")
        
        return result
    return wrapper

class MonitoredStrategy(BaseStrategy):
    @performance_monitor
    def generate_signal(self, data):
        # 策略逻辑
        pass
```

## 📚 相关文档

- [快速开始指南](quick_start.md)
- [API参考文档](api_reference.md)
- [配置说明](configuration.md)
- [常见问题](faq.md)

---

**祝您策略开发顺利！** 🚀

> **提示**: 策略开发是一个迭代过程，建议从简单策略开始，逐步优化和完善。