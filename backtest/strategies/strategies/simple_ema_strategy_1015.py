#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的简单EMA交叉策略
基于30分钟EMA9/EMA26交叉信号进行交易

策略特点：
1. 遇到交叉信号立即进场
2. 遇到反向交叉信号立即出场
3. 固定仓位，无加仓机制
4. 简单明了的交易逻辑

重构特性：
- 继承自BaseStrategy基类
- 使用配置管理器统一管理参数
- 策略逻辑与运行逻辑分离
- 支持参数化配置

作者：量化交易系统
版本：2.0 (重构版)
"""

import pandas as pd
import numpy as np
import ta
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# 添加当前目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_strategy import BaseStrategy
from config_manager import SimpleEMAConfig


class SimpleEMAStrategy(BaseStrategy):
    """
    简单EMA交叉策略
    
    基于EMA交叉信号的简单策略实现。
    当短期EMA上穿长期EMA时做多，下穿时做空。
    """
    
    # ==================== 策略独有参数配置 ====================
    # 这些参数可以在类顶部方便地修改
    
    # EMA参数 - 这些参数必须在config.json中定义
    # DEFAULT_EMA_SHORT = 9      # 短期EMA周期 - 已移除，必须从config读取
    # DEFAULT_EMA_LONG = 26      # 长期EMA周期 - 已移除，必须从config读取
    
    # 交易参数 - position_percentage属于global配置，不允许在策略中定义默认值
    # DEFAULT_POSITION_PERCENTAGE = 0.95  # 已移除，必须从global config读取
    
    # 时间框架
    DEFAULT_TIMEFRAME = '30min'  # 主要分析时间框架
    
    # 策略标识
    STRATEGY_TYPE = 'simple_ema'
    STRATEGY_NAME = '简单EMA交叉策略'
    STRATEGY_DESCRIPTION = '基于EMA交叉的简单策略，交叉进，反向交叉出'
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化简单EMA交叉策略
        
        Args:
            config (Dict[str, Any], optional): 策略配置参数
        """
        # 调用父类初始化
        super().__init__(config)
        
        # 设置策略基本信息
        self.strategy_type = self.STRATEGY_TYPE
        self.strategy_name = self.STRATEGY_NAME
        self.strategy_description = self.STRATEGY_DESCRIPTION
        
        # 获取策略特定配置
        self._setup_strategy_config()
        
        # 初始化策略特定变量
        self._init_strategy_variables()
    
    def _setup_strategy_config(self):
        """设置策略特定配置"""
        # 获取EMA参数 - 必须在config.json中定义，不允许默认值
        self.ema_short = self.config.get('ema_short')
        self.ema_long = self.config.get('ema_long')
        
        if self.ema_short is None or self.ema_long is None:
            raise ValueError("ema_short和ema_long必须在config.json的strategies配置中定义")
        
        # 获取交易参数 - position_percentage属于global配置
        self.position_percentage = self.config.get('position_percentage')
        if self.position_percentage is None:
            raise ValueError("position_percentage必须在config.json的global配置中定义")
        
        # 获取时间框架
        self.timeframe = self.config.get('timeframe', self.DEFAULT_TIMEFRAME)
        
        # 验证参数
        self._validate_config()
    
    def _validate_config(self):
        """验证策略配置参数"""
        if self.ema_short >= self.ema_long:
            raise ValueError(f"短期EMA周期({self.ema_short})必须小于长期EMA周期({self.ema_long})")
        
        if not 0 < self.position_percentage <= 1:
            raise ValueError(f"仓位比例({self.position_percentage})必须在0-1之间")
        
        if self.ema_short < 1 or self.ema_long < 1:
            raise ValueError("EMA周期必须大于0")
    
    def _init_strategy_variables(self):
        """初始化策略特定变量"""
        # EMA列名
        self.ema_short_col = f'EMA{self.ema_short}'
        self.ema_long_col = f'EMA{self.ema_long}'
        
        # 策略状态
        self.last_signal = None  # 记录上一个信号
        self.trade_count = 0     # 交易计数器，用于生成trade_id
        
        print(f"策略初始化完成:")
        print(f"  - EMA参数: {self.ema_short}/{self.ema_long}")
        print(f"  - 仓位比例: {self.position_percentage*100:.1f}%")
        print(f"  - 时间框架: {self.timeframe}")
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            df (pd.DataFrame): 价格数据
            
        Returns:
            pd.DataFrame: 包含指标的数据框
        """
        df = df.copy()
        
        # 计算EMA指标
        df[self.ema_short_col] = ta.trend.EMAIndicator(
            df['close'], window=self.ema_short
        ).ema_indicator()
        
        df[self.ema_long_col] = ta.trend.EMAIndicator(
            df['close'], window=self.ema_long
        ).ema_indicator()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame, current_idx: int) -> Tuple[Optional[str], float]:
        """
        生成交易信号
        
        Args:
            df (pd.DataFrame): 包含指标的价格数据
            current_idx (int): 当前数据索引
            
        Returns:
            Tuple[Optional[str], float]: (信号类型, 信号价格)
        """
        if current_idx < 1:
            return None, 0.0
        
        # 获取当前和前一根K线的EMA值
        current_ema_short = df.iloc[current_idx][self.ema_short_col]
        current_ema_long = df.iloc[current_idx][self.ema_long_col]
        prev_ema_short = df.iloc[current_idx-1][self.ema_short_col]
        prev_ema_long = df.iloc[current_idx-1][self.ema_long_col]
        
        # 检查是否有有效的EMA值
        if pd.isna(current_ema_short) or pd.isna(current_ema_long) or \
           pd.isna(prev_ema_short) or pd.isna(prev_ema_long):
            return None, 0.0
        
        # 检测金叉（做多信号）
        if prev_ema_short <= prev_ema_long and current_ema_short > current_ema_long:
            signal_price = (current_ema_short + current_ema_long) / 2
            return 'long', signal_price
        
        # 检测死叉（做空信号）
        if prev_ema_short >= prev_ema_long and current_ema_short < current_ema_long:
            signal_price = (current_ema_short + current_ema_long) / 2
            return 'short', signal_price
        
        return None, 0.0
    
    def should_enter_position(self, signal: str, signal_price: float, 
                            current_data: pd.Series) -> bool:
        """
        判断是否应该进场
        
        Args:
            signal (str): 信号类型 ('long' 或 'short')
            signal_price (float): 信号价格
            current_data (pd.Series): 当前K线数据
            
        Returns:
            bool: 是否应该进场
        """
        # 简单EMA策略：有信号就进场
        return True
    
    def should_exit_position(self, current_data: pd.Series, 
                           signal: Optional[str] = None) -> Tuple[bool, str]:
        """
        判断是否应该出场
        
        Args:
            current_data (pd.Series): 当前K线数据
            signal (Optional[str]): 当前信号
            
        Returns:
            Tuple[bool, str]: (是否出场, 出场原因)
        """
        # 如果有反向信号，则出场
        if signal and self.current_side:
            if (self.current_side == 'long' and signal == 'short') or \
               (self.current_side == 'short' and signal == 'long'):
                return True, "反向交叉信号"
        
        return False, ""
    
    def calculate_position_size(self, signal: str, entry_price: float) -> float:
        """
        计算仓位大小
        
        Args:
            signal (str): 信号类型
            entry_price (float): 入场价格
            
        Returns:
            float: 仓位大小
        """
        # 计算投入资金
        investment = self.capital * self.position_percentage
        
        # 计算仓位数量（应用杠杆）
        position_size = (investment * self.leverage) / entry_price
        
        return position_size
    
    def _force_close_position(self, price: float, timestamp: Any, reason: str):
        """
        强制平仓
        
        Args:
            price (float): 平仓价格
            timestamp: 平仓时间
            reason (str): 平仓原因
        """
        if self.position_size > 0:
            # 计算盈亏
            if self.current_side == 'long':
                profit = (price - self.entry_price) * self.position_size
            else:  # short
                profit = (self.entry_price - price) * self.position_size
            
            # 扣除手续费
            fee_cost = abs(self.position_size) * price * self.fee
            profit -= fee_cost
            
            # 更新资金（归还保证金 + 盈亏）
            self.capital += self.position_value + profit
            
            # 更新交易记录
            if self.detailed_trades:
                last_trade = self.detailed_trades[-1]
                last_trade['exit_time'] = timestamp
                last_trade['exit_price'] = price
                last_trade['profit'] = profit
                last_trade['reason'] = reason
                last_trade['status'] = 'closed'  # 更新状态为已平仓
            
            # 平仓日志已简化
            
            # 重置持仓状态
            self.position_size = 0
            self.position_value = 0
            self.entry_price = 0
            self.current_side = None
    
    # ==================== 实现BaseStrategy抽象方法 ====================
    
    def get_strategy_specific_config(self) -> Dict:
        """
        获取策略特定的配置参数
        
        Returns:
            Dict: 策略特定的配置参数
        """
        return {
            'ema_short': self.ema_short,
            'ema_long': self.ema_long,
            'position_percentage': self.position_percentage,
            'timeframe': self.timeframe
        }
    
    def detect_signals(self, current_idx: int) -> Tuple[Optional[str], Optional[float]]:
        """
        检测交易信号
        
        Args:
            current_idx (int): 当前K线索引
            
        Returns:
            Tuple[Optional[str], Optional[float]]: (信号类型, 信号价格)
        """
        return self.generate_signals(self.klines_30min, current_idx)
    
    def execute_trading_logic(self, signal: str, price: float, timestamp: Any) -> bool:
        """
        执行交易逻辑
        
        Args:
            signal (str): 交易信号 ('long', 'short', 'close')
            price (float): 交易价格
            timestamp: 时间戳
            
        Returns:
            bool: 是否成功执行交易
        """
        try:
            if signal in ['long', 'short']:
                # 如果已有持仓且信号与当前持仓方向相反，先平仓
                if self.position_size > 0:
                    if (self.current_side == 'long' and signal == 'short') or \
                       (self.current_side == 'short' and signal == 'long'):
                        self._force_close_position(price, timestamp, "反向交叉信号")
                
                # 如果无持仓，开新仓
                if self.position_size == 0:
                    # 计算投入资金（保证金）
                    investment = self.capital * self.position_percentage
                    # 计算杠杆后的仓位大小
                    position_size = (investment * self.leverage) / price
                    
                    # 开仓
                    self.position_size = position_size
                    self.position_value = investment
                    self.entry_price = price
                    self.current_side = signal
                    self.capital -= investment
                    
                    # 增加交易计数器
                    self.trade_count += 1
                    
                    # 记录交易
                    trade_record = {
                        'trade_id': self.trade_count,
                        'type': signal,
                        'entry_time': timestamp,
                        'entry_price': price,
                        'position_size': position_size,
                        'investment': investment,
                        'capital_allocated': investment,  # 添加资金分配字段
                        'exit_time': None,
                        'exit_price': None,
                        'profit': None,
                        'reason': None,
                        'status': 'open',  # 添加状态字段
                        'action': '初始入场'
                    }
                    self.detailed_trades.append(trade_record)
                    
            elif signal == 'close':
                if self.position_size > 0:
                    self._force_close_position(price, timestamp, "信号平仓")
            
            return True
            
        except Exception as e:
            print(f"执行交易逻辑失败: {e}")
            return False
    
    def _execute_backtest_loop(self):
        """执行回测循环"""
        print(f"\\n开始执行{self.strategy_name}回测循环...")
        print(f"30分钟K线数量: {len(self.klines_30min)}")
        print(f"1分钟K线数量: {len(self.klines_1min)}")
        
        # 计算技术指标
        self.klines_30min = self.calculate_indicators(self.klines_30min)
        
        # 设置用于图表的价格数据
        self.price_data_for_chart = self.klines_30min.copy()
        
        # 遍历30分钟K线
        for i in range(len(self.klines_30min)):
            candle_30min = self.klines_30min.iloc[i]
            
            # 获取对应的1分钟数据进行爆仓检测
            df_1min_period = self.get_minute_data_for_period(self.klines_1min, candle_30min)
            
            # 在每个1分钟K线上检查爆仓
            if len(df_1min_period) > 0:
                for _, min_candle in df_1min_period.iterrows():
                    if self._check_liquidation(min_candle['close'], min_candle.name):
                        break  # 如果爆仓，跳出循环
            
            # 检测交易信号
            signal, signal_price = self.detect_signals(i)
            
            if signal:
                # 获取对应的1分钟数据，使用第一根1分钟K线的收盘价作为入场价
                df_1min_period = self.get_minute_data_for_period(self.klines_1min, candle_30min)
                
                if len(df_1min_period) > 0:
                    first_1min_candle = df_1min_period.iloc[0]
                    entry_price = first_1min_candle['close']
                    entry_timestamp = first_1min_candle.name
                    
                    # 执行交易逻辑
                    self.execute_trading_logic(signal, entry_price, entry_timestamp)
            
            # 记录图表数据（在交易逻辑执行之后，以记录正确的资金状态）
            ema_short_val = candle_30min.get(f'ema_{self.ema_short}', None)
            ema_long_val = candle_30min.get(f'ema_{self.ema_long}', None)
            self.record_chart_data(candle_30min.name, ema_short_val, ema_long_val)
        
        # 如果回测结束时还有持仓，强制平仓
        if self.position_size > 0:
            last_price = self.klines_1min.iloc[-1]['close']
            last_time = self.klines_1min.index[-1]
            self._force_close_position(last_price, last_time, "回测结束强制平仓")
            
            # 强制平仓后记录最终资金状态
            self.capital_history.append(self.capital)
            self.timestamp_history.append(last_time)
    
    def get_minute_data_for_period(self, df_minute: pd.DataFrame, 
                                 candle_main: pd.Series) -> pd.DataFrame:
        """
        获取主时间框架K线对应的分钟数据
        
        Args:
            df_minute (pd.DataFrame): 分钟级数据
            candle_main (pd.Series): 主时间框架K线
            
        Returns:
            pd.DataFrame: 对应的分钟数据
        """
        # 30分钟数据的open_time是索引，需要使用candle_main.name获取时间
        start_time = candle_main.name
        # 计算结束时间（30分钟后）
        end_time = start_time + pd.Timedelta(minutes=30)
        
        # df_minute的open_time也是索引，使用index进行筛选
        mask = (df_minute.index >= start_time) & (df_minute.index <= end_time)
        return df_minute[mask]
    
    def get_strategy_config_summary(self) -> Dict[str, Any]:
        """
        获取策略配置摘要
        
        Returns:
            Dict[str, Any]: 策略配置摘要
        """
        return {
            'strategy_type': self.strategy_type,
            'strategy_name': self.strategy_name,
            'ema_short': self.ema_short,
            'ema_long': self.ema_long,
            'position_percentage': self.position_percentage,
            'timeframe': self.timeframe,
            'symbol': self.symbol,
            'leverage': self.leverage,
            'maintenance_margin_rate': self.maintenance_margin_rate
        }
    
    def plot_strategy_specific_indicators(self, ax, df: pd.DataFrame):
        """
        绘制策略特定的技术指标
        
        Args:
            ax: matplotlib轴对象
            df (pd.DataFrame): 包含指标的数据
        """
        # 绘制EMA线
        if self.ema_short_col in df.columns:
            ax.plot(df.index, df[self.ema_short_col], 
                   color='blue', linewidth=2, label=f'EMA{self.ema_short}', alpha=0.8)
        
        if self.ema_long_col in df.columns:
            ax.plot(df.index, df[self.ema_long_col], 
                   color='red', linewidth=2, label=f'EMA{self.ema_long}', alpha=0.8)
    
    def get_chart_filename(self) -> str:
        """
        获取图表文件名
        
        Returns:
            str: 图表文件名
        """
        return 'simple_ema_strategy_chart.png'
    
    def plot_trading_chart(self):
        """
        重写父类的画图方法，使用simple_ema策略专用的画图功能
        """
        try:
            print("正在生成Simple EMA策略专用图表...")
            self.generate_strategy_chart()
            
            # 生成交易分析图表
            if self.detailed_trades:
                from chart_generator import ChartGenerator
                chart_gen = ChartGenerator()
                chart_gen.generate_trade_analysis_chart(self.detailed_trades, self.strategy_name)
            
            # 生成资金曲线图
            if self.capital_history and self.timestamp_history:
                from chart_generator import ChartGenerator
                chart_gen = ChartGenerator()
                chart_gen.generate_performance_chart(
                    self.capital_history, 
                    self.timestamp_history, 
                    self.strategy_name
                )
            
        except Exception as e:
            print(f"⚠️ 生成Simple EMA策略图表时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def generate_strategy_chart(self):
        """
        使用统一的ChartGenerator生成策略图表
        """
        try:
            from chart_generator import ChartGenerator
            
            chart_gen = ChartGenerator()
            
            # 使用统一的图表生成器
            chart_gen.generate_strategy_chart(
                price_data=self.price_data_for_chart,
                trades=self.detailed_trades,
                strategy_name=self.strategy_name,
                timeframe=self.timeframe,
                ema_short=self.price_data_for_chart[self.ema_short_col] if self.ema_short_col in self.price_data_for_chart.columns else None,
                ema_long=self.price_data_for_chart[self.ema_long_col] if self.ema_long_col in self.price_data_for_chart.columns else None
            )
            
        except Exception as e:
            print(f"⚠️ 生成Simple EMA策略图表时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    



# 策略工厂函数
def create_simple_ema_strategy(config: Optional[Dict[str, Any]] = None) -> SimpleEMAStrategy:
    """
    创建简单EMA策略实例
    
    Args:
        config (Dict[str, Any], optional): 策略配置
        
    Returns:
        SimpleEMAStrategy: 策略实例
    """
    return SimpleEMAStrategy(config)


# 默认配置生成函数
def get_default_config() -> Dict[str, Any]:
    """
    获取默认配置
    
    注意：此函数已废弃，所有配置必须在config.json中定义
    
    Returns:
        Dict[str, Any]: 基本配置结构（不包含具体值）
    """
    return {
        # 以下参数必须在config.json中定义，不提供默认值
        'ema_short': None,  # 必须在config.json的strategies.simple_ema中定义
        'ema_long': None,   # 必须在config.json的strategies.simple_ema中定义
        'position_percentage': None,  # 必须在config.json的global中定义
        'timeframe': SimpleEMAStrategy.DEFAULT_TIMEFRAME,  # 可以有默认值的非关键参数
        'symbol': None,     # 必须在config.json的global中定义
        'start_date': None, # 必须在config.json的global中定义
        'end_date': None,   # 必须在config.json的global中定义
        'initial_capital': None,  # 必须在config.json的global中定义
        'leverage': None,   # 必须在config.json的global中定义
        'maintenance_margin_rate': None  # 必须在config.json的global中定义
    }


if __name__ == '__main__':
    """
    策略测试
    """
    print("简单EMA交叉策略测试")
    print("=" * 50)
    
    # 创建策略实例
    config = get_default_config()
    strategy = create_simple_ema_strategy(config)
    
    # 打印策略配置
    print("策略配置:")
    config_summary = strategy.get_strategy_config_summary()
    for key, value in config_summary.items():
        print(f"  {key}: {value}")
    
    print("\\n策略创建成功，可以通过StrategyRunner运行")