#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
突兀点交易策略回测系统
基于EMA交叉点的突兀点识别和等待机制的交易策略

策略逻辑：
1. 每15天计算ah值（突兀点差值标准）和adx值（突兀点出现频率）
2. 当交叉点价格差值大于ah时，标记为突兀点
3. 等待adx个交叉点后入场交易
4. 当交叉点价格差值再次大于ah时出场，重新等待
"""

import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import pytz
import os
import json

class OutlierTradingStrategy:
    def __init__(self, symbol='ETHUSDT', start_date='2024-01-01', end_date='2025-10-15', 
                 initial_capital=1000, leverage=25):
        self.symbol = symbol
        self.interval = "30m"
        self.start_date = start_date
        self.end_date = end_date
        self.base_url = "https://api.binance.com"
        
        # 策略参数
        self.calculation_interval_days = 15  # 每15天重新计算ah和adx
        self.lookback_days = 180  # 回顾过去半年（180天）
        self.ah_multiplier = 2.5  # ah值计算倍数
        self.adx_divisor = 4  # adx值计算除数
        
        # 杠杆交易参数
        self.initial_capital = initial_capital  # 初始资金
        self.leverage = leverage  # 杠杆倍数
        self.current_capital = initial_capital  # 当前资金
        self.position_size = 0  # 持仓数量
        self.entry_price = 0  # 入场价格
        
        # 交易状态
        self.current_position = None  # 'long', 'short', None
        self.entry_time = None  # 入场时间
        self.waiting_count = 0  # 等待计数器
        self.required_wait = 0  # 需要等待的交叉点数量
        self.is_waiting = False  # 是否在等待状态
        self.should_stop = False  # 是否应该停止交易
        
        # 记录数据
        self.trades = []
        self.completed_trades = []  # 完整的交易记录（包含入场和出场）
        self.ah_history = []
        self.adx_history = []
        self.crossover_history = []
        
        # 设置中文字体
        self.setup_chinese_font()
        
        # 创建输出目录
        self.output_dir = "outlier_strategy_results"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"突兀点交易策略回测系统初始化完成")
        print(f"交易对: {self.symbol}")
        print(f"时间范围: {self.start_date} 到 {self.end_date}")
        print(f"计算间隔: 每{self.calculation_interval_days}天")
        print(f"回顾期: {self.lookback_days}天")

    def setup_chinese_font(self):
        """设置中文字体"""
        try:
            # 尝试使用系统中文字体
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Arial.ttf',
                '/Windows/Fonts/arial.ttf'
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    plt.rcParams['font.family'] = ['DejaVu Sans']
                    break
            else:
                plt.rcParams['font.family'] = ['sans-serif']
                
            plt.rcParams['axes.unicode_minus'] = False
            
        except Exception as e:
            print(f"字体设置警告: {e}")
            plt.rcParams['font.family'] = ['sans-serif']

    def get_kline_data(self, start_time, end_time, limit=1000):
        """获取K线数据"""
        url = f"{self.base_url}/api/v3/klines"
        
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': self.symbol,
                'interval': self.interval,
                'startTime': current_start,
                'endTime': end_time,
                'limit': limit
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    break
                    
                all_data.extend(data)
                current_start = data[-1][6] + 1  # 下一个开始时间
                
                time.sleep(0.1)  # 避免API限制
                
            except Exception as e:
                print(f"获取数据错误: {e}")
                time.sleep(1)
                continue
        
        return all_data

    def process_kline_data(self, kline_data):
        """处理K线数据"""
        df = pd.DataFrame(kline_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # 转换数据类型
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # 转换为中国时区
        china_tz = pytz.timezone('Asia/Shanghai')
        df['open_time_china'] = df['open_time'].dt.tz_localize('UTC').dt.tz_convert(china_tz)
        
        return df

    def calculate_ema(self, prices, period):
        """计算EMA"""
        return prices.ewm(span=period, adjust=False).mean()

    def find_crossover_points(self, df):
        """找到EMA交叉点"""
        # 计算EMA
        df['ema9'] = self.calculate_ema(df['close'], 9)
        df['ema26'] = self.calculate_ema(df['close'], 26)
        
        # 找到交叉点
        df['ema_diff'] = df['ema9'] - df['ema26']
        df['prev_ema_diff'] = df['ema_diff'].shift(1)
        
        # 识别交叉点
        crossover_mask = (
            ((df['ema_diff'] > 0) & (df['prev_ema_diff'] <= 0)) |  # 金叉
            ((df['ema_diff'] < 0) & (df['prev_ema_diff'] >= 0))     # 死叉
        )
        
        crossover_points = df[crossover_mask].copy()
        
        if len(crossover_points) > 0:
            # 确定交叉类型
            crossover_points['crossover_type'] = np.where(
                crossover_points['ema_diff'] > 0, '金叉', '死叉'
            )
            
            # 计算与前一交叉点的价格差值
            crossover_points['price_diff'] = crossover_points['close'].diff()
            crossover_points['price_diff_abs'] = crossover_points['price_diff'].abs()
            
            # 第一个交叉点的差值设为0
            crossover_points.iloc[0, crossover_points.columns.get_loc('price_diff')] = 0
            crossover_points.iloc[0, crossover_points.columns.get_loc('price_diff_abs')] = 0
        
        return crossover_points

    def calculate_ah_value(self, crossover_points):
        """计算ah值（突兀点差值标准）"""
        if len(crossover_points) < 2:
            return 0
        
        # 计算所有交叉点差值绝对值的平均值
        avg_price_diff = crossover_points['price_diff_abs'].mean()
        
        # ah = 平均值 * 2.5
        ah = avg_price_diff * self.ah_multiplier
        
        return ah

    def calculate_adx_value(self, crossover_points, ah_value):
        """计算adx值（突兀点出现频率）"""
        if len(crossover_points) < 2 or ah_value == 0:
            return 0
        
        # 为所有交叉点添加序号
        crossover_points_with_seq = crossover_points.reset_index(drop=True)
        crossover_points_with_seq['global_sequence'] = range(len(crossover_points_with_seq))
        
        # 找到突兀点
        outlier_mask = crossover_points_with_seq['price_diff_abs'] > ah_value
        outlier_points = crossover_points_with_seq[outlier_mask]
        
        if len(outlier_points) < 2:
            return 0
        
        # 计算每个突兀点与前一突兀点在全局序号中的间隔（Δx）
        outlier_sequences = outlier_points['global_sequence'].values
        delta_x_values = []
        
        for i in range(1, len(outlier_sequences)):
            delta_x = outlier_sequences[i] - outlier_sequences[i-1]
            delta_x_values.append(delta_x)
        
        if not delta_x_values:
            return 0
        
        # 计算平均间隔并除以2
        avg_delta_x = np.mean(delta_x_values)
        adx = avg_delta_x / self.adx_divisor
        
        return max(1, int(adx))  # 至少等待1个交叉点

    def should_recalculate_parameters(self, current_date, last_calculation_date):
        """判断是否需要重新计算参数"""
        if last_calculation_date is None:
            return True
        
        # 确保两个日期都是date对象
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        if isinstance(last_calculation_date, datetime):
            last_calculation_date = last_calculation_date.date()
        
        days_diff = (current_date - last_calculation_date).days
        return days_diff >= self.calculation_interval_days

    def get_lookback_data(self, current_date):
        """获取回顾期数据"""
        # 确保current_date是datetime对象
        if isinstance(current_date, datetime):
            current_datetime = current_date
        else:
            current_datetime = datetime.combine(current_date, datetime.min.time())
        
        lookback_start = current_datetime - timedelta(days=self.lookback_days)
        
        # 转换为时间戳
        start_timestamp = int(lookback_start.timestamp() * 1000)
        end_timestamp = int(current_datetime.timestamp() * 1000)
        
        # 获取数据
        kline_data = self.get_kline_data(start_timestamp, end_timestamp)
        
        if not kline_data:
            return None
        
        df = self.process_kline_data(kline_data)
        return df

    def execute_trade(self, action, price, timestamp, crossover_type):
        """执行交易"""
        # 风险控制：如果资金不足，停止交易
        if self.current_capital <= 0:
            print(f"资金不足，停止交易。当前资金: {self.current_capital:.2f}")
            self.should_stop = True
            return
        
        pnl = 0
        old_capital = self.current_capital
        
        # 处理平仓操作
        if action == 'close' and self.current_position is not None:
            if self.current_position == 'long':
                # 平多仓
                pnl = (price - self.entry_price) * self.position_size
                print(f"平多仓: 买入价 {self.entry_price:.2f}, 卖出价 {price:.2f}, 持仓量 {self.position_size:.4f}")
            elif self.current_position == 'short':
                # 平空仓
                pnl = (self.entry_price - price) * abs(self.position_size)
                print(f"平空仓: 卖出价 {self.entry_price:.2f}, 买入价 {price:.2f}, 持仓量 {abs(self.position_size):.4f}")
            
            self.current_capital += pnl
            
            # 检查资金是否耗尽
            if self.current_capital <= 0:
                print(f"❌ 亏损: {pnl:.2f} 元")
                print(f"💸 资金耗尽！当前资金: {self.current_capital:.2f} 元")
                self.should_stop = True
            else:
                # 打印平仓信息
                if pnl > 0:
                    print(f"✅ 盈利: {pnl:.2f} 元")
                else:
                    print(f"❌ 亏损: {pnl:.2f} 元")
            
            # 记录完整的交易记录（出场）
            completed_trade = {
                'entry_time': self.entry_time,
                'exit_time': timestamp,
                'position_type': self.current_position,
                'entry_price': self.entry_price,
                'exit_price': price,
                'position_size': abs(self.position_size),
                'pnl': pnl,
                'capital_before': old_capital,
                'capital_after': self.current_capital,
                'duration': str(timestamp - self.entry_time) if self.entry_time else 'N/A'
            }
            self.completed_trades.append(completed_trade)
            
            print(f"📊 交易完成:")
            print(f"   入场时间: {self.entry_time}")
            print(f"   出场时间: {timestamp}")
            print(f"   持仓类型: {'做多' if self.current_position == 'long' else '做空'}")
            print(f"   入场价格: {self.entry_price:.2f}")
            print(f"   出场价格: {price:.2f}")
            print(f"   持续时间: {completed_trade['duration']}")
            
            # 清空持仓信息
            self.current_position = None
            self.position_size = 0
            self.entry_time = None
            
            # 如果只是平仓操作，直接返回
            if action == 'close':
                capital_change = self.current_capital - old_capital
                print(f"💰 当前资金: {self.current_capital:.2f} 元 (变化: {capital_change:+.2f} 元)")
                print("-" * 80)
                
                trade = {
                    'timestamp': timestamp,
                    'action': action,
                    'price': price,
                    'crossover_type': crossover_type,
                    'position': None,
                    'position_size': 0,
                    'current_capital': self.current_capital,
                    'entry_price': 0,
                    'entry_time': None,
                    'pnl': pnl
                }
                self.trades.append(trade)
                return
        
        # 风险控制：如果资金不足，不开新仓
        if self.current_capital <= 0:
            print(f"资金不足，停止交易。当前资金: {self.current_capital:.2f}")
            return
        
        # 处理开仓操作
        if action == 'buy_long':
            # 开多仓
            self.position_size = (self.current_capital * self.leverage) / price
            self.current_position = 'long'
            self.entry_price = price
            self.entry_time = timestamp
            print(f"🔵 开多仓: 买入价 {price:.2f}, 持仓量 {self.position_size:.4f}")
            
        elif action == 'sell_short':
            # 开空仓
            self.position_size = -(self.current_capital * self.leverage) / price
            self.current_position = 'short'
            self.entry_price = price
            self.entry_time = timestamp
            print(f"🔴 开空仓: 卖出价 {price:.2f}, 持仓量 {abs(self.position_size):.4f}")
        
        # 打印资金变化
        capital_change = self.current_capital - old_capital
        print(f"💰 当前资金: {self.current_capital:.2f} 元 (变化: {capital_change:+.2f} 元)")
        print("-" * 80)
        
        trade = {
            'timestamp': timestamp,
            'action': action,
            'price': price,
            'crossover_type': crossover_type,
            'position': self.current_position,
            'position_size': self.position_size,
            'current_capital': self.current_capital,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'pnl': pnl
        }
        
        self.trades.append(trade)

    def process_crossover(self, crossover_data, current_ah, current_adx):
        """处理单个交叉点"""
        price = crossover_data['close']
        timestamp = crossover_data['open_time_china']
        crossover_type = crossover_data['crossover_type']
        price_diff_abs = crossover_data['price_diff_abs']
        
        # 记录交叉点历史
        self.crossover_history.append({
            'timestamp': timestamp,
            'price': price,
            'crossover_type': crossover_type,
            'price_diff_abs': price_diff_abs,
            'ah_value': current_ah,
            'is_outlier': price_diff_abs > current_ah,
            'waiting_count': self.waiting_count,
            'required_wait': self.required_wait,
            'is_waiting': self.is_waiting,
            'position': self.current_position
        })
        
        # 检查是否是突兀点
        is_outlier = price_diff_abs > current_ah
        
        if is_outlier:
            print(f"发现突兀点: {timestamp}, 价格差值: {price_diff_abs:.2f}, ah值: {current_ah:.2f}")
            
            # 出场触发1：如果当前有持仓，立即平仓
            if self.current_position is not None:
                print(f"突兀点触发，立即平仓: {timestamp}")
                self.execute_trade('close', price, timestamp, crossover_type)
                self.current_position = None
            
            # 重新开始等待adx个普通交叉点
            self.is_waiting = True
            self.waiting_count = 0
            self.required_wait = current_adx
            
            print(f"开始等待 {self.required_wait} 个普通交叉点后入场")
        
        elif self.is_waiting:
            # 在等待期间，计数普通交叉点
            self.waiting_count += 1
            print(f"等待中: {self.waiting_count}/{self.required_wait} 个普通交叉点")
            
            if self.waiting_count >= self.required_wait:
                # 入场触发：距离上一个突兀点过了adx个普通交叉点，现在入场
                self.is_waiting = False
                self.waiting_count = 0
                
                print(f"等待结束，根据当前交叉点入场: {crossover_type}")
                # 根据交叉类型决定入场方向
                if crossover_type == '金叉':
                    self.execute_trade('buy_long', price, timestamp, crossover_type)
                elif crossover_type == '死叉':
                    self.execute_trade('sell_short', price, timestamp, crossover_type)
        
        else:
            # 不在等待期间，且不是突兀点（普通交叉点）
            # 在非等待期间，普通交叉点也要参与交易
            if self.current_position is not None:
                # 出场触发2：遇到普通交叉点，立即平仓然后再开仓
                print(f"遇到普通交叉点，执行平仓再开仓: {timestamp}, 交叉类型: {crossover_type}")
                
                # 先平仓
                self.execute_trade('close', price, timestamp, crossover_type)
                
                # 立即根据新的交叉类型开仓
                if crossover_type == '金叉':
                    self.execute_trade('buy_long', price, timestamp, crossover_type)
                elif crossover_type == '死叉':
                    self.execute_trade('sell_short', price, timestamp, crossover_type)
                
                print(f"完成平仓再开仓，继续循环直到遇到新突兀点")
            else:
                # 没有持仓时遇到普通交叉点，直接开仓
                print(f"无持仓状态下遇到普通交叉点，直接开仓: {timestamp}, 交叉类型: {crossover_type}")
                
                # 根据交叉类型直接开仓
                if crossover_type == '金叉':
                    self.execute_trade('buy_long', price, timestamp, crossover_type)
                elif crossover_type == '死叉':
                    self.execute_trade('sell_short', price, timestamp, crossover_type)

    def run_backtest(self):
        """运行回测"""
        print("开始运行突兀点交易策略回测...")
        
        # 获取全部数据
        start_timestamp = int(datetime.strptime(self.start_date, "%Y-%m-%d").timestamp() * 1000)
        end_timestamp = int(datetime.strptime(self.end_date, "%Y-%m-%d").timestamp() * 1000)
        
        print("获取历史数据...")
        kline_data = self.get_kline_data(start_timestamp, end_timestamp)
        
        if not kline_data:
            print("无法获取数据")
            return
        
        df = self.process_kline_data(kline_data)
        print(f"获取到 {len(df)} 条K线数据")
        
        # 找到所有交叉点
        print("计算EMA交叉点...")
        crossover_points = self.find_crossover_points(df)
        print(f"找到 {len(crossover_points)} 个交叉点")
        
        if len(crossover_points) == 0:
            print("未找到交叉点")
            return
        
        # 按时间顺序处理每个交叉点
        last_calculation_date = None
        current_ah = 0
        current_adx = 0
        
        for idx, (_, crossover_data) in enumerate(crossover_points.iterrows()):
            # 检查是否应该停止交易
            if self.should_stop:
                print(f"\n资金耗尽，提前结束回测。")
                break
                
            current_date = crossover_data['open_time_china'].date()
            
            # 检查是否需要重新计算参数
            if self.should_recalculate_parameters(current_date, last_calculation_date):
                print(f"\n重新计算参数 - 日期: {current_date}")
                
                # 获取回顾期数据
                lookback_df = self.get_lookback_data(current_date)
                
                if lookback_df is not None and len(lookback_df) > 0:
                    # 计算回顾期的交叉点
                    lookback_crossovers = self.find_crossover_points(lookback_df)
                    
                    if len(lookback_crossovers) > 1:
                        # 计算新的ah和adx值
                        current_ah = self.calculate_ah_value(lookback_crossovers)
                        current_adx = self.calculate_adx_value(lookback_crossovers, current_ah)
                        
                        print(f"新的ah值: {current_ah:.2f}")
                        print(f"新的adx值: {current_adx}")
                        
                        # 记录参数历史
                        self.ah_history.append({
                            'date': current_date,
                            'ah_value': current_ah,
                            'crossover_count': len(lookback_crossovers)
                        })
                        
                        self.adx_history.append({
                            'date': current_date,
                            'adx_value': current_adx,
                            'crossover_count': len(lookback_crossovers)
                        })
                        
                        last_calculation_date = current_date
            
            # 处理当前交叉点
            if current_ah > 0 and current_adx > 0:
                self.process_crossover(crossover_data, current_ah, current_adx)
        
        print(f"\n回测完成!")
        print(f"总交易次数: {len(self.trades)}")
        print(f"参数计算次数: {len(self.ah_history)}")
        
        # 生成报告
        self.generate_report()

    def calculate_performance(self):
        """计算策略表现"""
        if len(self.trades) == 0:
            return {
                'initial_capital': self.initial_capital,
                'final_capital': self.initial_capital,
                'total_return': 0,
                'total_return_pct': 0,
                'leverage': self.leverage
            }
        
        # 计算最终资金（如果还有持仓，需要按最后价格平仓）
        final_capital = self.current_capital
        if self.current_position is not None and len(self.trades) > 0:
            last_price = self.trades[-1]['price']
            if self.current_position == 'long':
                # 平多仓
                pnl = (last_price - self.entry_price) * self.position_size
                final_capital += pnl
            elif self.current_position == 'short':
                # 平空仓
                pnl = (self.entry_price - last_price) * abs(self.position_size)
                final_capital += pnl
        
        total_return = final_capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # 计算交易统计
        capital_changes = []
        for i in range(1, len(self.trades)):
            if 'current_capital' in self.trades[i]:
                prev_capital = self.trades[i-1].get('current_capital', self.initial_capital)
                curr_capital = self.trades[i]['current_capital']
                change_pct = ((curr_capital - prev_capital) / prev_capital) * 100
                capital_changes.append(change_pct)
        
        performance = {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'leverage': self.leverage,
            'total_trades': len(self.trades),
            'avg_return_per_trade': np.mean(capital_changes) if capital_changes else 0,
            'win_rate': len([c for c in capital_changes if c > 0]) / len(capital_changes) * 100 if capital_changes else 0,
            'max_gain_pct': max(capital_changes) if capital_changes else 0,
            'max_loss_pct': min(capital_changes) if capital_changes else 0
        }
        
        return performance

    def generate_report(self):
        """生成回测报告"""
        print("\n生成回测报告...")
        
        # 计算策略表现
        performance = self.calculate_performance()
        
        # 保存交易记录
        trades_df = pd.DataFrame(self.trades)
        if not trades_df.empty:
            trades_df.to_csv(f"{self.output_dir}/trades_record.csv", index=False)
        
        # 保存完整的交易记录（包含入场和出场时间）
        if self.completed_trades:
            completed_trades_df = pd.DataFrame(self.completed_trades)
            completed_trades_df.to_csv(f"{self.output_dir}/completed_trades.csv", index=False)
        
        # 保存交叉点历史
        crossover_df = pd.DataFrame(self.crossover_history)
        if not crossover_df.empty:
            crossover_df.to_csv(f"{self.output_dir}/crossover_history.csv", index=False)
        
        # 保存参数历史
        ah_df = pd.DataFrame(self.ah_history)
        if not ah_df.empty:
            ah_df.to_csv(f"{self.output_dir}/ah_history.csv", index=False)
        
        adx_df = pd.DataFrame(self.adx_history)
        if not adx_df.empty:
            adx_df.to_csv(f"{self.output_dir}/adx_history.csv", index=False)
        
        # 生成详细交易记录表格
        trade_details_table = self.generate_trade_details_table()
        
        # 生成文本报告
        report_content = f"""
突兀点交易策略回测报告（杠杆交易）
{'='*50}

策略参数:
- 交易对: {self.symbol}
- 时间范围: {self.start_date} 到 {self.end_date}
- 计算间隔: 每{self.calculation_interval_days}天
- 回顾期: {self.lookback_days}天
- ah倍数: {self.ah_multiplier}
- adx除数: {self.adx_divisor}

杠杆交易参数:
- 初始资金: {performance['initial_capital']:.2f} 元
- 杠杆倍数: {performance['leverage']}倍
- 最终资金: {performance['final_capital']:.2f} 元

回测结果:
- 总交易次数: {performance['total_trades']}
- 参数计算次数: {len(self.ah_history)}
- 交叉点总数: {len(self.crossover_history)}

策略表现:
- 总收益: {performance['total_return']:.2f} 元
- 总收益率: {performance['total_return_pct']:.2f}%
- 平均每笔交易收益率: {performance['avg_return_per_trade']:.2f}%
- 胜率: {performance['win_rate']:.2f}%
- 最大单笔盈利: {performance['max_gain_pct']:.2f}%
- 最大单笔亏损: {performance['max_loss_pct']:.2f}%

最终结果:
从 {performance['initial_capital']:.2f} 元开始，使用 {performance['leverage']}倍杠杆
最终资金为: {performance['final_capital']:.2f} 元

{trade_details_table}
"""
        
        # 保存报告
        with open(f"{self.output_dir}/backtest_report.txt", 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(report_content)
        print(f"\n报告已保存到 {self.output_dir} 目录")
    
    def generate_trade_details_table(self):
        """生成详细交易记录表格"""
        if not self.completed_trades:
            return "\n详细交易记录:\n暂无完成的交易记录\n"
        
        # 表格标题
        table_content = f"""
详细交易记录:
{'='*120}
{'序号':<4} {'开始时间':<20} {'结束时间':<20} {'交易方向':<8} {'开始价格':<12} {'结束价格':<12} {'持仓大小':<12} {'盈亏金额':<12} {'盈亏率':<10} {'交易前资金':<12} {'交易后资金':<12} {'持续时间':<15}
{'-'*120}
"""
        
        # 添加每笔交易的详细信息
        for i, trade in enumerate(self.completed_trades, 1):
            entry_time = trade.get('entry_time', 'N/A')
            exit_time = trade.get('exit_time', 'N/A')
            position_type = trade.get('position_type', 'N/A')
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            position_size = trade.get('position_size', 0)
            pnl = trade.get('pnl', 0)
            capital_before = trade.get('capital_before', 0)
            capital_after = trade.get('capital_after', 0)
            duration = trade.get('duration', 'N/A')
            
            # 计算盈亏率
            if capital_before > 0:
                pnl_rate = (pnl / capital_before) * 100
            else:
                pnl_rate = 0
            
            # 格式化交易方向显示
            direction_display = "做多" if position_type == "long" else "做空" if position_type == "short" else position_type
            
            # 格式化时间显示（只显示日期和时间，去掉时区信息）
            if entry_time != 'N/A' and entry_time:
                entry_time_str = str(entry_time).split('+')[0] if '+' in str(entry_time) else str(entry_time)
            else:
                entry_time_str = 'N/A'
                
            if exit_time != 'N/A' and exit_time:
                exit_time_str = str(exit_time).split('+')[0] if '+' in str(exit_time) else str(exit_time)
            else:
                exit_time_str = 'N/A'
            
            # 添加交易记录行
            table_content += f"{i:<4} {entry_time_str:<20} {exit_time_str:<20} {direction_display:<8} {entry_price:<12.2f} {exit_price:<12.2f} {position_size:<12.4f} {pnl:<12.2f} {pnl_rate:<10.2f}% {capital_before:<12.2f} {capital_after:<12.2f} {duration:<15}\n"
        
        table_content += f"{'-'*120}\n"
        
        # 添加汇总信息
        total_trades = len(self.completed_trades)
        profitable_trades = len([t for t in self.completed_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in self.completed_trades if t.get('pnl', 0) < 0])
        total_pnl = sum([t.get('pnl', 0) for t in self.completed_trades])
        
        table_content += f"""
交易汇总:
- 总交易次数: {total_trades}
- 盈利交易: {profitable_trades} 次
- 亏损交易: {losing_trades} 次
- 胜率: {(profitable_trades/total_trades*100) if total_trades > 0 else 0:.2f}%
- 总盈亏: {total_pnl:.2f} 元
"""
        
        return table_content

def main():
    """主函数"""
    strategy = OutlierTradingStrategy()
    strategy.run_backtest()

if __name__ == "__main__":
    main()