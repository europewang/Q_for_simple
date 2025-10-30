#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMA交叉策略回测（动态杠杆版本）
基于EMA9和EMA26的交叉信号进行交易
- 当EMA9上穿EMA26时，在收盘价做多
- 当EMA9下穿EMA26时，在收盘价做空
- 在下一个EMA交叉信号时平仓
- 每次交易使用10U，基础25倍杠杆
- 动态杠杆调整：亏损后杠杆+1，盈利后杠杆回归25x
- 使用半小时K线数据
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

class EMAStrategy:
    def __init__(self, symbol='ETHUSDT', start_date='2025-05-01', end_date='2025-10-17', 
                 initial_capital=1000, trade_amount=10, leverage=25, trading_fee=0.00045, leverage_increase_on_loss=2):
        """
        初始化EMA交叉策略
        
        Args:
            symbol: 交易对
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            trade_amount: 每次交易金额(U)
            leverage: 杠杆倍数（基础杠杆，动态调整）
            trading_fee: 交易费用率（单边费用率，默认0.045%）
        """
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trade_amount = trade_amount
        self.base_leverage = leverage  # 基础杠杆倍数
        self.current_leverage = leverage  # 当前杠杆倍数
        self.trading_fee = trading_fee  # 0.045% = 0.00045
        self.leverage_increase_on_loss = leverage_increase_on_loss # 亏损后杠杆增加的值
        self.last_doubling_capital = initial_capital # 记录上次资金翻倍时的资金量，用于动态调整交易金额

        # 交易状态
        self.current_position = None  # 'long', 'short', None
        self.position_size = 0
        self.entry_price = 0
        self.entry_time = None
        
        # 记录
        self.trades = []
        self.kline_data = None
        
        # 创建结果目录
        self.results_dir = './backtest_for_ema_Martin_strategy/ema_strategy_results'
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def get_kline_data(self, start_time, end_time, limit=1000):
        """获取K线数据"""
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': self.symbol,
            'interval': '30m',  # 1小时K线
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return None
    
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
        
        # 转换为中国时间
        beijing_tz = pytz.timezone('Asia/Shanghai')
        df['open_time_china'] = df['open_time'].dt.tz_localize('UTC').dt.tz_convert(beijing_tz).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['close_time_china'] = df['close_time'].dt.tz_localize('UTC').dt.tz_convert(beijing_tz).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return df
    
    def calculate_ema(self, prices, period):
        """计算EMA"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def find_crossover_signals(self, df):
        """找到EMA交叉信号"""
        # 计算EMA9和EMA26
        df['ema9'] = self.calculate_ema(df['close'], 9)
        df['ema26'] = self.calculate_ema(df['close'], 26)
        
        # 计算交叉信号
        df['ema_diff'] = df['ema9'] - df['ema26']
        df['ema_diff_prev'] = df['ema_diff'].shift(1)
        
        # 金叉：EMA9上穿EMA26 (做多信号)
        df['golden_cross'] = (df['ema_diff'] > 0) & (df['ema_diff_prev'] <= 0)
        
        # 死叉：EMA9下穿EMA26 (做空信号)
        df['death_cross'] = (df['ema_diff'] < 0) & (df['ema_diff_prev'] >= 0)
        
        # 任意交叉信号
        df['crossover'] = df['golden_cross'] | df['death_cross']
        
        return df
    
    def fetch_all_data(self):
        """获取所有需要的K线数据"""
        print(f"开始获取 {self.symbol} 1小时K线数据...")
        
        start_timestamp = int(pd.Timestamp(self.start_date).timestamp() * 1000)
        end_timestamp = int(pd.Timestamp(self.end_date).timestamp() * 1000)
        
        all_data = []
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            print(f"获取数据: {pd.Timestamp(current_start, unit='ms')}")
            
            kline_data = self.get_kline_data(current_start, end_timestamp, 1000)
            if not kline_data:
                break
            
            all_data.extend(kline_data)
            
            # 更新下一批数据的开始时间
            if len(kline_data) < 1000:
                break
            
            current_start = kline_data[-1][6] + 1  # 使用最后一条数据的close_time + 1
            time.sleep(0.1)  # 避免请求过于频繁
        
        if not all_data:
            raise Exception("无法获取K线数据")
        
        # 处理数据
        df = self.process_kline_data(all_data)
        
        # 去重并排序
        df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
        
        print(f"获取到 {len(df)} 条K线数据")
        return df
    
    def execute_trade(self, action, price, timestamp, signal_type):
        """执行交易"""
        old_capital = self.current_capital
        pnl = 0
        trading_fee_amount = 0
        
        if action == 'close':
            # 平仓
            if self.current_position and self.position_size != 0:
                # 计算交易费用（基于名义价值：保证金 * 杠杆 * 双边费用率）
                nominal_value = self.trade_amount * self.current_leverage  # 名义价值
                trading_fee_amount = nominal_value * self.trading_fee * 2  # 双边费用
                
                if self.current_position == 'long':
                    # 平多仓
                    pnl = self.position_size * (price - self.entry_price) - trading_fee_amount
                elif self.current_position == 'short':
                    # 平空仓
                    pnl = abs(self.position_size) * (self.entry_price - price) - trading_fee_amount
                
                self.current_capital += pnl

                # 检查资金是否翻倍，如果翻倍则调整交易金额
                if self.current_capital >= self.last_doubling_capital * 2:
                    self.trade_amount *= 2
                    self.last_doubling_capital = self.current_capital
                    print(f"   🎉 资金翻倍！当前资金: {self.current_capital:.2f} U，交易金额调整为: {self.trade_amount} U")

                print(f"🔄 平仓: {self.current_position} 仓位 (杠杆: {self.current_leverage}x)")
                print(f"   入场价: {self.entry_price:.2f}, 出场价: {price:.2f}")
                print(f"   持仓量: {abs(self.position_size):.4f}")
                print(f"   交易费用: {trading_fee_amount:.2f} U (双边{self.trading_fee*2*100:.3f}%)")
                if pnl > 0:
                    print(f"   ✅ 净盈利: {pnl:.2f} U")
                else:
                    print(f"   ❌ 净亏损: {pnl:.2f} U")
                
                # 动态杠杆调整逻辑
                old_leverage = self.current_leverage
                if pnl > 0:
                    # 盈利：杠杆回归基础杠杆
                    self.current_leverage = self.base_leverage
                    print(f"   📈 盈利交易，杠杆回归: {old_leverage}x → {self.current_leverage}x")
                else:
                    # 亏损：杠杆+2
                    self.current_leverage += self.leverage_increase_on_loss
                    print(f"   📉 亏损交易，杠杆增加: {old_leverage}x → {self.current_leverage}x")
                
                # 记录交易
                profit_loss_status = "盈利" if pnl > 0 else "亏损"
                trade = {
                    'profit_loss': profit_loss_status,
                    'timestamp': timestamp,
                    'action': 'close',
                    'position_type': self.current_position,
                    'price': price,
                    'signal_type': signal_type,
                    'position_size': abs(self.position_size),
                    'entry_price': self.entry_price,
                    'entry_time': self.entry_time,
                    'exit_price': price,
                    'exit_time': timestamp,
                    'pnl': pnl,
                    'trading_fee': trading_fee_amount,
                    'leverage_used': old_leverage,  # 记录本次交易使用的杠杆
                    'next_leverage': self.current_leverage,  # 记录下次交易的杠杆
                    'capital_before': old_capital,
                    'capital_after': self.current_capital
                }
                self.trades.append(trade)
                
                # 重置仓位
                self.current_position = None
                self.position_size = 0
                self.entry_price = 0
                self.entry_time = None
        
        elif action in ['buy_long', 'sell_short']:
            # 开仓
            if self.current_capital < self.trade_amount:
                print(f"资金不足，无法开仓。当前资金: {self.current_capital:.2f} U")
                return
            
            if action == 'buy_long':
                # 开多仓
                self.position_size = (self.trade_amount * self.current_leverage) / price
                self.current_position = 'long'
                self.entry_price = price
                self.entry_time = timestamp
                print(f"🔵 开多仓: 买入价 {price:.2f}, 持仓量 {self.position_size:.4f}, 杠杆 {self.current_leverage}x")
                
            elif action == 'sell_short':
                # 开空仓
                self.position_size = -(self.trade_amount * self.current_leverage) / price
                self.current_position = 'short'
                self.entry_price = price
                self.entry_time = timestamp
                print(f"🔴 开空仓: 卖出价 {price:.2f}, 持仓量 {abs(self.position_size):.4f}, 杠杆 {self.current_leverage}x")
        
        print(f"💰 当前资金: {self.current_capital:.2f} U")
        print("-" * 80)
    
    def process_signal(self, row):
        """处理交叉信号"""
        timestamp = row['close_time_china']
        price = row['close']
        
        if row['golden_cross']:
            # 金叉信号
            if self.current_position == 'short':
                # 先平空仓
                self.execute_trade('close', price, timestamp, 'golden_cross')
            
            # 开多仓
            if self.current_position is None:
                self.execute_trade('buy_long', price, timestamp, 'golden_cross')
                
        elif row['death_cross']:
            # 死叉信号
            if self.current_position == 'long':
                # 先平多仓
                self.execute_trade('close', price, timestamp, 'death_cross')
            
            # 开空仓
            if self.current_position is None:
                self.execute_trade('sell_short', price, timestamp, 'death_cross')
    
    def run_backtest(self):
        """运行回测"""
        print("=" * 80)
        print("开始EMA交叉策略回测（动态杠杆）")
        print(f"交易对: {self.symbol}")
        print(f"时间范围: {self.start_date} 到 {self.end_date}")
        print(f"K线周期: 半小时")
        print(f"初始资金: {self.initial_capital} U")
        print(f"每次交易金额: {self.trade_amount} U")
        print(f"基础杠杆倍数: {self.base_leverage}x (动态调整)")
        print(f"杠杆调整规则: 亏损后+{self.leverage_increase_on_loss}，盈利后回归{self.base_leverage}x")
        print("=" * 80)
        
        # 获取数据
        self.kline_data = self.fetch_all_data()
        
        # 计算EMA和交叉信号
        self.kline_data = self.find_crossover_signals(self.kline_data)
        
        # 保存K线数据
        self.kline_data.to_csv(f'{self.results_dir}/kline_data_with_ema.csv', index=False)
        
        # 找到所有交叉信号
        crossover_signals = self.kline_data[self.kline_data['crossover']].copy()
        print(f"找到 {len(crossover_signals)} 个EMA交叉信号")
        
        # 处理每个信号
        for idx, (_, signal_row) in enumerate(crossover_signals.iterrows()):
            print(f"\n处理第 {idx + 1} 个信号:")
            print(f"时间: {signal_row['close_time_china']}")
            print(f"价格: {signal_row['close']:.2f}")
            print(f"信号类型: {'金叉' if signal_row['golden_cross'] else '死叉'}")
            
            self.process_signal(signal_row)
        
        # 如果最后还有持仓，按最后价格平仓
        if self.current_position is not None:
            last_row = self.kline_data.iloc[-1]
            print(f"\n回测结束，平仓剩余持仓:")
            self.execute_trade('close', last_row['close'], last_row['close_time_china'], 'backtest_end')
        
        print("\n" + "=" * 80)
        print("回测完成")
        print("=" * 80)
        
        # 生成报告
        self.generate_report()
    
    def calculate_performance(self):
        """计算绩效指标"""
        if not self.trades:
            return {}
        
        # 只统计完整的交易（有平仓的）
        completed_trades = [t for t in self.trades if t['action'] == 'close']
        
        if not completed_trades:
            return {}
        
        total_trades = len(completed_trades)
        profitable_trades = len([t for t in completed_trades if t['pnl'] > 0])
        losing_trades = total_trades - profitable_trades
        
        total_pnl = sum(t['pnl'] for t in completed_trades)
        total_profit = sum(t['pnl'] for t in completed_trades if t['pnl'] > 0)
        total_loss = sum(t['pnl'] for t in completed_trades if t['pnl'] < 0)
        
        # 计算交易费用统计
        total_trading_fees = sum(t.get('trading_fee', 0) for t in completed_trades)
        
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_profit = total_profit / profitable_trades if profitable_trades > 0 else 0
        avg_loss = abs(total_loss) / losing_trades if losing_trades > 0 else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        total_return = ((self.current_capital - self.initial_capital) / self.initial_capital * 100)
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_loss_ratio': profit_loss_ratio,
            'total_trading_fees': total_trading_fees,
            'initial_capital': self.initial_capital,
            'final_capital': self.current_capital,
            'total_return': total_return
        }
    
    def analyze_consecutive_losses(self):
        """分析连续亏损情况"""
        if not self.trades:
            return {}
        
        # 只统计完整的交易（有平仓的）
        completed_trades = [t for t in self.trades if t['action'] == 'close']
        
        if not completed_trades:
            return {}
        
        # 1. 计算最多连续亏损交易次数
        max_consecutive_losses = 0
        current_consecutive_losses = 0
        max_loss_start_idx = 0
        max_loss_end_idx = 0
        current_loss_start_idx = 0
        
        for i, trade in enumerate(completed_trades):
            if trade['pnl'] < 0:  # 亏损交易
                if current_consecutive_losses == 0:
                    current_loss_start_idx = i
                current_consecutive_losses += 1
                
                if current_consecutive_losses > max_consecutive_losses:
                    max_consecutive_losses = current_consecutive_losses
                    max_loss_start_idx = current_loss_start_idx
                    max_loss_end_idx = i
            else:  # 盈利交易，重置连续亏损计数
                current_consecutive_losses = 0
        
        # 2. 计算最多连续亏损金额
        max_consecutive_loss_amount = 0
        current_consecutive_loss_amount = 0
        max_amount_loss_start_idx = 0
        max_amount_loss_end_idx = 0
        current_amount_loss_start_idx = 0
        
        for i, trade in enumerate(completed_trades):
            if trade['pnl'] < 0:  # 亏损交易
                if current_consecutive_loss_amount == 0:
                    current_amount_loss_start_idx = i
                current_consecutive_loss_amount += abs(trade['pnl'])
                
                if current_consecutive_loss_amount > max_consecutive_loss_amount:
                    max_consecutive_loss_amount = current_consecutive_loss_amount
                    max_amount_loss_start_idx = current_amount_loss_start_idx
                    max_amount_loss_end_idx = i
            else:  # 盈利交易，重置连续亏损金额
                current_consecutive_loss_amount = 0
        
        # 3. 计算最大回撤期间（包含盈利但整体亏损阶段）
        max_drawdown = 0
        max_drawdown_start_idx = 0
        max_drawdown_end_idx = 0
        peak_capital = self.initial_capital
        peak_idx = 0
        
        for i, trade in enumerate(completed_trades):
            current_capital = trade['capital_after']
            
            if current_capital > peak_capital:
                peak_capital = current_capital
                peak_idx = i
            else:
                drawdown = peak_capital - current_capital
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_drawdown_start_idx = peak_idx
                    max_drawdown_end_idx = i
        
        return {
            'max_consecutive_losses': max_consecutive_losses,
            'max_loss_start_idx': max_loss_start_idx + 1,  # 转换为1开始的序号
            'max_loss_end_idx': max_loss_end_idx + 1,
            'max_consecutive_loss_amount': max_consecutive_loss_amount,
            'max_amount_loss_start_idx': max_amount_loss_start_idx + 1,
            'max_amount_loss_end_idx': max_amount_loss_end_idx + 1,
            'max_drawdown': max_drawdown,
            'max_drawdown_start_idx': max_drawdown_start_idx + 1,
            'max_drawdown_end_idx': max_drawdown_end_idx + 1
        }
    
    def generate_report(self):
        """生成回测报告"""
        performance = self.calculate_performance()
        loss_analysis = self.analyze_consecutive_losses()
        
        # 生成文本报告
        report_content = f"""
EMA交叉策略回测报告
{'=' * 50}

策略参数:
- 交易对: {self.symbol}
- 时间范围: {self.start_date} 到 {self.end_date}
- K线周期: 半小时
- EMA参数: EMA9 和 EMA26
- 初始资金: {self.initial_capital:.2f} U
- 每次交易金额: {self.trade_amount} U
- 基础杠杆倍数: {self.base_leverage}x (动态调整)
- 杠杆调整规则: 亏损后+{self.leverage_increase_on_loss}，盈利后回归{self.base_leverage}x
- 交易费用率: {self.trading_fee*100:.3f}% (单边) / {self.trading_fee*2*100:.3f}% (双边)

回测结果:
- 总交易次数: {performance.get('total_trades', 0)}
- 盈利交易: {performance.get('profitable_trades', 0)}
- 亏损交易: {performance.get('losing_trades', 0)}
- 胜率: {performance.get('win_rate', 0):.2f}%
- 总盈亏: {performance.get('total_pnl', 0):.2f} U (已扣除交易费用)
- 总盈利: {performance.get('total_profit', 0):.2f} U
- 总亏损: {performance.get('total_loss', 0):.2f} U
- 总交易费用: {performance.get('total_trading_fees', 0):.2f} U
- 平均盈利: {performance.get('avg_profit', 0):.2f} U
- 平均亏损: {performance.get('avg_loss', 0):.2f} U
- 盈亏比: {performance.get('profit_loss_ratio', 0):.2f}
- 初始资金: {performance.get('initial_capital', 0):.2f} U
- 最终资金: {performance.get('final_capital', 0):.2f} U
- 总收益率: {performance.get('total_return', 0):.2f}%

连续亏损分析:
- 最多连续亏损交易次数: {loss_analysis.get('max_consecutive_losses', 0)} 次
  (交易序号 {loss_analysis.get('max_loss_start_idx', 0)} 到 {loss_analysis.get('max_loss_end_idx', 0)})
- 最多连续亏损金额: {loss_analysis.get('max_consecutive_loss_amount', 0):.2f} U
  (交易序号 {loss_analysis.get('max_amount_loss_start_idx', 0)} 到 {loss_analysis.get('max_amount_loss_end_idx', 0)})
- 最大回撤金额: {loss_analysis.get('max_drawdown', 0):.2f} U
  (交易序号 {loss_analysis.get('max_drawdown_start_idx', 0)} 到 {loss_analysis.get('max_drawdown_end_idx', 0)})

最终收益: {performance.get('final_capital', 0) - performance.get('initial_capital', 0):.2f} U
"""
        
        # 保存报告
        with open(f'{self.results_dir}/backtest_report.txt', 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # 绘制盈亏柱状图
        self.plot_profit_loss_bar_chart()

        # 保存交易记录
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            
            # 定义中文列名映射
            column_mapping = {
                'profit_loss': '盈亏状态',
                'timestamp': '时间戳',
                'action': '操作',
                'position_type': '仓位类型',
                'price': '价格',
                'signal_type': '信号类型',
                'position_size': '仓位大小',
                'entry_price': '入场价格',
                'entry_time': '入场时间',
                'exit_price': '出场价格',
                'exit_time': '出场时间',
                'pnl': '盈亏金额',
                'trading_fee': '交易费用',
                'capital_before': '交易前资金',
                'capital_after': '交易后资金',
                'leverage_used': '杠杆数'
            }
            
            # 重命名列为中文
            trades_df_chinese = trades_df.rename(columns=column_mapping)
            
            # 重新排列列顺序，将盈亏金额放在第二列
            column_order = [
                '盈亏状态', '盈亏金额', '交易费用', '时间戳', '操作', '仓位类型', '价格',
                '信号类型', '仓位大小', '入场价格', '入场时间', '出场价格',
                '出场时间', '交易前资金', '交易后资金', '杠杆数'
            ]
            trades_df_reordered = trades_df_chinese[column_order]
            trades_df_reordered.to_csv(f'{self.results_dir}/trades_record.csv', index=False, encoding='utf-8-sig')
        
        print(report_content)
        
        return performance

    def plot_profit_loss_bar_chart(self):
        """绘制每笔交易的盈亏柱状图，并按半年分割"""
        if not self.trades:
            print("没有交易记录，无法绘制盈亏柱状图。")
            return

        trades_df = pd.DataFrame([t for t in self.trades if t['action'] == 'close'])
        if trades_df.empty:
            print("没有完成的交易记录，无法绘制盈亏柱状图。")
            return

        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])

        # 设置中文字体
        try:
            font_manager.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc')
            plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            print("Warning: Could not set Chinese font. Please ensure 'wqy-microhei.ttc' is installed or adjust font path.")
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans'] # Fallback to default if Chinese font fails

        # 计算时间范围
        min_date = trades_df['exit_time'].min()
        max_date = trades_df['exit_time'].max()
        
        # 按半年分割
        current_start_date = min_date
        chart_idx = 1
        
        while current_start_date <= max_date:
            current_end_date = current_start_date + pd.DateOffset(months=3) - pd.DateOffset(days=1)
            
            # 确保不会超出最大日期
            if current_end_date > max_date:
                current_end_date = max_date

            period_trades = trades_df[(trades_df['exit_time'] >= current_start_date) & \
                                      (trades_df['exit_time'] <= current_end_date)].copy()

            if not period_trades.empty:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(30, 14), sharex=False) # 创建两个子图，共享x轴改为False，宽度增加一倍

                # --- 上方子图：按时间轴显示盈亏 --- 
                colors = ['red' if pnl < 0 else 'green' for pnl in period_trades['pnl']]
                ax1.bar(period_trades['exit_time'], period_trades['pnl'], color=colors, width=0.05)

                for i, pnl_value in enumerate(period_trades['pnl']):
                    y_position = pnl_value + (1.0 if pnl_value > 0 else -1.0)
                    ax1.text(period_trades['exit_time'].iloc[i], y_position, f'{pnl_value:.2f}', ha='center', va='center', color='black', fontsize=7, rotation=90)
                ax1.set_xlabel('平仓时间')
                ax1.set_ylabel('盈亏 (U)', color='blue')
                ax1.tick_params(axis='y', labelcolor='blue')
                ax1.set_title(f'{self.symbol} 每笔交易盈亏 (按时间轴) ({current_start_date.strftime("%Y-%m-%d")} 至 {current_end_date.strftime("%Y-%m-%d")})')
                ax1.grid(True, linestyle='--', alpha=0.6)
                fig.autofmt_xdate()
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))

                # --- 下方子图：按交易序号显示盈亏 --- 
                # 为当前时间段的交易生成一个交易序号
                period_trades = period_trades.reset_index(drop=True) # 重置索引以获得从0开始的交易序号
                trade_indices = period_trades.index + 1 # 交易序号从1开始

                ax2.bar(trade_indices, period_trades['pnl'], color=colors, width=0.05)

                for i, pnl_value in enumerate(period_trades['pnl']):
                    y_position = pnl_value + (1.0 if pnl_value > 0 else -1.0)
                    ax2.text(trade_indices[i], y_position, f'{pnl_value:.2f}', ha='center', va='center', color='black', fontsize=7, rotation=90)
                ax2.set_xlabel('交易序号')
                ax2.set_ylabel('盈亏 (U)', color='blue')
                ax2.tick_params(axis='y', labelcolor='blue')
                ax2.set_title(f'{self.symbol} 每笔交易盈亏 (按交易序号) ({current_start_date.strftime("%Y-%m-%d")} 至 {current_end_date.strftime("%Y-%m-%d")})')
                ax2.grid(False) # 移除下方子图的背景网格
                
                # 确保交易序号的间隔一致，每隔5个显示一个
                display_indices = trade_indices[::5] # 每隔5个取一个索引
                display_labels = [str(i) for i in display_indices]
                ax2.set_xticks(display_indices)
                ax2.set_xticklabels(display_labels, rotation=90, fontsize=7)

                plt.tight_layout() # 调整布局以避免重叠
                
                # 保存图表
                chart_path = f'{self.results_dir}/profit_loss_bar_chart_{chart_idx}.png'
                plt.savefig(chart_path, bbox_inches='tight', dpi=300)
                plt.close(fig)
                print(f"盈亏柱状图已保存到 {chart_path}")
                chart_idx += 1
            
            current_start_date = current_end_date + pd.DateOffset(days=1)

def main():
    """主函数"""
    # 创建策略实例
    strategy = EMAStrategy(
        symbol='BTCUSDT',
        start_date='2018-10-01',
        end_date='2023-10-30',
        initial_capital=30,
        trade_amount=10,
        leverage=2,
        leverage_increase_on_loss=2  # 亏损后杠杆增加值
    )
    
    # 运行回测
    strategy.run_backtest()

if __name__ == "__main__":
    main()