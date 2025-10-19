#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分批入场EMA交叉策略 - 重构版本
基于策略模式重构，继承自BaseStrategy

策略特点：
1. 使用30分钟EMA9/EMA26交叉作为主要信号
2. 分批入场：首次37%，后续按1%, 2%, 4%, 8%, 16%, 32%逐步加仓
3. 在新的低点（做多）或高点（做空）时触发加仓
4. 反向交叉信号时全部平仓

作者：量化交易系统
版本：2.0 (重构版本)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import os
import sys

# 导入基础策略类和配置管理器
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from base_strategy import BaseStrategy
from config_manager import ConfigManager, StagedEMAConfig

class StagedEMAStrategy(BaseStrategy):
    """
    分批入场EMA交叉策略类
    
    该策略基于EMA交叉信号进行分批入场交易，特点是：
    1. 首次入场使用37%资金
    2. 后续在有利价格点按递增比例加仓
    3. 反向交叉时全部平仓
    
    价格使用逻辑：
    - 入场价格：使用交叉点所在K线的收盘价格
    - 加仓价格：使用当前1分钟K线的收盘价格
    - 出场价格：使用当前1分钟K线的收盘价格
    - 爆仓检测：使用当前1分钟K线的收盘价格
    """
    
    # ==================== 策略特有参数配置 ====================
    # 分批入场比例配置 - 可在类顶部修改
    LONG_ENTRY_STAGES = [0.37, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32]  # 做多分批比例
    SHORT_ENTRY_STAGES = [0.37, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32]  # 做空分批比例
    
    # EMA参数配置 - 必须在config.json中定义
    # EMA_SHORT = 9      # 已移除，必须从config读取
    # EMA_LONG = 26      # 已移除，必须从config读取
    
    # 仓位管理参数 - position_percentage属于global配置，不允许在策略中定义
    # POSITION_PERCENTAGE = 0.95  # 已移除，必须从global config读取
    
    # 时间框架配置
    TIMEFRAME = '30min'         # 主要时间框架
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化分批入场EMA策略
        
        Args:
            config (Dict, optional): 策略配置参数
        """
        # 调用父类初始化
        super().__init__(config)
        
        # 设置策略基本信息（必须在父类初始化之后设置，避免被覆盖）
        self.strategy_name = "分批入场EMA交叉策略"
        self.strategy_description = "基于EMA交叉的分批入场策略，支持逐步加仓"
        self.strategy_version = "2.0"
        
        # ==================== 策略特有参数 ====================
        # 从配置中获取参数 - 必须在config.json中定义，不允许默认值
        self.ema_short = self.config.get('ema_short')
        self.ema_long = self.config.get('ema_long')
        
        if self.ema_short is None or self.ema_long is None:
            raise ValueError("ema_short和ema_long必须在config.json的strategies配置中定义")
        
        # position_percentage属于global配置
        self.position_percentage = self.config.get('position_percentage')
        if self.position_percentage is None:
            raise ValueError("position_percentage必须在config.json的global配置中定义")
        # 杠杆倍数必须从配置文件读取，不设置默认值
        self.leverage = self.config.get('leverage')
        self.timeframe = self.config.get('timeframe', self.TIMEFRAME)
        
        # 分批入场参数
        self.long_entry_stages = self.config.get('long_entry_stages', self.LONG_ENTRY_STAGES.copy())
        self.short_entry_stages = self.config.get('short_entry_stages', self.SHORT_ENTRY_STAGES.copy())
        
        # ==================== 分批入场状态变量 ====================
        self.current_stage_index = 0           # 当前入场阶段索引
        self.current_stage_capital_allocated = 0  # 当前已分配的资金
        self.last_low = 0                      # 用于做多加仓的最低价记录
        self.last_high = 0                     # 用于做空加仓的最高价记录
        self.current_signal = None             # 当前信号类型
        self.trade_count = 0                   # 交易计数器
        
        # ==================== 新规则相关状态变量 ====================
        self.entry_crossover_price = 0         # 入场时的交叉点价格
        self.pending_signal = None              # 待执行的信号
        self.pending_signal_type = None         # 待执行的信号类型
        self.pending_signal_price = 0           # 待执行的信号价格
        self.current_30min_candle_start = None  # 当前30分钟K线开始时间
        self.minute_lows_for_long = []          # 做多时的分钟级最低价记录
        self.minute_highs_for_short = []        # 做空时的分钟级最高价记录
        
        print(f"策略初始化完成:")
        print(f"  - EMA参数: {self.ema_short}/{self.ema_long}")
        print(f"  - 仓位比例: {self.position_percentage*100:.1f}%")
        print(f"  - 杠杆倍数: {self.leverage}x")
        print(f"  - 时间框架: {self.timeframe}")
        print(f"  - 分批入场阶段: {len(self.long_entry_stages)}个")
    
    # ==================== 技术指标计算 ====================
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            df (pd.DataFrame): K线数据
            
        Returns:
            pd.DataFrame: 包含技术指标的数据
        """
        df = df.copy()
        
        # 计算EMA
        df[f'ema_{self.ema_short}'] = df['close'].ewm(span=self.ema_short).mean()
        df[f'ema_{self.ema_long}'] = df['close'].ewm(span=self.ema_long).mean()
        
        return df
    
    def detect_ema_crossover(self, df: pd.DataFrame, current_idx: int) -> Tuple[Optional[str], Optional[float]]:
        """
        检测EMA交叉信号
        
        Args:
            df (pd.DataFrame): 包含EMA指标的数据
            current_idx (int): 当前K线索引
            
        Returns:
            Tuple[Optional[str], Optional[float]]: (信号类型, 信号价格)
        """
        if current_idx < 1:
            return None, None
        
        # 获取当前和前一根K线的EMA值
        current_ema_short = df.iloc[current_idx][f'ema_{self.ema_short}']
        current_ema_long = df.iloc[current_idx][f'ema_{self.ema_long}']
        prev_ema_short = df.iloc[current_idx - 1][f'ema_{self.ema_short}']
        prev_ema_long = df.iloc[current_idx - 1][f'ema_{self.ema_long}']
        
        # 检测金叉（做多信号）
        if prev_ema_short <= prev_ema_long and current_ema_short > current_ema_long:
            # 返回交叉点所在K线的收盘价格（用于入场）
            return 'long', df.iloc[current_idx]['close']
        
        # 检测死叉（做空信号）
        elif prev_ema_short >= prev_ema_long and current_ema_short < current_ema_long:
            # 返回交叉点所在K线的收盘价格（用于入场）
            return 'short', df.iloc[current_idx]['close']
        
        return None, None
    
    # ==================== 分批入场逻辑 ====================
    
    def should_add_to_position(self, current_price: float, trade_type: str) -> bool:
        """
        判断是否应该加仓 - 基于1分钟K线的新低点/新高点
        
        Args:
            current_price (float): 当前价格
            trade_type (str): 交易类型
            
        Returns:
            bool: 是否应该加仓
        """
        # 检查基本条件
        if not self.in_position or self.current_stage_index >= len(self.long_entry_stages):
            return False
        
        if self.current_stage_capital_allocated >= self.initial_capital:
            return False
        
        # 检查价格条件 - 基于1分钟K线的新低点/新高点
        if trade_type == 'long':
            # 做多：当前价格创造新低点时加仓
            if len(self.minute_lows_for_long) == 0 or current_price < min(self.minute_lows_for_long):
                self.minute_lows_for_long.append(current_price)
                return True
        elif trade_type == 'short':
            # 做空：当前价格创造新高点时加仓
            if len(self.minute_highs_for_short) == 0 or current_price > max(self.minute_highs_for_short):
                self.minute_highs_for_short.append(current_price)
                return True
        
        return False
    
    def open_position_staged(self, price: float, timestamp: Any, trade_type: str):
        """
        分批开仓 - 首次入场
        
        Args:
            price (float): 入场价格
            timestamp: 入场时间
            trade_type (str): 交易类型
        """
        if self.in_position:
            return
        
        # 初始化分批入场参数
        self.current_stage_index = 0
        self.current_stage_capital_allocated = 0
        self.last_low = price
        self.last_high = price
        self.current_signal = trade_type
        
        # 记录入场交叉点价格（用于出场条件1）
        self.entry_crossover_price = price
        
        # 初始化1分钟级别的价格跟踪
        self.minute_lows_for_long = []
        self.minute_highs_for_short = []
        
        # 计算首次入场资金 - 基于当前可用资金
        stage_percentage = (self.long_entry_stages[self.current_stage_index] 
                          if trade_type == 'long' 
                          else self.short_entry_stages[self.current_stage_index])
        
        capital_to_use = self.capital * self.position_percentage * stage_percentage
        
        if capital_to_use > 0:
            # 计算仓位和手续费
            size = (capital_to_use * self.leverage) / price
            fee_cost = size * price * self.fee
            
            # 更新仓位状态
            self.position_size += size
            self.entry_price = price
            self.capital -= (capital_to_use + fee_cost)  # 扣除投入资金和手续费
            self.in_position = True
            self.current_side = trade_type
            self.current_stage_capital_allocated += capital_to_use
            self.trade_count += 1
            
            # 记录交易
            trade_record = {
                'trade_id': self.trade_count,
                'type': trade_type,
                'entry_time': timestamp,
                'entry_price': price,
                'position_size': size,
                'capital_allocated': capital_to_use,
                'fee': fee_cost,
                'exit_time': None,
                'exit_price': None,
                'profit': None,
                'status': 'open',
                'action': '初始入场'
            }
            self.detailed_trades.append(trade_record)
            
            # 详细的初始入场日志
            log_content = f"\n{'='*80}\n"
            log_content += f"🚀 第{self.trade_count}次交易 - 初始入场 {trade_type.upper()}\n"
            log_content += f"{'='*80}\n"
            log_content += f"📅 时间: {timestamp}\n"
            log_content += f"💰 当前资金: ${self.capital:.2f}\n"
            log_content += f"📈 入场价格: ${price:.2f}\n"
            log_content += f"💵 投入金额: ${capital_to_use:.2f}\n"
            log_content += f"📊 仓位大小: {size:.6f}\n"
            log_content += f"💸 手续费: ${fee_cost:.2f}\n"
            log_content += f"🎯 杠杆倍数: {self.leverage}x\n"
            log_content += f"📋 分批阶段: 1/{len(self.long_entry_stages)}\n"
            log_content += f"{'='*80}"
            
            # 输出到控制台
            print(log_content)
            
            # 写入txt日志文件
            self.write_to_txt_log(log_content)
            
            # 移动到下一个入场阶段
            self.current_stage_index += 1
    
    def add_to_position(self, price: float, timestamp: Any, trade_type: str):
        """
        加仓函数
        
        Args:
            price (float): 加仓价格
            timestamp: 加仓时间
            trade_type (str): 交易类型
        """
        if not self.in_position or self.current_stage_index >= len(self.long_entry_stages):
            return
        
        # 计算加仓资金 - 基于当前可用资金
        stage_percentage = (self.long_entry_stages[self.current_stage_index] 
                          if trade_type == 'long' 
                          else self.short_entry_stages[self.current_stage_index])
        
        capital_to_add = self.capital * stage_percentage
        
        # 确保有足够的资金进行加仓
        if capital_to_add <= 0 or capital_to_add > self.capital:
            return
        
        # 计算加仓仓位和手续费
        size_to_add = (capital_to_add * self.leverage) / price
        fee_cost = size_to_add * price * self.fee
        
        # 更新平均入场价格
        self.entry_price = ((self.entry_price * self.position_size + price * size_to_add) / 
                           (self.position_size + size_to_add))
        
        # 更新仓位状态
        self.position_size += size_to_add
        self.capital -= (capital_to_add + fee_cost)  # 扣除投入资金和手续费
        self.current_stage_capital_allocated += capital_to_add
        
        # 记录加仓交易（注意：加仓不增加trade_count，因为它属于同一笔交易）
        trade_record = {
            'trade_id': self.trade_count,  # 使用当前交易ID，不增加计数（加仓属于同一笔交易）
            'type': trade_type,            # 交易方向：long/short
            'entry_time': timestamp,       # 加仓时间戳
            'entry_price': price,          # 加仓价格
            'position_size': size_to_add,  # 本次加仓的仓位大小
            'capital_allocated': capital_to_add,  # 本次加仓投入的资金
            'fee': fee_cost,               # 本次加仓产生的手续费
            'exit_time': None,             # 平仓时间（加仓时未平仓，留空）
            'exit_price': None,            # 平仓价格（加仓时未平仓，留空）
            'profit': None,                # 盈亏（加仓时未实现，留空）
            'status': 'open',              # 交易状态：open/closed
            'action': f'第{self.current_stage_index}次加仓'  # 操作描述
        }
        self.detailed_trades.append(trade_record)
        
        # 详细的加仓日志
        log_content = f"\n{'='*80}\n"
        log_content += f"📈 第{self.trade_count}次交易 - 第{self.current_stage_index}次加仓 {trade_type.upper()}\n"
        log_content += f"{'='*80}\n"
        log_content += f"📅 时间: {timestamp}\n"
        log_content += f"💰 当前资金: ${self.capital:.2f}\n"
        log_content += f"📈 加仓价格: ${price:.2f}\n"
        log_content += f"💵 本次投入: ${capital_to_add:.2f}\n"
        log_content += f"📊 本次仓位: {size_to_add:.6f}\n"
        log_content += f"💸 手续费: ${fee_cost:.2f}\n"
        log_content += f"🔄 累计投入: ${self.current_stage_capital_allocated:.2f}\n"
        log_content += f"📊 总仓位: {self.position_size:.6f}\n"
        log_content += f"💹 平均价格: ${self.entry_price:.2f}\n"
        log_content += f"📋 分批阶段: {self.current_stage_index + 1}/{len(self.long_entry_stages)}\n"
        log_content += f"{'='*80}"
        
        # 输出到控制台
        print(log_content)
        
        # 写入txt日志文件
        self.write_to_txt_log(log_content)
        
        # 移动到下一个入场阶段
        self.current_stage_index += 1
    
    # ==================== 新的出场条件检测方法 ====================
    
    def check_exit_condition_1_crossover_price(self, current_price: float) -> bool:
        """
        出场条件1：突破入场交叉点价格
        
        Args:
            current_price (float): 当前收盘价
            
        Returns:
            bool: 是否满足出场条件
        """
        if not self.in_position or self.entry_crossover_price == 0:
            return False
        
        if self.current_side == 'long':
            # 做多：当前价格跌破入场交叉点价格
            return current_price < self.entry_crossover_price
        elif self.current_side == 'short':
            # 做空：当前价格突破入场交叉点价格
            return current_price > self.entry_crossover_price
        
        return False
    
    def check_exit_condition_2_three_candles(self, df_30min: pd.DataFrame, current_idx: int) -> bool:
        """
        出场条件2：突破前三根同色K线底部/顶部
        
        Args:
            df_30min (pd.DataFrame): 30分钟K线数据
            current_idx (int): 当前30分钟K线索引
            
        Returns:
            bool: 是否满足出场条件
        """
        if not self.in_position or current_idx < 3:
            return False
        
        # 获取当前价格（使用当前30分钟K线的收盘价）
        current_price = df_30min.iloc[current_idx]['close']
        
        if self.current_side == 'long':
            # 做多：寻找前三根绿色K线（上升，close > open）的最低价
            green_lows = []
            for i in range(current_idx - 3, current_idx):
                if i >= 0:
                    candle = df_30min.iloc[i]
                    if candle['close'] > candle['open']:  # 绿色K线
                        green_lows.append(candle['low'])
            
            if len(green_lows) >= 3:
                min_green_low = min(green_lows[-3:])  # 取最近三根绿色K线的最低价
                return current_price < min_green_low
                
        elif self.current_side == 'short':
            # 做空：寻找前三根红色K线（下降，close < open）的最高价
            red_highs = []
            for i in range(current_idx - 3, current_idx):
                if i >= 0:
                    candle = df_30min.iloc[i]
                    if candle['close'] < candle['open']:  # 红色K线
                        red_highs.append(candle['high'])
            
            if len(red_highs) >= 3:
                max_red_high = max(red_highs[-3:])  # 取最近三根红色K线的最高价
                return current_price > max_red_high
        
        return False
    
    def check_exit_condition_3_ema_half_candle(self, df_30min: pd.DataFrame, current_idx: int) -> bool:
        """
        出场条件3：突破EMA9超过一半K线大小
        
        Args:
            df_30min (pd.DataFrame): 30分钟K线数据
            current_idx (int): 当前30分钟K线索引
            
        Returns:
            bool: 是否满足出场条件
        """
        if not self.in_position or current_idx < 0:
            return False
        
        current_candle = df_30min.iloc[current_idx]
        current_price = current_candle['close']
        current_ema9 = current_candle[f'ema_{self.ema_short}']
        
        # 计算当前30分钟K线大小
        current_candle_size = current_candle['high'] - current_candle['low']
        half_candle_size = 0.5 * current_candle_size
        
        if self.current_side == 'long':
            # 做多：价格跌破 EMA9 - 0.5 * candle_size
            threshold = current_ema9 - half_candle_size
            return current_price < threshold
        elif self.current_side == 'short':
            # 做空：价格突破 EMA9 + 0.5 * candle_size
            threshold = current_ema9 + half_candle_size
            return current_price > threshold
        
        return False
    
    def check_exit_condition_4_reverse_crossover(self, df_30min: pd.DataFrame, current_idx: int) -> bool:
        """
        出场条件4：反向EMA交叉
        
        Args:
            df_30min (pd.DataFrame): 30分钟K线数据
            current_idx (int): 当前30分钟K线索引
            
        Returns:
            bool: 是否满足出场条件
        """
        if not self.in_position or current_idx < 1:
            return False
        
        # 检测反向交叉
        signal, _ = self.detect_ema_crossover(df_30min, current_idx)
        
        if signal and signal != self.current_side:
            return True
        
        return False
    
    def check_all_exit_conditions(self, df_30min: pd.DataFrame, current_idx: int, minute_price: float = None) -> Tuple[bool, str]:
        """
        检查所有出场条件
        
        Args:
            df_30min (pd.DataFrame): 30分钟K线数据
            current_idx (int): 当前30分钟K线索引
            minute_price (float, optional): 1分钟级别的当前价格
            
        Returns:
            Tuple[bool, str]: (是否需要出场, 出场原因)
        """
        if not self.in_position:
            return False, ""
        
        # 使用1分钟价格或30分钟收盘价
        current_price = minute_price if minute_price is not None else df_30min.iloc[current_idx]['close']
        
        # 条件1：突破入场交叉点价格
        if self.check_exit_condition_1_crossover_price(current_price):
            return True, "突破入场交叉点价格"
        
        # 条件2：突破前三根同色K线底部/顶部
        if self.check_exit_condition_2_three_candles(df_30min, current_idx):
            return True, "突破前三根同色K线底部/顶部"
        
        # 条件3：突破EMA9超过一半K线大小
        if self.check_exit_condition_3_ema_half_candle(df_30min, current_idx):
            return True, "突破EMA9超过一半K线大小"
        
        # 条件4：反向EMA交叉
        if self.check_exit_condition_4_reverse_crossover(df_30min, current_idx):
            return True, "反向EMA交叉"
        
        return False, ""
    
    def close_all_positions(self, price: float, timestamp: Any, reason: str):
        """
        平仓所有持仓
        
        Args:
            price (float): 平仓价格
            timestamp: 平仓时间
            reason (str): 平仓原因
        """
        if not self.in_position or self.position_size <= 0:
            return
        
        # 计算总盈亏
        if self.current_side == 'long':
            total_profit = (price - self.entry_price) * self.position_size
        else:  # short
            total_profit = (self.entry_price - price) * self.position_size
        
        # 计算手续费
        fee_cost = self.position_size * price * self.fee
        total_profit -= fee_cost
        
        # 更新资金 - 释放保证金并加上盈亏
        self.capital += (self.current_stage_capital_allocated + total_profit)
        
        # 计算总投入资金，用于按比例分配profit
        total_capital_allocated = sum(trade.get('capital_allocated', 0) 
                                    for trade in self.detailed_trades 
                                    if trade.get('status') == 'open')
        
        # 更新所有未平仓的交易记录
        for trade in self.detailed_trades:
            if trade.get('status') == 'open':
                trade['exit_time'] = timestamp
                trade['exit_price'] = price
                
                # 按资金比例分配profit
                if total_capital_allocated > 0:
                    capital_ratio = trade.get('capital_allocated', 0) / total_capital_allocated
                    trade['profit'] = total_profit * capital_ratio
                else:
                    trade['profit'] = 0
                    
                trade['status'] = 'closed'
        
        # 详细的平仓日志
        log_content = f"\n{'='*80}\n"
        log_content += f"🏁 第{self.trade_count}次交易 - 全部平仓 {self.current_side.upper()}\n"
        log_content += f"{'='*80}\n"
        log_content += f"📅 平仓时间: {timestamp}\n"
        log_content += f"📈 平仓价格: ${price:.2f}\n"
        log_content += f"📊 平仓仓位: {self.position_size:.6f}\n"
        log_content += f"💰 平仓前资金: ${self.capital - total_profit:.2f}\n"
        log_content += f"💸 手续费: ${fee_cost:.2f}\n"
        log_content += f"💵 总投入: ${total_capital_allocated:.2f}\n"
        log_content += f"💹 总盈亏: ${total_profit:.2f}\n"
        log_content += f"📊 收益率: {(total_profit / total_capital_allocated * 100):.2f}%" if total_capital_allocated > 0 else "0.00%"
        log_content += f"\n💰 平仓后资金: ${self.capital:.2f}\n"
        log_content += f"📋 平仓原因: {reason}\n"
        log_content += f"{'='*80}"
        
        # 输出到控制台
        print(log_content)
        
        # 写入txt日志文件
        self.write_to_txt_log(log_content)
        
        # 重置状态
        self.position_size = 0
        self.entry_price = 0
        self.in_position = False
        self.current_side = None
        self.current_stage_index = 0
        self.current_stage_capital_allocated = 0
        self.current_signal = None
        
        # 重置新增的状态变量
        self.entry_crossover_price = 0
        self.pending_signal = None
        self.pending_signal_type = None
        self.pending_signal_price = 0
        self.current_30min_candle_start = None
        self.minute_lows_for_long = []
        self.minute_highs_for_short = []
    
    # ==================== 实现BaseStrategy抽象方法 ====================
    
    def get_strategy_specific_config(self) -> Dict:
        """获取策略特定配置"""
        return {
            'ema_short': self.ema_short,            # 短期EMA周期（默认9）
            'ema_long': self.ema_long,              # 长期EMA周期（默认26）
            'position_percentage': self.position_percentage,  # 总仓位比例（默认95%）
            'leverage': self.leverage,              # 杠杆倍数（从配置读取）
            'timeframe': self.timeframe,            # 主时间框架（默认30min）
            'long_entry_stages': self.long_entry_stages,      # 做多分批入场比例列表
            'short_entry_stages': self.short_entry_stages   # 做空分批入场比例列表
        }
    
    def plot_strategy_specific_indicators(self, ax, df: pd.DataFrame):
        """
        绘制策略特定的技术指标
        
        Args:
            ax: matplotlib轴对象
            df (pd.DataFrame): 包含指标的数据
        """
        # 绘制EMA线
        ema_short_col = f'EMA{self.ema_short}'
        ema_long_col = f'EMA{self.ema_long}'
        
        if ema_short_col in df.columns:
            ax.plot(df.index, df[ema_short_col], 
                   color='blue', linewidth=2, label=f'EMA{self.ema_short}', alpha=0.8)
        
        if ema_long_col in df.columns:
            ax.plot(df.index, df[ema_long_col], 
                   color='red', linewidth=2, label=f'EMA{self.ema_long}', alpha=0.8)
    
    def plot_trading_chart(self):
        """
        重写父类的画图方法，使用staged_ema策略专用的画图功能
        """
        try:
            print("正在生成Staged EMA策略专用图表...")
            
            # 使用现有的chart_generator，但确保它能正确处理staged_ema的数据结构
            from chart_generator import ChartGenerator
            
            chart_gen = ChartGenerator()
            
            # 准备价格数据
            price_data = self.price_data_for_chart
            if price_data is None:
                price_data = self.klines_30min
            
            if price_data is None or price_data.empty:
                print("⚠️ 没有价格数据，无法生成图表")
                return
            
            # 准备EMA数据
            ema_short = None
            ema_long = None
            
            # 使用正确的列名格式（与calculate_indicators方法中的格式一致）
            ema_short_col = f'ema_{self.ema_short}'
            ema_long_col = f'ema_{self.ema_long}'
            
            if ema_short_col in price_data.columns:
                ema_short = price_data[ema_short_col]
            if ema_long_col in price_data.columns:
                ema_long = price_data[ema_long_col]
            
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
            
        except Exception as e:
            print(f"⚠️ 生成Staged EMA策略图表时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def detect_signals(self, current_idx: int) -> Tuple[Optional[str], Optional[float]]:
        """检测交易信号"""
        return self.detect_ema_crossover(self.klines_30min, current_idx)
    
    def execute_trading_logic(self, signal: str, price: float, timestamp: Any) -> bool:
        """执行交易逻辑"""
        try:
            # 如果有反向信号，先平仓
            if self.in_position and self.current_signal != signal:
                self.close_all_positions(price, timestamp, "反向交叉信号")
            
            # 如果无持仓，开新仓
            if not self.in_position:
                self.open_position_staged(price, timestamp, signal)
            
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
        
        # 用于存储待执行的信号
        pending_signal = None
        pending_signal_type = None
        
        # 遍历30分钟K线
        for i in range(len(self.klines_30min)):
            candle_30min = self.klines_30min.iloc[i]
            
            # 获取对应的1分钟数据进行爆仓检测和加仓检测
            df_1min_period = self.get_minute_data_for_period(self.klines_1min, candle_30min)
            
            # 在每个1分钟K线上检查爆仓、出场条件和加仓机会
            if len(df_1min_period) > 0:
                for _, min_candle in df_1min_period.iterrows():
                    # 检查爆仓
                    if self._check_liquidation(min_candle['close'], min_candle.name):
                        break
                    
                    # 检查新的出场条件（使用1分钟价格）
                    if self.in_position:
                        should_exit, exit_reason = self.check_all_exit_conditions(
                            self.klines_30min, i, min_candle['close']
                        )
                        if should_exit:
                            self.close_all_positions(min_candle['close'], min_candle.name, exit_reason)
                            break
                    
                    # 检查加仓机会
                    if (self.in_position and self.current_signal and 
                        self.should_add_to_position(min_candle['close'], self.current_signal)):
                        self.add_to_position(min_candle['close'], min_candle.name, self.current_signal)
            
            # 如果有待执行的信号，使用交叉点所在K线的收盘价格执行入场
            if pending_signal and len(df_1min_period) > 0:
                # 使用交叉点所在K线的收盘价格（pending_signal就是交叉点价格）
                execution_price = pending_signal
                # 使用当前30分钟K线的时间戳作为执行时间
                execution_timestamp = candle_30min.name
                
                # 判断是开仓还是平仓
                if self.in_position and self.current_signal != pending_signal_type:
                    # 反向信号，执行平仓（平仓使用当前价格，不是交叉点价格）
                    first_1min_candle = df_1min_period.iloc[0]
                    close_price = first_1min_candle['close']
                    close_timestamp = first_1min_candle.name
                    self.close_all_positions(close_price, close_timestamp, "反向交叉信号")
                
                # 如果无持仓，执行开仓（开仓使用交叉点价格）
                if not self.in_position:
                    self.open_position_staged(execution_price, execution_timestamp, pending_signal_type)
                
                # 清除待执行信号
                pending_signal = None
                pending_signal_type = None
            
            # 检测交易信号
            signal, signal_price = self.detect_signals(i)
            
            if signal:
                # 将信号标记为待执行，在下一个30分钟周期执行
                pending_signal = signal_price
                pending_signal_type = signal
        
        # 如果回测结束时还有持仓，强制平仓
        if self.in_position:
            last_price = self.klines_1min.iloc[-1]['close']
            last_time = self.klines_1min.index[-1]
            self.close_all_positions(last_price, last_time, "回测结束强制平仓")

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
        # 计算结束时间（30分钟后，但不包含下一个30分钟周期的开始时间）
        end_time = start_time + pd.Timedelta(minutes=30)
        
        # df_minute的open_time也是索引，使用index进行筛选
        # 注意：使用 < end_time 而不是 <= end_time，避免包含下一个30分钟周期的第一根1分钟K线
        mask = (df_minute.index >= start_time) & (df_minute.index < end_time)
        return df_minute[mask]


def create_staged_ema_strategy(config: Optional[Dict] = None) -> StagedEMAStrategy:
    """
    创建分批入场EMA策略实例的工厂函数
    
    Args:
        config (Dict, optional): 策略配置参数
        
    Returns:
        StagedEMAStrategy: 策略实例
    """
    return StagedEMAStrategy(config)


def get_default_config() -> Dict:
    """
    获取默认配置
    
    注意：此函数已废弃，所有配置必须在config.json中定义
    
    Returns:
        Dict: 基本配置结构（不包含具体值）
    """
    return {
        'strategy_type': 'staged_ema',
        'strategy_name': '分批入场EMA交叉策略',
        # 以下参数必须在config.json中定义，不提供默认值
        'ema_short': None,  # 必须在config.json的strategies.staged_ema中定义
        'ema_long': None,   # 必须在config.json的strategies.staged_ema中定义
        'position_percentage': None,  # 必须在config.json的global中定义
        'leverage': None,   # 必须在config.json的global中定义
        'timeframe': StagedEMAStrategy.TIMEFRAME,  # 可以有默认值的非关键参数
        'long_entry_stages': StagedEMAStrategy.LONG_ENTRY_STAGES.copy(),
        'short_entry_stages': StagedEMAStrategy.SHORT_ENTRY_STAGES.copy(),
        'symbol': None,     # 必须在config.json的global中定义
        'maintenance_margin_rate': None  # 必须在config.json的global中定义
    }


if __name__ == '__main__':
    # 测试重构后的分批入场EMA交叉策略
    print("\\n" + "="*60)
    config_manager = ConfigManager()
    config = config_manager.get_strategy_config('staged_ema')
    
    print("分批入场EMA交叉策略测试")
    print("=" * 50)
    
    # 创建策略实例
    strategy = create_staged_ema_strategy(config)
    
    # 显示策略配置
    print("策略配置:")
    strategy_config = strategy.get_strategy_specific_config()
    for key, value in strategy_config.items():
        print(f"  {key}: {value}")
    
    print("\\n策略创建成功，可以通过StrategyRunner运行")