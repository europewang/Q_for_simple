#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略基类 - BaseStrategy
定义所有交易策略的通用接口和共同功能

该基类提供：
1. 统一的策略接口定义
2. 通用的数据处理方法
3. 标准的交易管理功能
4. 统一的结果输出格式
5. 可扩展的配置管理

作者：量化交易系统
版本：1.0
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import json
import warnings
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any

# 导入数据管理器
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_manager import data_manager

# 忽略警告信息
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class BaseStrategy(ABC):
    """
    策略基类
    
    所有具体策略都应该继承此基类，并实现抽象方法。
    提供通用的数据处理、交易管理和结果统计功能。
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化策略基类
        
        Args:
            config (Dict, optional): 策略配置参数字典
        """
        # ==================== 基础策略信息 ====================
        self.strategy_name = "基础策略"
        self.strategy_description = "策略基类，提供通用功能"
        self.strategy_version = "1.0"
        
        # ==================== 默认配置参数 ====================
        self._default_config = {
            # 交易基础参数
            'symbol': 'BTCUSDT',
            'start_date': '1 Oct, 2024',
            'end_date': '8 Oct, 2024',
            'initial_capital': 10000.0,
            'leverage': 1.0,
            'fee': 0.0004,
            'maintenance_margin_rate': 0.05,
            
            # EMA参数
            'ema_short': 9,
            'ema_long': 26,
            
            # 资金管理参数
            'position_percentage': 0.95,
            
            # 日志配置
            'logging_config': {
                'enable_detailed_log': True,
                'log_trades_to_file': True,
                'log_file_prefix': 'trades_detailed_log'
            },
            
            # 图表配置
            'chart_config': {
                'use_arrows_for_trades': True,
                'avoid_text_overlap': True,
                'chart_dpi': 300,
                'save_chart': True
            },
            
            # 输出配置
            'output_dir': 'output'
        }
        
        # 合并用户配置和默认配置
        self.config = self._merge_config(config or {})
        
        # 从配置中设置属性
        self._set_attributes_from_config()
        
        # ==================== 数据存储 ====================
        self.klines_1min = None
        self.klines_30min = None
        self.klines_1hour = None
        
        # ==================== 交易记录 ====================
        self.trades = []
        self.detailed_trades = []
        self.trade_log = []
        
        # ==================== 图表可视化数据 ====================
        self.ema_short_values = []  # 短期EMA值记录
        self.ema_long_values = []   # 长期EMA值记录
        self.capital_history = []   # 资金历史记录
        self.timestamp_history = [] # 时间戳历史记录
        self.price_data_for_chart = None  # 用于图表的价格数据
        
        # ==================== 交易状态变量 ====================
        self.reset_trading_state()
        
        # 确保输出目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 设置txt日志文件路径（将在initialize_txt_log中动态设置）
        self.txt_log_file = None
    
    def _merge_config(self, user_config: Dict) -> Dict:
        """
        合并用户配置和默认配置
        
        Args:
            user_config (Dict): 用户提供的配置
            
        Returns:
            Dict: 合并后的配置
        """
        merged_config = self._default_config.copy()
        
        # 递归合并嵌套字典
        def deep_merge(default_dict, user_dict):
            for key, value in user_dict.items():
                if key in default_dict and isinstance(default_dict[key], dict) and isinstance(value, dict):
                    deep_merge(default_dict[key], value)
                else:
                    default_dict[key] = value
        
        deep_merge(merged_config, user_config)
        return merged_config
    
    def _set_attributes_from_config(self):
        """从配置中设置对象属性"""
        # 基础交易参数
        self.symbol = self.config['symbol']
        self.start_date = self.config['start_date']
        self.end_date = self.config['end_date']
        self.initial_capital = self.config['initial_capital']
        self.leverage = self.config['leverage']
        self.fee = self.config['fee']
        self.maintenance_margin_rate = self.config['maintenance_margin_rate']
        
        # EMA参数
        self.ema_short = self.config['ema_short']
        self.ema_long = self.config['ema_long']
        
        # 资金管理参数
        self.position_percentage = self.config['position_percentage']
        
        # 配置对象
        self.logging_config = self.config['logging_config']
        self.chart_config = self.config['chart_config']
        self.output_dir = self.config['output_dir']
    
    def reset_trading_state(self):
        """重置交易状态"""
        self.capital = self.initial_capital
        self.position_size = 0
        self.position_value = 0
        self.entry_price = 0
        self.in_position = False
        self.current_signal = None
        self.last_signal = None
        
        # 清空交易记录
        self.trades.clear()
        self.detailed_trades.clear()
        self.trade_log.clear()
        
        # 清空图表数据
        self.ema_short_values.clear()
        self.ema_long_values.clear()
        self.capital_history.clear()
        self.timestamp_history.clear()
    
    # ==================== 抽象方法 - 子类必须实现 ====================
    
    @abstractmethod
    def get_strategy_specific_config(self) -> Dict:
        """
        获取策略特定的配置参数
        
        子类应该重写此方法，返回策略特有的配置参数
        
        Returns:
            Dict: 策略特定的配置参数
        """
        pass
    
    @abstractmethod
    def detect_signals(self, current_idx: int) -> Tuple[Optional[str], Optional[float]]:
        """
        检测交易信号
        
        Args:
            current_idx (int): 当前K线索引
            
        Returns:
            Tuple[Optional[str], Optional[float]]: (信号类型, 信号价格)
        """
        pass
    
    @abstractmethod
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
        pass
    
    # ==================== 通用数据处理方法 ====================
    
    def get_kline_data(self):
        """获取K线数据"""
        # 获取1分钟K线数据
        df_1min_raw = data_manager.get_kline_data(
            symbol=self.symbol,
            interval='1m',
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        if df_1min_raw is None or df_1min_raw.empty:
            raise ValueError("无法获取历史数据，请检查网络连接和API配置")
        
        # 设置索引并选择需要的列
        self.klines_1min = df_1min_raw.set_index('open_time')[['open', 'high', 'low', 'close']]
        
        # 重采样生成30分钟和1小时数据
        self.klines_30min = self._resample_to_30min(df_1min_raw)
        self.klines_1hour = self._resample_to_hourly(df_1min_raw)
    
    def _resample_to_30min(self, df_1min: pd.DataFrame) -> pd.DataFrame:
        """将1分钟数据重采样为30分钟数据"""
        df_1min_copy = df_1min.copy()
        df_1min_copy.set_index('open_time', inplace=True)
        
        # 重采样规则
        resample_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        df_30min = df_1min_copy.resample('30T').agg(resample_rules)
        df_30min.dropna(inplace=True)
        
        return df_30min
    
    def _resample_to_hourly(self, df_1min: pd.DataFrame) -> pd.DataFrame:
        """将1分钟数据重采样为1小时数据"""
        df_1min_copy = df_1min.copy()
        df_1min_copy.set_index('open_time', inplace=True)
        
        # 重采样规则
        resample_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        df_1hour = df_1min_copy.resample('1H').agg(resample_rules)
        df_1hour.dropna(inplace=True)
        
        return df_1hour
    
    def _calculate_ema(self, df: pd.DataFrame, span: int) -> pd.DataFrame:
        """计算EMA指标"""
        df = df.copy()
        df[f'ema_{span}'] = df['close'].ewm(span=span).mean()
        return df
    
    # ==================== 通用交易管理方法 ====================
    
    def _check_liquidation(self, current_price: float, timestamp: Any) -> bool:
        """
        检查是否触发爆仓
        
        Args:
            current_price (float): 当前价格
            timestamp: 时间戳
            
        Returns:
            bool: 是否触发爆仓
        """
        if not self.in_position or self.position_size == 0:
            return False
        
        # 计算当前持仓市值
        current_position_value = abs(self.position_size) * current_price
        
        # 计算未实现盈亏
        if self.current_signal == 'long':
            unrealized_pnl = (current_price - self.entry_price) * abs(self.position_size)
        else:  # short
            unrealized_pnl = (self.entry_price - current_price) * abs(self.position_size)
        
        # 计算保证金要求（基于当前持仓市值）
        required_margin = current_position_value / self.leverage
        
        # 计算维持保证金要求
        maintenance_margin = current_position_value * self.maintenance_margin_rate
        
        # 计算可用资金（当前资金 + 未实现盈亏）
        available_funds = self.capital + unrealized_pnl
        
        # 检查是否触发爆仓：可用资金小于维持保证金要求
        if available_funds < maintenance_margin:
            # 强制平仓
            self._force_close_position(current_price, timestamp, "爆仓强制平仓")
            return True
        
        return False
    
    def _force_close_position(self, price: float, timestamp: Any, reason: str):
        """强制平仓"""
        if not self.in_position:
            return
        
        # 计算盈亏
        if self.current_signal == 'long':
            profit = (price - self.entry_price) * abs(self.position_size)
        else:
            profit = (self.entry_price - price) * abs(self.position_size)
        
        # 扣除手续费
        fee_cost = abs(self.position_size) * price * self.fee
        profit -= fee_cost
        
        # 更新资金
        self.capital += profit
        
        # 记录交易
        trade_record = {
            'entry_time': getattr(self, 'position_entry_time', timestamp),
            'exit_time': timestamp,
            'signal': self.current_signal,
            'entry_price': self.entry_price,
            'exit_price': price,
            'position_size': self.position_size,
            'profit': profit,
            'reason': reason,
            'capital_after': self.capital
        }
        
        self.trades.append(trade_record)
        self.detailed_trades.append(trade_record)
        
        # 重置仓位状态
        self.position_size = 0
        self.position_value = 0
        self.entry_price = 0
        self.in_position = False
        self.current_signal = None
    
    # ==================== 通用结果统计方法 ====================
    
    def get_strategy_results(self) -> Dict:
        """
        获取策略回测结果
        
        Returns:
            Dict: 包含策略性能指标的字典
        """
        # 强制平仓未完成的交易
        if self.in_position and hasattr(self, 'klines_30min') and not self.klines_30min.empty:
            last_price = self.klines_30min.iloc[-1]['close']
            self._force_close_position(last_price, self.klines_30min.index[-1], '回测结束强制平仓')
        
        # 智能选择交易记录列表：优先使用detailed_trades，如果为空则使用trades
        trades_to_analyze = self.detailed_trades if self.detailed_trades else self.trades
        
        if not trades_to_analyze:
            return self._get_empty_results()
        
        # 计算基础统计 - 兼容不同的交易记录格式
        completed_trades = []
        initial_entry_trades = []  # 只计算初始入场的交易
        
        for trade in trades_to_analyze:
            # 检查交易是否已完成（有退出时间或状态为closed）
            has_exit_time = 'exit_time' in trade and trade['exit_time'] is not None
            is_closed = trade.get('status') == 'closed'
            if has_exit_time or is_closed:
                completed_trades.append(trade)
                # 只计算初始入场的交易作为真正的交易次数
                if trade.get('action') == '初始入场':
                    initial_entry_trades.append(trade)
        
        # 使用初始入场交易数作为总交易次数
        total_trades = len(initial_entry_trades) if initial_entry_trades else len(completed_trades)
        
        if total_trades == 0:
            return self._get_empty_results()
        
        # 计算盈利交易数量 - 基于完整交易计算
        profitable_trades = 0
        profits = []
        
        # 按trade_id分组计算完整交易的利润
        if initial_entry_trades:
            # 对于分批策略，按trade_id分组计算总利润
            trade_groups = {}
            for trade in self.detailed_trades:
                if trade.get('status') == 'closed':
                    trade_id = trade.get('trade_id')
                    if trade_id not in trade_groups:
                        trade_groups[trade_id] = []
                    trade_groups[trade_id].append(trade)
            
            # 计算每个完整交易的总利润
            for trade_id, trades in trade_groups.items():
                total_profit = sum(t.get('profit', 0) for t in trades)
                profits.append(total_profit)
                if total_profit > 0:
                    profitable_trades += 1
        else:
            # 对于简单策略，直接使用completed_trades
            for trade in completed_trades:
                profit = trade.get('profit', 0)
                if profit is not None:
                    profits.append(profit)
                    if profit > 0:
                        profitable_trades += 1
        
        # 计算性能指标
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        total_return = (self.capital - self.initial_capital) / self.initial_capital
        
        # 计算利润统计 - 修复：基于绝对金额而不是比例
        if profits:
            # 平均收益率：平均每笔交易的收益率
            avg_profit_per_trade = np.mean(profits)
            avg_profit = avg_profit_per_trade / self.initial_capital
            
            # 最大盈利和最大亏损：单笔交易的最大盈亏
            max_profit_amount = max(profits)
            max_loss_amount = min(profits)
            max_profit = max_profit_amount / self.initial_capital
            max_loss = max_loss_amount / self.initial_capital
        else:
            avg_profit = max_profit = max_loss = 0
        
        return {
            'strategy_name': self.strategy_name,
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'avg_profit': avg_profit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'final_capital': self.capital,
            'detailed_trades': self.detailed_trades
        }
    
    def _get_empty_results(self) -> Dict:
        """返回空结果"""
        return {
            'strategy_name': self.strategy_name,
            'total_trades': 0,
            'profitable_trades': 0,
            'win_rate': 0,
            'total_return': 0,
            'avg_profit': 0,
            'max_profit': 0,
            'max_loss': 0,
            'final_capital': self.capital,
            'detailed_trades': []
        }
    
    # ==================== 通用报告生成方法 ====================
    
    def print_results(self, results: Optional[Dict] = None):
        """打印回测结果"""
        if results is None:
            results = self.get_strategy_results()
        
        print(f"\n{'=' * 60}")
        print(f"{results['strategy_name']} - 回测报告")
        print(f"{'=' * 60}")
        print(f"总交易次数: {results['total_trades']}")
        print(f"胜率: {results['win_rate']:.2%}")
        print(f"总收益率: {results['total_return']:.2%}")
        print(f"平均收益率: {results['avg_profit']:.2%}")
        print(f"最大单笔盈利: {results['max_profit']:.2%}")
        print(f"最大单笔亏损: {results['max_loss']:.2%}")
        print(f"最终资金: ${results['final_capital']:.2f}")
        
        # 添加详细交易汇总
        self._print_detailed_trade_summary(results)
    
    def _print_detailed_trade_summary(self, results: Dict):
        """打印详细的交易汇总信息"""
        detailed_trades = results.get('detailed_trades', [])
        if not detailed_trades:
            return
        
        print(f"\n{'=' * 80}")
        print(f"📊 详细交易汇总 - 共{results['total_trades']}笔完整交易")
        print(f"{'=' * 80}")
        
        # 按trade_id分组，统计每笔完整交易
        trade_groups = {}
        for trade in detailed_trades:
            if trade.get('status') == 'closed':  # 只统计已完成的交易
                trade_id = trade.get('trade_id', 0)
                if trade_id not in trade_groups:
                    trade_groups[trade_id] = {
                        'stages': [],
                        'total_investment': 0,
                        'total_profit': 0,
                        'entry_time': None,
                        'exit_time': None,
                        'trade_type': trade.get('type', 'unknown')
                    }
                
                group = trade_groups[trade_id]
                group['stages'].append(trade)
                group['total_investment'] += trade.get('capital_allocated', 0)
                group['total_profit'] += trade.get('profit', 0)
                
                # 记录交易时间范围：初始入场时间作为开始，最晚的出场时间作为结束
                if trade.get('action') == '初始入场':
                    group['entry_time'] = trade.get('entry_time')
                if group['exit_time'] is None or trade.get('exit_time', '') > group['exit_time']:
                    group['exit_time'] = trade.get('exit_time')
        
        # 输出每笔完整交易的详细信息
        for trade_id, group in sorted(trade_groups.items()):
            profit_rate = (group['total_profit'] / group['total_investment'] * 100) if group['total_investment'] > 0 else 0
            profit_status = "✅ 盈利" if group['total_profit'] > 0 else "❌ 亏损" if group['total_profit'] < 0 else "⚖️ 持平"
            
            print(f"\n🔸 第{trade_id}次交易 ({group['trade_type'].upper()}) - {profit_status}")
            print(f"   📅 交易时间: {group['entry_time']} → {group['exit_time']}")
            print(f"   💵 总投入: ${group['total_investment']:.2f}")
            print(f"   💹 总盈亏: ${group['total_profit']:.2f}")
            print(f"   📊 收益率: {profit_rate:.2f}%")
            print(f"   📋 分批次数: {len(group['stages'])}次")
            
            # 显示每个分批的详细信息
            for i, stage in enumerate(group['stages'], 1):
                action = stage.get('action', f'第{i}次')
                investment = stage.get('capital_allocated', 0)
                profit = stage.get('profit', 0)
                entry_price = stage.get('entry_price', 0)
                exit_price = stage.get('exit_price', 0)
                print(f"      └─ {action}: 投入${investment:.2f}, 盈亏${profit:.2f}, 价格${entry_price:.2f}→${exit_price:.2f}")
        
        print(f"\n{'=' * 80}")
    
    def save_results_to_file(self, results: Optional[Dict] = None):
        """保存结果到文件"""
        if not self.logging_config.get('log_trades_to_file', True):
            return
        
        if results is None:
            results = self.get_strategy_results()
        
        # 构建文件名
        prefix = self.logging_config.get('log_file_prefix', 'trades_detailed_log')
        filename = f"{prefix}_{self.strategy_name.replace(' ', '_')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"交易日志已保存到: {filepath}")
    
    def write_to_txt_log(self, content: str, append: bool = True):
        """
        写入内容到txt日志文件
        
        Args:
            content (str): 要写入的内容
            append (bool): 是否追加模式，默认True
        """
        if not self.txt_log_file or not self.logging_config.get('log_trades_to_file', True):
            return
        
        try:
            mode = 'a' if append else 'w'
            with open(self.txt_log_file, mode, encoding='utf-8') as f:
                f.write(content + '\n')
        except Exception as e:
            print(f"写入txt日志文件失败: {e}")
    
    def initialize_txt_log(self):
        """初始化txt日志文件，写入策略信息头部"""
        # 动态设置txt日志文件路径（确保使用正确的策略名称）
        if self.logging_config.get('log_trades_to_file', True):
            log_prefix = self.logging_config.get('log_file_prefix', 'trades_detailed_log')
            self.txt_log_file = os.path.join(self.output_dir, f"{log_prefix}_{self.strategy_name.replace(' ', '_')}.txt")
        
        if not self.txt_log_file:
            return
        
        header = f"""{'='*80}
📊 {self.strategy_name} - 详细交易日志
{'='*80}
📅 回测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 交易标的: {self.symbol}
📈 数据周期: {self.start_date} → {self.end_date}
💰 初始资金: ${self.initial_capital:.2f}
🎯 杠杆倍数: {self.leverage}x
💸 手续费率: {self.fee:.4f}
{'='*80}

"""
        self.write_to_txt_log(header, append=False)
    
    def save_detailed_summary_to_txt(self, results: Dict):
        """
        将详细交易汇总保存到txt文件
        
        Args:
            results (Dict): 策略运行结果
        """
        if not self.txt_log_file:
            return
        
        # 重新写入整个文件，将回测报告放在开头
        self._rewrite_txt_log_with_summary(results)
    
    def _rewrite_txt_log_with_summary(self, results: Dict):
        """
        重新写入txt日志文件，将回测报告汇总放在开头
        
        Args:
            results (Dict): 策略运行结果
        """
        if not self.txt_log_file:
            return
        
        # 读取现有的交易详情内容（如果文件存在）
        existing_content = ""
        if os.path.exists(self.txt_log_file):
            try:
                with open(self.txt_log_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            except Exception as e:
                print(f"读取现有日志文件失败: {e}")
        
        # 构建新的文件内容
        # 1. 回测报告汇总（放在最开始）
        summary_content = f"""回测报告
{'='*60}
总交易次数: {results.get('total_trades', 0)}
胜率: {results.get('win_rate', 0):.2%}
总收益率: {results.get('total_return', 0):.2%}
平均收益率: {results.get('total_return', 0) / max(results.get('total_trades', 1), 1):.2%}
最大单笔盈利: {results.get('max_profit', 0):.2%}
最大单笔亏损: {results.get('max_loss', 0):.2%}
最终资金: ${results.get('final_capital', 0):.2f}
{'='*60}

"""
        
        # 2. 策略基本信息
        header = f"""{'='*80}
📊 {self.strategy_name} - 详细交易日志
{'='*80}
📅 回测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 交易标的: {self.symbol}
📈 数据周期: {self.start_date} → {self.end_date}
💰 初始资金: ${self.initial_capital:.2f}
🎯 杠杆倍数: {self.leverage}x
💸 手续费率: {self.fee:.4f}
{'='*80}

"""
        
        # 3. 详细交易汇总
        detailed_summary = f"{'='*80}\n"
        detailed_summary += f"📊 策略运行完成 - 详细汇总\n"
        detailed_summary += f"{'='*80}\n"
        detailed_summary += f"📈 总收益率: {results.get('total_return', 0):.2%}\n"
        detailed_summary += f"💰 最终资金: ${results.get('final_capital', 0):.2f}\n"
        detailed_summary += f"📊 总交易次数: {results.get('total_trades', 0)}\n"
        detailed_summary += f"✅ 盈利交易: {results.get('winning_trades', 0)}\n"
        detailed_summary += f"❌ 亏损交易: {results.get('losing_trades', 0)}\n"
        detailed_summary += f"🎯 胜率: {results.get('win_rate', 0):.2%}\n"
        detailed_summary += f"💹 最大单笔盈利: {results.get('max_profit', 0):.2%}\n"
        detailed_summary += f"📉 最大单笔亏损: {results.get('max_loss', 0):.2%}\n"
        detailed_summary += f"{'='*80}\n\n"
        
        # 4. 添加详细交易汇总
        detailed_trades = results.get('detailed_trades', [])
        if detailed_trades:
            detailed_summary += f"📊 详细交易汇总 - 共{results['total_trades']}笔完整交易\n"
            detailed_summary += f"{'='*80}\n"
            
            # 按trade_id分组，统计每笔完整交易
            trade_groups = {}
            for trade in detailed_trades:
                if trade.get('status') == 'closed':  # 只统计已完成的交易
                    trade_id = trade.get('trade_id', 0)
                    if trade_id not in trade_groups:
                        trade_groups[trade_id] = {
                            'stages': [],
                            'total_investment': 0,
                            'total_profit': 0,
                            'entry_time': None,
                            'exit_time': None,
                            'trade_type': trade.get('type', 'unknown')
                        }
                    
                    group = trade_groups[trade_id]
                    group['stages'].append(trade)
                    group['total_investment'] += trade.get('capital_allocated', 0)
                    group['total_profit'] += trade.get('profit', 0)
                    
                    # 记录交易时间范围：初始入场时间作为开始，最晚的出场时间作为结束
                    if trade.get('action') == '初始入场':
                        group['entry_time'] = trade.get('entry_time')
                    if group['exit_time'] is None or trade.get('exit_time', '') > group['exit_time']:
                        group['exit_time'] = trade.get('exit_time')
            
            # 输出每笔完整交易的详细信息
            for trade_id, group in sorted(trade_groups.items()):
                profit_rate = (group['total_profit'] / group['total_investment'] * 100) if group['total_investment'] > 0 else 0
                profit_status = "✅ 盈利" if group['total_profit'] > 0 else "❌ 亏损" if group['total_profit'] < 0 else "⚖️ 持平"
                
                detailed_summary += f"\n🔸 第{trade_id}次交易 ({group['trade_type'].upper()}) - {profit_status}\n"
                detailed_summary += f"   📅 交易时间: {group['entry_time']} → {group['exit_time']}\n"
                detailed_summary += f"   💵 总投入: ${group['total_investment']:.2f}\n"
                detailed_summary += f"   💹 总盈亏: ${group['total_profit']:.2f}\n"
                detailed_summary += f"   📊 收益率: {profit_rate:.2f}%\n"
                detailed_summary += f"   📋 分批次数: {len(group['stages'])}次\n"
                
                # 显示每个分批的详细信息
                for i, stage in enumerate(group['stages'], 1):
                    action = stage.get('action', f'第{i}次')
                    investment = stage.get('capital_allocated', 0)
                    profit = stage.get('profit', 0)
                    entry_price = stage.get('entry_price', 0)
                    exit_price = stage.get('exit_price', 0)
                    entry_time = stage.get('entry_time', '')
                    detailed_summary += f"      └─ {action} ({entry_time}): 投入${investment:.2f}, 盈亏${profit:.2f}, 价格${entry_price:.2f}→${exit_price:.2f}\n"
            
            detailed_summary += f"\n{'='*80}\n"
        
        # 5. 组合所有内容并写入文件
        final_content = summary_content + header + detailed_summary
        
        # 写入文件（覆盖模式）
        try:
            with open(self.txt_log_file, 'w', encoding='utf-8') as f:
                f.write(final_content)
            print(f"详细交易日志已保存到: {self.txt_log_file}")
        except Exception as e:
            print(f"写入txt日志文件失败: {e}")
    
    # ==================== 主要执行方法 ====================
    
    def run_backtest(self) -> Dict:
        """
        运行回测 - 模板方法
        
        定义回测的基本流程，具体的交易逻辑由子类实现
        
        Returns:
            Dict: 回测结果
        """
        try:
            # 0. 初始化txt日志文件
            self.initialize_txt_log()
            
            # 1. 获取数据
            self.get_kline_data()
            
            # 2. 计算技术指标
            self._calculate_indicators()
            
            # 3. 执行回测循环
            self._execute_backtest_loop()
            
            # 4. 生成结果
            results = self.get_strategy_results()
            
            # 5. 打印和保存结果
            self.print_results(results)
            self.save_results_to_file(results)
            
            # 6. 保存详细交易日志到txt文件
            self.save_detailed_summary_to_txt(results)
            
            # 7. 生成图表
            if self.chart_config.get('save_chart', True):
                self.plot_trading_chart()
            
            return results
            
        except Exception as e:
            print(f"回测执行出错: {str(e)}")
            raise
    
    def _calculate_indicators(self):
        """计算技术指标 - 子类可以重写"""
        if self.klines_30min is not None:
            self.klines_30min = self._calculate_ema(self.klines_30min, self.ema_short)
            self.klines_30min = self._calculate_ema(self.klines_30min, self.ema_long)
            self.klines_30min.dropna(inplace=True)
        
        if self.klines_1hour is not None:
            self.klines_1hour = self._calculate_ema(self.klines_1hour, self.ema_short)
            self.klines_1hour = self._calculate_ema(self.klines_1hour, self.ema_long)
            self.klines_1hour.dropna(inplace=True)
    
    @abstractmethod
    def _execute_backtest_loop(self):
        """执行回测循环 - 子类必须实现"""
        pass
    
    def plot_trading_chart(self):
        """绘制交易图表"""
        try:
            # 导入图表生成器
            from chart_generator import ChartGenerator
            
            chart_gen = ChartGenerator()
            
            # 准备价格数据
            price_data = self.price_data_for_chart
            if price_data is None:
                # 使用30分钟数据作为默认
                price_data = self.klines_30min
            
            if price_data is None or price_data.empty:
                print("⚠️ 没有价格数据，无法生成图表")
                return
            
            # 准备EMA数据
            ema_short = None
            ema_long = None
            
            if self.ema_short_values:
                ema_short = pd.Series(self.ema_short_values, index=price_data.index[:len(self.ema_short_values)])
            elif f'ema_{self.ema_short}' in price_data.columns:
                ema_short = price_data[f'ema_{self.ema_short}']
            
            if self.ema_long_values:
                ema_long = pd.Series(self.ema_long_values, index=price_data.index[:len(self.ema_long_values)])
            elif f'ema_{self.ema_long}' in price_data.columns:
                ema_long = price_data[f'ema_{self.ema_long}']
            
            # 生成主要交易图表
            chart_gen.generate_strategy_chart(
                price_data=price_data,
                trades=self.detailed_trades,
                strategy_name=self.strategy_name,
                ema_short=ema_short,
                ema_long=ema_long,
                timeframe="30min"
            )
            
            # 生成交易分析图表
            if self.detailed_trades:
                chart_gen.generate_trade_analysis_chart(self.detailed_trades, self.strategy_name)
            
            # 生成资金曲线图
            if self.capital_history and self.timestamp_history:
                chart_gen.generate_performance_chart(
                    self.capital_history, 
                    self.timestamp_history, 
                    self.strategy_name
                )
            
        except ImportError:
            print("⚠️ 无法导入图表生成器，跳过图表生成")
        except Exception as e:
            print(f"⚠️ 生成图表时出错: {str(e)}")
    
    def record_chart_data(self, timestamp, ema_short_val=None, ema_long_val=None):
        """
        记录用于图表的数据
        
        Args:
            timestamp: 时间戳
            ema_short_val: 短期EMA值
            ema_long_val: 长期EMA值
        """
        # 记录时间戳和资金
        self.timestamp_history.append(timestamp)
        self.capital_history.append(self.capital)
        
        # 记录EMA值
        if ema_short_val is not None:
            self.ema_short_values.append(ema_short_val)
        if ema_long_val is not None:
            self.ema_long_values.append(ema_long_val)