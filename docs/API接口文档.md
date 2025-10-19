# MyQuant API 接口文档

## 📋 概述

本文档详细说明了MyQuant量化交易系统中各个核心类和方法的API接口，帮助开发者理解和使用系统的各个组件。MyQuant采用分层架构设计，包含应用层、策略层、基础层和数据层，提供完整的量化交易解决方案。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层 (Application Layer)                │
├─────────────────────────────────────────────────────────────┤
│  StrategyManager (策略管理器)  │  run_strategy.py (运行器)    │
├─────────────────────────────────────────────────────────────┤
│                    策略层 (Strategy Layer)                   │
├─────────────────────────────────────────────────────────────┤
│ SimpleEMA │ StagedEMA │ ComplexEMA │ AdvancedStagedEMA      │
├─────────────────────────────────────────────────────────────┤
│                    基础层 (Base Layer)                       │
├─────────────────────────────────────────────────────────────┤
│  BaseStrategy (策略基类)  │  ConfigManager (配置管理器)      │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                       │
├─────────────────────────────────────────────────────────────┤
│              DataManager (数据管理器)                        │
└─────────────────────────────────────────────────────────────┘
```

## 🗂️ 目录

- [数据管理器 (DataManager)](#数据管理器-datamanager)
- [策略基类 (BaseStrategy)](#策略基类-basestrategy)
- [配置管理器 (ConfigManager)](#配置管理器-configmanager)
- [策略运行器 (StrategyRunner)](#策略运行器-strategyrunner)
- [策略管理器 (StrategyManager)](#策略管理器-strategymanager)
- [具体策略类](#具体策略类)
- [配置数据类](#配置数据类)
- [图表生成器 (ChartGenerator)](#图表生成器-chartgenerator)

---

## 数据管理器 (DataManager)

### 类描述
`DataManager` 负责管理市场数据的获取、缓存和处理，支持从Binance API获取K线数据并提供智能缓存机制。

### 初始化

```python
from data_manager import DataManager

# 使用全局实例
from data_manager import data_manager

# 或创建新实例
dm = DataManager()
```

### 主要方法

#### `get_kline_data(symbol, start_date, end_date, interval='30m', force_refresh=False)`

获取K线数据（优先从缓存获取）

**参数:**
- `symbol` (str): 交易对符号，如 'BTCUSDT'
- `start_date` (str): 开始日期，支持格式：'2024-01-01' 或 '1 Jan, 2024'
- `end_date` (str): 结束日期，格式同上
- `interval` (str): 时间间隔，支持 '1m', '30m', '1h', '4h', '1d'
- `force_refresh` (bool): 是否强制刷新缓存，默认False

**返回值:**
- `pandas.DataFrame`: K线数据，包含以下列：
  - `open_time`: 开盘时间
  - `open`: 开盘价
  - `high`: 最高价
  - `low`: 最低价
  - `close`: 收盘价
  - `volume`: 成交量
  - `close_time`: 收盘时间

**示例:**
```python
# 获取BTC 30分钟K线数据
data = data_manager.get_kline_data('BTCUSDT', '2024-01-01', '2024-01-31', '30m')

# 强制刷新缓存
data = data_manager.get_kline_data('BTCUSDT', '2024-01-01', '2024-01-31', '1h', force_refresh=True)
```

#### `get_kline_data_monthly(symbol, start_date, end_date, interval='30m', force_refresh=False, save_monthly_files=True, monthly_output_dir=None)`

按月份拆分获取K线数据，适用于长时间范围的数据获取

**参数:**
- `symbol` (str): 交易对符号
- `start_date` (str): 开始日期
- `end_date` (str): 结束日期
- `interval` (str): 时间间隔
- `force_refresh` (bool): 是否强制刷新缓存
- `save_monthly_files` (bool): 是否保存月度文件
- `monthly_output_dir` (str): 月度文件输出目录

**返回值:**
- `pandas.DataFrame`: 合并后的完整K线数据

**示例:**
```python
# 获取全年数据，按月保存
data = data_manager.get_kline_data_monthly(
    'BTCUSDT', '2024-01-01', '2024-12-31', '1m',
    save_monthly_files=True,
    monthly_output_dir='output/monthly_data'
)
```

#### `get_multiple_intervals(symbol, start_date, end_date, intervals=['30m', '1m'], force_refresh=False)`

获取多个时间间隔的K线数据

**参数:**
- `symbol` (str): 交易对符号
- `start_date` (str): 开始日期
- `end_date` (str): 结束日期
- `intervals` (list): 时间间隔列表
- `force_refresh` (bool): 是否强制刷新缓存

**返回值:**
- `dict`: 包含不同时间间隔数据的字典

**示例:**
```python
# 同时获取1分钟和30分钟数据
data = data_manager.get_multiple_intervals(
    'BTCUSDT', '2024-01-01', '2024-01-31', 
    intervals=['1m', '30m', '1h']
)
# 访问不同间隔的数据
minute_data = data['1m']
hour_data = data['1h']
```

#### `clear_cache(symbol=None, older_than_days=None)`

清理缓存文件

**参数:**
- `symbol` (str, optional): 指定清理某个交易对的缓存，None表示清理所有
- `older_than_days` (int, optional): 清理多少天前的缓存，None表示清理所有

**示例:**
```python
# 清理所有缓存
data_manager.clear_cache()

# 清理BTC相关的缓存
data_manager.clear_cache(symbol='BTCUSDT')

# 清理7天前的缓存
data_manager.clear_cache(older_than_days=7)
```

#### `list_cache_files()`

列出所有缓存文件及其信息

**示例:**
```python
data_manager.list_cache_files()
```

---

## 策略基类 (BaseStrategy)

### 类描述
`BaseStrategy` 是所有交易策略的基类，定义了策略的标准接口和通用功能。位于 `strategies/base_strategy.py`，提供数据处理、交易管理、性能统计等核心功能。

### 初始化

```python
from strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
```

### 核心属性

- `strategy_name` (str): 策略名称
- `strategy_description` (str): 策略描述
- `strategy_version` (str): 策略版本
- `symbol` (str): 交易对符号
- `initial_capital` (float): 初始资金
- `capital` (float): 当前资金
- `leverage` (float): 杠杆倍数
- `fee` (float): 手续费率
- `position` (float): 当前持仓
- `trades` (list): 交易记录列表
- `detailed_trades` (list): 详细交易记录

### 主要方法

#### `__init__(config=None)`
初始化策略基类

**参数:**
- `config` (dict, optional): 策略配置参数字典

**默认配置包含:**
- 交易基础参数：symbol, start_date, end_date, initial_capital, leverage, fee
- EMA参数：ema_short, ema_long
- 资金管理参数：position_percentage
- 日志配置：enable_detailed_log, log_trades_to_file
- 图表配置：use_arrows_for_trades, chart_dpi

#### `reset_trading_state()`
重置交易状态

重置所有交易相关的状态变量，包括资金、持仓、交易记录等。

#### `preprocess_data(data)`
数据预处理

**参数:**
- `data` (pandas.DataFrame): 原始K线数据

**返回值:**
- `pandas.DataFrame`: 预处理后的数据

**功能:**
- 数据类型转换
- 时间索引设置
- 数据验证和清洗

#### `calculate_ema(data, period)`
计算指数移动平均线

**参数:**
- `data` (pandas.Series): 价格数据
- `period` (int): EMA周期

**返回值:**
- `pandas.Series`: EMA值序列

#### `calculate_trend_strength(data, period=14)`
计算趋势强度指标

**参数:**
- `data` (pandas.DataFrame): K线数据
- `period` (int): 计算周期，默认14

**返回值:**
- `pandas.Series`: 趋势强度值序列

#### `open_position(price, size, side='long', timestamp=None)`
开仓操作

**参数:**
- `price` (float): 开仓价格
- `size` (float): 开仓数量
- `side` (str): 方向，'long' 或 'short'
- `timestamp` (datetime, optional): 开仓时间

**返回值:**
- `bool`: 开仓是否成功

#### `close_position(price, timestamp=None)`
平仓操作

**参数:**
- `price` (float): 平仓价格
- `timestamp` (datetime, optional): 平仓时间

**返回值:**
- `dict`: 平仓结果，包含盈亏信息

#### `calculate_performance_metrics()`
计算性能指标

**返回值:**
- `dict`: 包含以下性能指标的字典
  - `total_return`: 总收益率
  - `annual_return`: 年化收益率
  - `max_drawdown`: 最大回撤
  - `sharpe_ratio`: 夏普比率
  - `win_rate`: 胜率
  - `profit_loss_ratio`: 盈亏比
  - `total_trades`: 总交易次数
  - `profitable_trades`: 盈利交易次数
  - `losing_trades`: 亏损交易次数

#### `plot_trading_chart(save_path=None)`
绘制交易图表

**参数:**
- `save_path` (str, optional): 图表保存路径

**功能:**
- 绘制K线图
- 标记买卖点
- 显示EMA线
- 保存图表文件

#### `save_detailed_trades(filename=None)`
保存详细交易记录

**参数:**
- `filename` (str, optional): 保存文件名

**功能:**
- 将交易记录保存为JSON格式
- 包含中文字段名
- 自动生成文件名

### 抽象方法（子类必须实现）

#### `get_strategy_specific_config()`
获取策略特定的配置参数

**返回值:**
- `dict`: 策略特定的配置参数

#### `run_backtest()`
运行回测（核心方法）

**返回值:**
- `dict`: 回测结果，包含性能指标和交易记录

### 配置管理

#### `_merge_config(user_config)`
合并用户配置和默认配置

**参数:**
- `user_config` (dict): 用户提供的配置

**返回值:**
- `dict`: 合并后的完整配置

#### `_validate_config(config)`
验证配置参数

**参数:**
- `config` (dict): 配置参数

**功能:**
- 检查必要参数是否存在
- 验证参数类型和范围
- 设置默认值

---

## 配置管理器 (ConfigManager)

### 类描述
`ConfigManager` 负责管理系统和策略的配置文件，位于 `strategies/config_manager.py`。提供配置的读取、保存、验证和修改功能，统一管理全局交易配置，确保杠杆、保证金比例等关键参数的一致性。

### 初始化

```python
from strategies.config_manager import ConfigManager, get_config_manager

# 创建配置管理器实例
config_manager = ConfigManager(config_dir='config')

# 或使用全局单例
config_manager = get_config_manager()
```

### 核心属性

- `config_dir` (str): 配置文件目录
- `config_file` (str): 主配置文件路径
- `configs` (dict): 所有配置的字典
- `strategy_config_classes` (dict): 策略配置类映射
- `global_trading_config` (GlobalTradingConfig): 全局交易配置

### 主要方法

#### `__init__(config_dir='config')`
初始化配置管理器

**参数:**
- `config_dir` (str): 配置文件目录，默认为 'config'

**功能:**
- 创建配置目录（如果不存在）
- 加载或创建默认配置
- 初始化策略配置类映射

#### `get_strategy_config(strategy_type)`
获取指定策略的配置

**参数:**
- `strategy_type` (str): 策略类型，支持：
  - `'simple_ema'`: 简单EMA策略
  - `'staged_ema'`: 分批入场EMA策略
  - `'complex_ema'`: 复杂EMA策略
  - `'advanced_staged_ema'`: 高级分批入场EMA策略

**返回值:**
- `dict`: 完整的策略配置字典，包含：
  - 策略特定配置
  - 全局交易配置
  - 日志配置
  - 图表配置

**示例:**
```python
config = config_manager.get_strategy_config('simple_ema')
print(config['initial_capital'])  # 10000.0
print(config['ema_short'])        # 9
```

#### `save_configs()`
保存所有配置到文件

**功能:**
- 将内存中的配置保存到JSON文件
- 自动格式化JSON输出
- 处理保存异常

#### `load_configs()`
从文件加载配置

**返回值:**
- `dict`: 加载的配置字典

**功能:**
- 从JSON文件读取配置
- 处理文件不存在的情况
- 验证配置格式

#### `update_strategy_config(strategy_type, updates)`
更新策略配置

**参数:**
- `strategy_type` (str): 策略类型
- `updates` (dict): 要更新的配置项

**示例:**
```python
# 更新简单EMA策略的参数
config_manager.update_strategy_config('simple_ema', {
    'ema_short': 12,
    'ema_long': 26,
    'initial_capital': 20000
})
```

#### `update_global_config(updates)`
更新全局交易配置

**参数:**
- `updates` (dict): 要更新的全局配置项

**示例:**
```python
# 更新全局配置
config_manager.update_global_config({
    'leverage': 2.0,
    'fee': 0.0005
})
```

#### `get_all_strategy_types()`
获取所有支持的策略类型

**返回值:**
- `list`: 策略类型列表

#### `validate_strategy_config(strategy_type, config)`
验证策略配置

**参数:**
- `strategy_type` (str): 策略类型
- `config` (dict): 配置字典

**返回值:**
- `bool`: 验证是否通过

**功能:**
- 检查必要参数
- 验证参数类型和范围
- 提供详细的错误信息

#### `create_default_config(strategy_type)`
创建策略的默认配置

**参数:**
- `strategy_type` (str): 策略类型

**返回值:**
- `dict`: 默认配置字典

#### `reset_to_defaults(strategy_type=None)`
重置配置为默认值

**参数:**
- `strategy_type` (str, optional): 指定策略类型，None表示重置所有

**功能:**
- 重置指定策略或所有策略的配置
- 保留用户自定义的全局配置

### 配置文件结构

配置管理器使用统一的JSON配置文件 `config.json`，包含以下结构：

```json
{
  "global_trading_config": {
    "symbol": "BTCUSDT",
    "start_date": "1 Oct, 2024",
    "end_date": "8 Oct, 2024",
    "initial_capital": 10000.0,
    "leverage": 1.0,
    "fee": 0.0004,
    "maintenance_margin_rate": 0.05,
    "output_directory": "output"
  },
  "simple_ema": {
    "ema_short": 9,
    "ema_long": 26,
    "position_percentage": 0.95
  },
  "staged_ema": {
    "ema_short": 9,
    "ema_long": 26,
    "entry_stages": 3,
    "stage_interval": 5,
    "stage_percentage": 0.3
  },
  "logging": {
    "enable_detailed_log": true,
    "log_trades_to_file": true,
    "log_file_prefix": "trades_detailed_log",
    "log_level": "INFO"
  },
  "chart": {
    "use_arrows_for_trades": true,
    "avoid_text_overlap": true,
    "chart_dpi": 300,
    "save_chart": true
  },
  "strategies_to_run": [
    "simple_ema",
    "staged_ema",
    "complex_ema",
    "advanced_staged_ema"
  ]
}
```

---

## 策略运行器 (StrategyRunner)

### 类描述
`StrategyRunner` 负责运行单个策略并管理其生命周期，位于 `strategies/strategy_runner.py`。提供策略的统一运行接口、批量策略执行、策略结果的收集和管理、策略运行状态监控以及异常处理和错误恢复。

### 初始化

```python
from strategies.strategy_runner import StrategyRunner, StrategyFactory

# 创建策略运行器
runner = StrategyRunner()

# 或使用工厂方法
runner = StrategyFactory.create_runner()
```

### 核心属性

- `config_manager` (ConfigManager): 配置管理器实例
- `strategy_registry` (dict): 策略类注册表
- `running_strategies` (dict): 正在运行的策略实例
- `strategy_results` (dict): 策略运行结果
- `execution_log` (list): 执行日志
- `is_running` (bool): 运行状态
- `start_time` (datetime): 开始时间
- `end_time` (datetime): 结束时间

### 主要方法

#### `__init__(config_manager=None)`
初始化策略运行器

**参数:**
- `config_manager` (ConfigManager, optional): 配置管理器实例

**功能:**
- 初始化运行状态
- 注册所有可用的策略类
- 设置执行日志

#### `register_strategy(strategy_type, strategy_class)`
注册策略类

**参数:**
- `strategy_type` (str): 策略类型标识
- `strategy_class` (class): 策略类

**功能:**
- 将策略类添加到注册表
- 验证策略类的有效性
- 支持动态策略注册

**示例:**
```python
from strategies.simple_ema_strategy import SimpleEMAStrategy

runner.register_strategy('simple_ema', SimpleEMAStrategy)
```

#### `run_strategy(strategy_type, config=None, **kwargs)`
运行指定策略

**参数:**
- `strategy_type` (str): 策略类型
- `config` (dict, optional): 策略配置，None时使用默认配置
- `**kwargs`: 额外的运行参数

**返回值:**
- `dict`: 策略运行结果，包含：
  - `strategy_name`: 策略名称
  - `execution_time`: 执行时间
  - `performance_metrics`: 性能指标
  - `trades`: 交易记录
  - `status`: 运行状态
  - `error_message`: 错误信息（如果有）

**示例:**
```python
# 使用默认配置运行策略
result = runner.run_strategy('simple_ema')

# 使用自定义配置运行策略
custom_config = {
    'ema_short': 12,
    'ema_long': 26,
    'initial_capital': 20000
}
result = runner.run_strategy('simple_ema', config=custom_config)
```

#### `run_multiple_strategies(strategy_types=None, parallel=False)`
运行多个策略

**参数:**
- `strategy_types` (list, optional): 要运行的策略类型列表，None表示运行所有注册的策略
- `parallel` (bool): 是否并行运行，默认False

**返回值:**
- `dict`: 包含所有策略结果的字典

**示例:**
```python
# 运行指定策略
results = runner.run_multiple_strategies(['simple_ema', 'staged_ema'])

# 并行运行所有策略
results = runner.run_multiple_strategies(parallel=True)
```

#### `get_strategy_status(strategy_type)`
获取策略运行状态

**参数:**
- `strategy_type` (str): 策略类型

**返回值:**
- `dict`: 策略状态信息

#### `stop_strategy(strategy_type)`
停止正在运行的策略

**参数:**
- `strategy_type` (str): 策略类型

**返回值:**
- `bool`: 停止是否成功

#### `list_registered_strategies()`
列出所有已注册的策略

**返回值:**
- `list`: 策略类型列表

#### `list_available_strategies()`
列出所有可用的策略类型

**返回值:**
- `list`: 可用策略类型列表

#### `get_execution_log()`
获取执行日志

**返回值:**
- `list`: 执行日志列表

#### `clear_results()`
清空策略运行结果

**功能:**
- 清空所有策略结果
- 重置运行状态
- 清空执行日志

#### `validate_strategy_config(strategy_type, config)`
验证策略配置

**参数:**
- `strategy_type` (str): 策略类型
- `config` (dict): 配置字典

**返回值:**
- `tuple`: (is_valid, error_messages)

### 异常处理

#### `handle_strategy_error(strategy_type, error)`
处理策略运行错误

**参数:**
- `strategy_type` (str): 策略类型
- `error` (Exception): 异常对象

**功能:**
- 记录错误信息
- 清理资源
- 提供错误恢复建议

### 工厂类 (StrategyFactory)

#### `create_runner(config_manager=None)`
创建策略运行器

**参数:**
- `config_manager` (ConfigManager, optional): 配置管理器

**返回值:**
- `StrategyRunner`: 策略运行器实例

#### `get_available_strategies()`
获取可用的策略类型列表

**返回值:**
- `list`: 策略类型列表

---

## 策略管理器 (StrategyManager)

### 类描述
`StrategyManager` 负责管理多个策略的并行运行和结果比较。

### 主要方法

#### `__init__(config_path='config.json')`
初始化策略管理器

**参数:**
- `config_path` (str): 主配置文件路径

#### `run_strategies(strategies_to_run=None)`
运行多个策略

**参数:**
- `strategies_to_run` (list, optional): 要运行的策略列表，None表示运行所有策略

**返回值:**
- `dict`: 包含所有策略结果的字典

#### `compare_strategies(results)`
比较策略性能

**参数:**
- `results` (dict): 策略结果字典

**返回值:**
- `pandas.DataFrame`: 策略比较表

#### `generate_comparison_charts(results, output_dir='output')`
生成策略比较图表

**参数:**
- `results` (dict): 策略结果字典
- `output_dir` (str): 输出目录

---

## 具体策略类

### SimpleEMAStrategy (简单EMA交叉策略)

#### 策略描述
基于快慢EMA均线交叉的简单交易策略。

#### 配置参数
- `fast_ema_period` (int): 快速EMA周期，默认12
- `slow_ema_period` (int): 慢速EMA周期，默认26
- `initial_capital` (float): 初始资金
- `leverage` (float): 杠杆倍数
- `position_percentage` (float): 仓位百分比

#### 主要方法

##### `run_backtest(data, **kwargs)`
运行回测

**参数:**
- `data` (pandas.DataFrame): K线数据
- `**kwargs`: 其他参数

**返回值:**
- `dict`: 回测结果

### StagedEMAStrategy (分批入场EMA交叉策略)

#### 策略描述
基于EMA交叉的分批入场策略，支持多次分批建仓。

#### 配置参数
- `fast_ema_period` (int): 快速EMA周期
- `slow_ema_period` (int): 慢速EMA周期
- `entry_stages` (int): 入场阶段数，默认3
- `stage_interval` (int): 阶段间隔（K线数），默认5
- `initial_capital` (float): 初始资金
- `leverage` (float): 杠杆倍数

### ComplexEMAStrategy (复杂EMA交叉策略)

#### 策略描述
包含趋势强度过滤的复杂EMA交叉策略。

#### 配置参数
- `fast_ema_period` (int): 快速EMA周期
- `slow_ema_period` (int): 慢速EMA周期
- `trend_strength_period` (int): 趋势强度计算周期，默认14
- `min_trend_strength` (float): 最小趋势强度阈值，默认0.02
- `initial_capital` (float): 初始资金
- `leverage` (float): 杠杆倍数

### AdvancedStagedEMAStrategy (高级分批入场EMA交叉策略)

#### 策略描述
结合趋势强度过滤和分批入场的高级策略，包含爆仓检测功能。

#### 配置参数
- `fast_ema_period` (int): 快速EMA周期
- `slow_ema_period` (int): 慢速EMA周期
- `trend_strength_period` (int): 趋势强度计算周期
- `min_trend_strength` (float): 最小趋势强度阈值
- `entry_stages` (int): 入场阶段数
- `stage_interval` (int): 阶段间隔
- `maintenance_margin_rate` (float): 维持保证金率，默认0.004
- `initial_capital` (float): 初始资金
- `leverage` (float): 杠杆倍数

#### 特殊功能
- **爆仓检测**: 自动检测并处理爆仓情况
- **中文化输出**: 支持中文字段名的JSON输出

---

## 🔧 使用示例

### 基本使用流程

```python
# 1. 导入必要模块
from strategy_manager import StrategyManager
from data_manager import data_manager

# 2. 创建策略管理器
manager = StrategyManager('config.json')

# 3. 运行所有策略
results = manager.run_strategies()

# 4. 比较策略性能
comparison = manager.compare_strategies(results)
print(comparison)

# 5. 生成比较图表
manager.generate_comparison_charts(results)
```

### 单独运行策略

```python
# 1. 导入策略运行器
from strategies.strategy_runner import StrategyRunner

# 2. 创建运行器并注册策略
runner = StrategyRunner()

# 3. 运行特定策略
config = {
    'symbol': 'BTCUSDT',
    'start_date': '2024-01-01',
    'end_date': '2024-01-31',
    'initial_capital': 10000,
    'leverage': 1.0
}

result = runner.run_strategy('SimpleEMAStrategy', config)
```

### 自定义数据获取

```python
# 1. 获取自定义时间范围的数据
data = data_manager.get_kline_data(
    'ETHUSDT', '2024-06-01', '2024-06-30', '1h'
)

# 2. 获取多个时间间隔的数据
multi_data = data_manager.get_multiple_intervals(
    'BTCUSDT', '2024-01-01', '2024-01-07',
    intervals=['1m', '5m', '15m', '30m', '1h']
)
```

---

## 📊 返回数据格式

### 策略结果格式

```python
{
    'strategy_name': '策略名称',
    'performance_metrics': {
        'total_return': 0.15,           # 总收益率
        'annual_return': 0.18,          # 年化收益率
        'max_drawdown': 0.08,           # 最大回撤
        'sharpe_ratio': 1.25,           # 夏普比率
        'win_rate': 0.65,               # 胜率
        'profit_loss_ratio': 1.8,       # 盈亏比
        'total_trades': 45,             # 总交易次数
        'profitable_trades': 29,        # 盈利交易次数
        'losing_trades': 16             # 亏损交易次数
    },
    'trades': [                         # 交易记录
        {
            'entry_time': '2024-01-01 10:00:00',
            'exit_time': '2024-01-01 12:00:00',
            'side': 'long',
            'entry_price': 42000.0,
            'exit_price': 42500.0,
            'quantity': 0.1,
            'pnl': 50.0,
            'pnl_percentage': 0.012
        }
    ],
    'equity_curve': [                   # 资金曲线
        {'time': '2024-01-01', 'equity': 10000.0},
        {'time': '2024-01-02', 'equity': 10050.0}
    ]
}
```

### K线数据格式

```python
DataFrame columns:
- open_time (datetime): 开盘时间
- open (float): 开盘价
- high (float): 最高价
- low (float): 最低价
- close (float): 收盘价
- volume (float): 成交量
- close_time (datetime): 收盘时间
```

---

## ⚠️ 注意事项

1. **API限制**: Binance API有请求频率限制，建议合理使用缓存机制
2. **数据完整性**: 确保网络连接稳定，避免数据获取中断
3. **内存使用**: 长时间范围的1分钟数据会占用较多内存
4. **配置文件**: 确保配置文件格式正确，必要参数不能缺失
5. **环境变量**: 需要正确设置Binance API密钥（如果需要）

---

## 🔗 相关文档

- [操作说明](操作说明.md) - 系统使用指南
- [算法说明](算法说明.md) - 算法原理详解
- [配置文件说明](配置文件说明.md) - 配置参数详解

---

## 配置数据类

### 概述
MyQuant系统使用数据类（dataclass）来定义和管理各种配置参数，确保类型安全和参数验证。

### 全局交易配置 (GlobalTradingConfig)

```python
@dataclass
class GlobalTradingConfig:
    symbol: str = 'BTCUSDT'
    start_date: str = '1 Oct, 2024'
    end_date: str = '8 Oct, 2024'
    initial_capital: float = 10000.0
    leverage: float = 1.0
    fee: float = 0.0004
    maintenance_margin_rate: float = 0.05
    output_directory: str = 'output'
```

### 策略配置类

#### SimpleEMAConfig (简单EMA策略配置)
```python
@dataclass
class SimpleEMAConfig(BaseConfig):
    ema_short: int = 9
    ema_long: int = 26
    position_percentage: float = 0.95
```

#### StagedEMAConfig (分批入场EMA策略配置)
```python
@dataclass
class StagedEMAConfig(BaseConfig):
    ema_short: int = 9
    ema_long: int = 26
    entry_stages: int = 3
    stage_interval: int = 5
    stage_percentage: float = 0.3
```

#### ComplexEMAConfig (复杂EMA策略配置)
```python
@dataclass
class ComplexEMAConfig(BaseConfig):
    ema_short: int = 9
    ema_long: int = 26
    trend_strength_period: int = 14
    min_trend_strength: float = 0.02
    position_percentage: float = 0.95
```

#### AdvancedStagedEMAConfig (高级分批入场EMA策略配置)
```python
@dataclass
class AdvancedStagedEMAConfig(BaseConfig):
    ema_short: int = 9
    ema_long: int = 26
    trend_strength_period: int = 14
    min_trend_strength: float = 0.02
    entry_stages: int = 3
    stage_interval: int = 5
    stage_percentage: float = 0.3
```

### 日志配置 (LoggingConfig)
```python
@dataclass
class LoggingConfig:
    enable_detailed_log: bool = True
    log_trades_to_file: bool = True
    log_file_prefix: str = 'trades_detailed_log'
    log_level: str = 'INFO'
```

### 图表配置 (ChartConfig)
```python
@dataclass
class ChartConfig:
    use_arrows_for_trades: bool = True
    avoid_text_overlap: bool = True
    chart_dpi: int = 300
    save_chart: bool = True
```

---

## 图表生成器 (ChartGenerator)

### 类描述
`ChartGenerator` 负责生成交易策略的可视化图表，位于 `chart_generator.py`。提供K线图、交易信号、技术指标等的绘制功能。

### 主要功能

#### 交易图表生成
- K线图绘制
- 买卖信号标记
- EMA均线显示
- 成交量柱状图
- 趋势强度指标

#### 性能图表生成
- 资金曲线图
- 回撤曲线图
- 收益分布图
- 交易统计图表

#### 比较图表生成
- 多策略性能对比
- 收益率对比
- 风险指标对比

### 使用示例

```python
from chart_generator import ChartGenerator

# 创建图表生成器
chart_gen = ChartGenerator()

# 生成交易图表
chart_gen.plot_trading_chart(
    data=kline_data,
    trades=trade_records,
    indicators={'ema_short': ema_short, 'ema_long': ema_long},
    save_path='output/charts/trading_chart.png'
)

# 生成性能图表
chart_gen.plot_performance_chart(
    equity_curve=equity_data,
    save_path='output/charts/performance_chart.png'
)
```

---

## 🔧 完整使用示例

### 1. 基本策略运行

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 导入必要模块
from strategies.strategy_runner import StrategyRunner
from strategies.config_manager import get_config_manager
from data_manager import data_manager

def main():
    # 1. 创建策略运行器
    runner = StrategyRunner()
    
    # 2. 获取配置管理器
    config_manager = get_config_manager()
    
    # 3. 运行单个策略
    result = runner.run_strategy('simple_ema')
    
    # 4. 输出结果
    print(f"策略名称: {result['strategy_name']}")
    print(f"总收益率: {result['performance_metrics']['total_return']:.2%}")
    print(f"夏普比率: {result['performance_metrics']['sharpe_ratio']:.2f}")
    
    # 5. 运行多个策略对比
    results = runner.run_multiple_strategies([
        'simple_ema', 'staged_ema', 'complex_ema'
    ])
    
    # 6. 生成对比报告
    for strategy_name, result in results.items():
        metrics = result['performance_metrics']
        print(f"{strategy_name}: 收益率 {metrics['total_return']:.2%}, "
              f"最大回撤 {metrics['max_drawdown']:.2%}")

if __name__ == "__main__":
    main()
```

### 2. 自定义策略开发

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from strategies.base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class MyCustomStrategy(BaseStrategy):
    """自定义策略示例"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.strategy_name = "我的自定义策略"
        self.strategy_description = "基于RSI和MACD的复合策略"
    
    def get_strategy_specific_config(self):
        """返回策略特定配置"""
        return {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9
        }
    
    def calculate_indicators(self):
        """计算技术指标"""
        # 计算RSI
        self.data['rsi'] = self.calculate_rsi(self.data['close'], 
                                            self.config['rsi_period'])
        
        # 计算MACD
        macd_data = self.calculate_macd(self.data['close'],
                                      self.config['macd_fast'],
                                      self.config['macd_slow'],
                                      self.config['macd_signal'])
        self.data = pd.concat([self.data, macd_data], axis=1)
    
    def run_backtest(self):
        """运行回测"""
        # 1. 重置状态
        self.reset_trading_state()
        
        # 2. 获取数据
        data = data_manager.get_kline_data(
            self.symbol, self.start_date, self.end_date
        )
        self.data = self.preprocess_data(data)
        
        # 3. 计算指标
        self.calculate_indicators()
        
        # 4. 执行交易逻辑
        for i in range(len(self.data)):
            current_data = self.data.iloc[i]
            
            # 买入信号：RSI超卖且MACD金叉
            if (current_data['rsi'] < self.config['rsi_oversold'] and
                current_data['macd'] > current_data['macd_signal'] and
                self.position == 0):
                
                size = self.calculate_position_size(current_data['close'])
                self.open_position(current_data['close'], size, 'long',
                                 current_data.name)
            
            # 卖出信号：RSI超买或MACD死叉
            elif ((current_data['rsi'] > self.config['rsi_overbought'] or
                   current_data['macd'] < current_data['macd_signal']) and
                  self.position > 0):
                
                self.close_position(current_data['close'], current_data.name)
        
        # 5. 生成图表
        self.plot_trading_chart()
        
        # 6. 返回结果
        return {
            'strategy_name': self.strategy_name,
            'performance_metrics': self.calculate_performance_metrics(),
            'trades': self.trades,
            'final_capital': self.capital
        }
    
    def calculate_rsi(self, prices, period):
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast, slow, signal):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        
        return pd.DataFrame({
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_histogram': macd_histogram
        })

# 使用自定义策略
if __name__ == "__main__":
    # 创建策略实例
    strategy = MyCustomStrategy({
        'symbol': 'ETHUSDT',
        'start_date': '1 Nov, 2024',
        'end_date': '30 Nov, 2024',
        'initial_capital': 50000,
        'rsi_period': 14,
        'macd_fast': 12,
        'macd_slow': 26
    })
    
    # 运行回测
    result = strategy.run_backtest()
    
    # 输出结果
    print(f"策略收益率: {result['performance_metrics']['total_return']:.2%}")
    print(f"交易次数: {result['performance_metrics']['total_trades']}")
```

### 3. 批量策略管理

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from strategy_manager import StrategyManager
import pandas as pd

def main():
    # 1. 创建策略管理器
    manager = StrategyManager()
    
    # 2. 运行所有策略
    print("开始运行所有策略...")
    results = manager.run_strategies()
    
    # 3. 生成对比表
    comparison_df = manager.compare_strategies(results)
    print("\n策略对比结果:")
    print(comparison_df.to_string())
    
    # 4. 生成对比图表
    manager.generate_comparison_charts(results, 'output/comparison')
    
    # 5. 保存结果到Excel
    with pd.ExcelWriter('output/strategy_comparison.xlsx') as writer:
        comparison_df.to_excel(writer, sheet_name='策略对比', index=False)
        
        # 为每个策略创建详细页面
        for strategy_name, result in results.items():
            if 'trades' in result:
                trades_df = pd.DataFrame(result['trades'])
                trades_df.to_excel(writer, sheet_name=f'{strategy_name}_交易记录', 
                                 index=False)
    
    print("\n所有策略运行完成，结果已保存到 output/ 目录")

if __name__ == "__main__":
    main()
```

---

## ⚠️ 注意事项

1. **API限制**: Binance API有请求频率限制，建议合理使用缓存机制
2. **数据完整性**: 确保网络连接稳定，避免数据获取中断
3. **内存使用**: 长时间范围的1分钟数据会占用较多内存
4. **配置文件**: 确保配置文件格式正确，必要参数不能缺失
5. **环境变量**: 需要正确设置Binance API密钥（如果需要）
6. **线程安全**: 多线程环境下使用时注意线程安全
7. **异常处理**: 建议在生产环境中添加完善的异常处理机制

---

## 🔗 相关文档

- [操作说明](操作说明.md) - 系统使用指南
- [算法说明](算法说明.md) - 算法原理详解
- [策略运行结果总结](策略运行结果总结.md) - 策略性能分析
- [项目清理记录](项目清理记录.md) - 项目维护记录

---

*本API文档涵盖了MyQuant系统的核心接口，如有疑问请参考相关源代码或联系开发团队。*