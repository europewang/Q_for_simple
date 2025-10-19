#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMA交叉点半年期回测分析工具
从2023年到2025年10月15日，每半年生成一副大图
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import time
import warnings
import os
import pytz
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class EMABacktestPeriods:
    def __init__(self):
        self.symbol = "ETHUSDT"
        self.interval = "30m"
        self.base_url = "https://api.binance.com/api/v3/klines"
        
    def generate_periods(self, start_year=2023, end_date="2025-10-15"):
        """生成半年期时间段"""
        periods = []
        current_date = datetime(start_year, 1, 1)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date < end_datetime:
            # 计算半年期的结束时间
            if current_date.month <= 6:
                period_end = datetime(current_date.year, 6, 30)
                period_name = f"{current_date.year}年上半年"
            else:
                period_end = datetime(current_date.year, 12, 31)
                period_name = f"{current_date.year}年下半年"
            
            # 确保不超过最终结束日期
            if period_end > end_datetime:
                period_end = end_datetime
                if current_date.month <= 6:
                    period_name = f"{current_date.year}年上半年(至{end_date})"
                else:
                    period_name = f"{current_date.year}年下半年(至{end_date})"
            
            periods.append({
                'name': period_name,
                'start': current_date.strftime("%Y-%m-%d"),
                'end': period_end.strftime("%Y-%m-%d"),
                'start_datetime': current_date,
                'end_datetime': period_end
            })
            
            # 移动到下一个半年期
            if current_date.month <= 6:
                current_date = datetime(current_date.year, 7, 1)
            else:
                current_date = datetime(current_date.year + 1, 1, 1)
        
        return periods
    
    def get_timestamp(self, date_str):
        """将日期字符串转换为时间戳（毫秒）"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    
    def fetch_kline_data(self, start_date, end_date):
        """获取指定时间段的K线数据"""
        print(f"正在获取 {self.symbol} 的 {self.interval} K线数据...")
        print(f"时间范围: {start_date} 到 {end_date}")
        
        start_time = self.get_timestamp(start_date)
        end_time = self.get_timestamp(end_date)
        
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': self.symbol,
                'interval': self.interval,
                'startTime': current_start,
                'endTime': end_time,
                'limit': 1000
            }
            
            try:
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    break
                
                all_data.extend(data)
                print(f"已获取 {len(all_data)} 条数据...")
                
                # 更新下一次请求的开始时间
                current_start = data[-1][6] + 1  # 使用最后一条数据的关闭时间+1ms
                
                # 避免请求过于频繁
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                print(f"请求失败: {e}")
                break
        
        if not all_data:
            print("未获取到任何数据")
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(all_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # 数据类型转换
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', utc=True)
        
        # 转换为中国时区（UTC+8）
        china_tz = pytz.timezone('Asia/Shanghai')
        df['open_time'] = df['open_time'].dt.tz_convert(china_tz)
        df['close_time'] = df['close_time'].dt.tz_convert(china_tz)
        
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        print(f"总共获取到 {len(df)} 条K线数据")
        return df
    
    def calculate_ema(self, prices, period):
        """计算指数移动平均线"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def find_crossover_points(self, df):
        """找到EMA交叉点"""
        print("正在计算EMA9和EMA26...")
        
        # 计算EMA
        df['ema9'] = self.calculate_ema(df['close'], 9)
        df['ema26'] = self.calculate_ema(df['close'], 26)
        
        # 找到交叉点
        df['ema_diff'] = df['ema9'] - df['ema26']
        df['prev_ema_diff'] = df['ema_diff'].shift(1)
        
        # 识别交叉点：当前差值和前一个差值符号不同
        crossover_mask = (
            (df['ema_diff'] > 0) & (df['prev_ema_diff'] <= 0) |  # 金叉
            (df['ema_diff'] < 0) & (df['prev_ema_diff'] >= 0)     # 死叉
        )
        
        crossover_points = df[crossover_mask].copy()
        
        if crossover_points.empty:
            print("未找到交叉点")
            return pd.DataFrame()
        
        # 标记交叉类型
        crossover_points['crossover_type'] = crossover_points['ema_diff'].apply(
            lambda x: '金叉' if x > 0 else '死叉'
        )
        
        # 添加序号
        crossover_points['sequence'] = range(1, len(crossover_points) + 1)
        
        golden_crosses = len(crossover_points[crossover_points['crossover_type'] == '金叉'])
        death_crosses = len(crossover_points[crossover_points['crossover_type'] == '死叉'])
        
        print(f"找到 {len(crossover_points)} 个EMA交叉点")
        print(f"金叉: {golden_crosses} 个")
        print(f"死叉: {death_crosses} 个")
        
        return crossover_points
    
    def create_period_chart(self, crossover_points, period_info, output_dir):
        """为单个时间段创建图表"""
        if crossover_points.empty:
            print(f"时间段 {period_info['name']} 没有交叉点数据，跳过图表生成")
            return None
        
        print(f"正在为 {period_info['name']} 生成图表...")
        
        # 计算相对时间（从统计开始时间的天数）
        start_datetime = period_info['start_datetime']
        # 将start_datetime转换为中国时区以匹配crossover_points['open_time']
        china_tz = pytz.timezone('Asia/Shanghai')
        start_datetime_china = china_tz.localize(start_datetime)
        crossover_points['days_from_start'] = (
            crossover_points['open_time'] - start_datetime_china
        ).dt.total_seconds() / (24 * 3600)
        
        # 计算与前一交叉点的价格差值绝对值
        crossover_points['price_diff_abs'] = crossover_points['close'].diff().abs()
        # 第一个交叉点没有前一个交叉点，设为0
        crossover_points.loc[crossover_points.index[0], 'price_diff_abs'] = 0
        
        # 计算突兀点阈值 - 使用均值的两倍
        valid_price_diff = crossover_points[crossover_points['price_diff_abs'] > 0]['price_diff_abs']
        
        if len(valid_price_diff) == 0:
            outlier_threshold = 0
            outlier_points = crossover_points.iloc[0:0]  # 空DataFrame
            avg_price_diff = 0
        else:
            # 计算平均值
            avg_price_diff = valid_price_diff.mean()
            # 使用均值的两倍作为突兀点阈值
            outlier_threshold = avg_price_diff * 2
            method_name = "均值×2"
            
            # 识别突兀点
            outlier_points = crossover_points[crossover_points['price_diff_abs'] > outlier_threshold]
        
        print(f"  使用{method_name}识别突兀点，平均值: {avg_price_diff:.1f}, 阈值: {outlier_threshold:.1f}, 突兀点数量: {len(outlier_points)}")
        
        # 创建更大的图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 16))
        
        # 分离金叉和死叉数据
        golden_cross = crossover_points[crossover_points['crossover_type'] == '金叉']
        death_cross = crossover_points[crossover_points['crossover_type'] == '死叉']
        
        # 图表1: 序号 vs 价格差值绝对值
        ax1.plot(crossover_points['sequence'], crossover_points['price_diff_abs'], 
                'b-', alpha=0.7, linewidth=2, label='价格差值变化')
        
        ax1.scatter(golden_cross['sequence'], golden_cross['price_diff_abs'], 
                   c='red', alpha=0.8, s=30, label='金叉', zorder=5)
        ax1.scatter(death_cross['sequence'], death_cross['price_diff_abs'], 
                   c='green', alpha=0.8, s=30, label='死叉', zorder=5)
        
        # 添加平均值分界线
        if avg_price_diff > 0:
            ax1.axhline(y=avg_price_diff, color='purple', linestyle='-', alpha=0.8, 
                       linewidth=2, label=f'平均值分界线 ({avg_price_diff:.1f})')
        
        # 标记突兀点
        if not outlier_points.empty:
            ax1.scatter(outlier_points['sequence'], outlier_points['price_diff_abs'], 
                       c='yellow', edgecolors='black', alpha=0.9, s=80, 
                       label='突兀点', zorder=6, marker='*')
            
            # 标记突兀点间的x坐标差值
            outlier_sequences = outlier_points['sequence'].values
            outlier_prices = outlier_points['price_diff_abs'].values
            for i in range(1, len(outlier_sequences)):
                prev_seq = outlier_sequences[i-1]
                curr_seq = outlier_sequences[i]
                curr_price = outlier_prices[i]
                diff = curr_seq - prev_seq
                
                # 在当前突兀点的右上角标注差值
                offset_x = max(1, (ax1.get_xlim()[1] - ax1.get_xlim()[0]) * 0.01)  # x轴偏移量
                offset_y = max(1, (ax1.get_ylim()[1] - ax1.get_ylim()[0]) * 0.02)  # y轴偏移量
                
                ax1.annotate(f'Δx={diff}', xy=(curr_seq + offset_x, curr_price + offset_y), 
                           fontsize=9, ha='left', va='bottom',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))
        
        # 添加趋势线
        valid_data = crossover_points[crossover_points['sequence'] > 1]
        if len(valid_data) > 1:
            z = np.polyfit(valid_data['sequence'], valid_data['price_diff_abs'], 1)
            p = np.poly1d(z)
            ax1.plot(valid_data['sequence'], p(valid_data['sequence']), 
                    "orange", linestyle='--', alpha=0.8, linewidth=2, label='趋势线')
        
        ax1.set_xlabel('交叉点序号', fontsize=14)
        ax1.set_ylabel('与前一交叉点价格差值绝对值 (USDT)', fontsize=14)
        ax1.set_title(f'{period_info["name"]} EMA9/EMA26交叉点 - 序号 vs 价格差值绝对值', fontsize=16)
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=12)
        
        # 图表2: 时间 vs 价格差值绝对值
        ax2.plot(crossover_points['days_from_start'], crossover_points['price_diff_abs'], 
                'b-', alpha=0.7, linewidth=2, label='价格差值变化')
        
        ax2.scatter(golden_cross['days_from_start'], golden_cross['price_diff_abs'], 
                   c='red', alpha=0.8, s=30, label='金叉', zorder=5)
        ax2.scatter(death_cross['days_from_start'], death_cross['price_diff_abs'], 
                   c='green', alpha=0.8, s=30, label='死叉', zorder=5)
        
        # 添加平均值分界线
        if avg_price_diff > 0:
            ax2.axhline(y=avg_price_diff, color='purple', linestyle='-', alpha=0.8, 
                       linewidth=2, label=f'平均值分界线 ({avg_price_diff:.1f})')
        
        # 标记突兀点
        if not outlier_points.empty:
            ax2.scatter(outlier_points['days_from_start'], outlier_points['price_diff_abs'], 
                       c='yellow', edgecolors='black', alpha=0.9, s=80, 
                       label='突兀点', zorder=6, marker='*')
            
            # 标记突兀点间的时间差值
            outlier_days = outlier_points['days_from_start'].values
            outlier_prices_2 = outlier_points['price_diff_abs'].values
            for i in range(1, len(outlier_days)):
                prev_day = outlier_days[i-1]
                curr_day = outlier_days[i]
                curr_price_2 = outlier_prices_2[i]
                diff = curr_day - prev_day
                
                # 在当前突兀点的右上角标注差值
                offset_x = max(0.5, (ax2.get_xlim()[1] - ax2.get_xlim()[0]) * 0.01)  # x轴偏移量
                offset_y = max(1, (ax2.get_ylim()[1] - ax2.get_ylim()[0]) * 0.02)  # y轴偏移量
                
                ax2.annotate(f'Δt={diff:.1f}天', xy=(curr_day + offset_x, curr_price_2 + offset_y), 
                           fontsize=9, ha='left', va='bottom',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))
        
        # 添加趋势线
        if len(valid_data) > 1:
            z2 = np.polyfit(valid_data['days_from_start'], valid_data['price_diff_abs'], 1)
            p2 = np.poly1d(z2)
            ax2.plot(valid_data['days_from_start'], p2(valid_data['days_from_start']), 
                    "orange", linestyle='--', alpha=0.8, linewidth=2, label='趋势线')
        
        ax2.set_xlabel('时间 (从期间开始的天数)', fontsize=14)
        ax2.set_ylabel('与前一交叉点价格差值绝对值 (USDT)', fontsize=14)
        ax2.set_title(f'{period_info["name"]} EMA9/EMA26交叉点 - 时间 vs 价格差值绝对值', fontsize=16)
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=12)
        
        plt.tight_layout()
        
        # 保存图表
        filename = f"ema_analysis_{period_info['name'].replace('年', '').replace('半年', 'H').replace('上', '1').replace('下', '2').replace('(', '_').replace(')', '').replace('至', 'to')}.png"
        filepath = os.path.join(output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"图表已保存到: {filepath}")
        
        # 保存突兀点数据
        if not outlier_points.empty:
            outlier_filepath = self.save_outlier_data(outlier_points, period_info, output_dir)
            print(f"突兀点数据已保存到: {outlier_filepath}")
        
        return filepath, outlier_points
    
    def save_outlier_data(self, outlier_points, period_info, output_dir):
        """保存突兀点数据，包括时间间隔和序号间隔"""
        if outlier_points.empty:
            return None
        
        # 创建突兀点数据副本
        outlier_data = outlier_points.copy()
        
        # 计算与前一突兀点的间隔
        outlier_data = outlier_data.sort_values('sequence').reset_index(drop=True)
        
        # 初始化间隔列
        outlier_data['time_interval_days'] = 0.0
        outlier_data['sequence_interval'] = 0
        outlier_data['time_interval_hours'] = 0.0
        
        # 计算间隔（从第二个突兀点开始）
        for i in range(1, len(outlier_data)):
            # 序号间隔
            outlier_data.loc[i, 'sequence_interval'] = outlier_data.loc[i, 'sequence'] - outlier_data.loc[i-1, 'sequence']
            
            # 时间间隔（直接使用已有的时间对象，避免时区转换问题）
            current_time = outlier_data.loc[i, 'open_time']
            prev_time = outlier_data.loc[i-1, 'open_time']
            time_diff = current_time - prev_time
            
            # 转换为天数和小时数
            outlier_data.loc[i, 'time_interval_days'] = time_diff.total_seconds() / (24 * 3600)
            outlier_data.loc[i, 'time_interval_hours'] = time_diff.total_seconds() / 3600
        
        # 格式化时间列为中国时区字符串（去除时区信息显示）
        if hasattr(outlier_data['open_time'].iloc[0], 'strftime'):
            outlier_data['open_time_china'] = outlier_data['open_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            outlier_data['open_time_china'] = outlier_data['open_time'].astype(str)
        
        # 选择要保存的列
        columns_to_save = [
            'sequence', 'open_time_china', 'close', 'ema9', 'ema26', 'crossover_type', 
            'price_diff_abs', 'sequence_interval', 'time_interval_days', 'time_interval_hours'
        ]
        
        # 生成文件名
        filename = f"outliers_{period_info['name'].replace('年', '').replace('半年', 'H').replace('上', '1').replace('下', '2').replace('(', '_').replace(')', '').replace('至', 'to')}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # 保存数据
        outlier_data[columns_to_save].to_csv(filepath, index=False, encoding='utf-8')
        
        return filepath
    
    def save_period_results(self, crossover_points, period_info, output_dir, all_crossover_points=None):
        """保存单个时间段的分析结果"""
        if crossover_points.empty:
            return None
        
        # 创建数据副本以避免修改原始数据
        result_data = crossover_points.copy()
        
        # 确保包含price_diff_abs列
        if 'price_diff_abs' not in result_data.columns:
            result_data['price_diff_abs'] = result_data['close'].diff().abs()
            result_data.loc[result_data.index[0], 'price_diff_abs'] = 0
        
        # 添加上一交叉时间列
        result_data = result_data.sort_values('sequence').reset_index(drop=True)
        result_data['prev_crossover_time'] = ''
        
        # 如果提供了所有交叉点数据，使用它来计算前一个交叉点时间
        if all_crossover_points is not None and not all_crossover_points.empty:
            all_crossover_sorted = all_crossover_points.sort_values('sequence').reset_index(drop=True)
            
            for i, row in result_data.iterrows():
                current_sequence = row['sequence']
                # 在所有交叉点中找到当前序号之前的最近一个交叉点
                prev_crossovers = all_crossover_sorted[all_crossover_sorted['sequence'] < current_sequence]
                if not prev_crossovers.empty:
                    prev_time = prev_crossovers.iloc[-1]['open_time']  # 取最后一个（最近的）
                    if hasattr(prev_time, 'strftime'):
                        result_data.loc[i, 'prev_crossover_time'] = prev_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        result_data.loc[i, 'prev_crossover_time'] = str(prev_time)
        else:
            # 如果没有提供所有交叉点数据，使用原来的逻辑（基于当前数据内部）
            for i in range(1, len(result_data)):
                prev_time = result_data.loc[i-1, 'open_time']
                if hasattr(prev_time, 'strftime'):
                    result_data.loc[i, 'prev_crossover_time'] = prev_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    result_data.loc[i, 'prev_crossover_time'] = str(prev_time)
        
        # 格式化时间列为中国时区字符串（去除时区信息显示）
        if hasattr(result_data['open_time'].iloc[0], 'strftime'):
            result_data['open_time_china'] = result_data['open_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            result_data['open_time_china'] = result_data['open_time'].astype(str)
        
        filename = f"ema_results_{period_info['name'].replace('年', '').replace('半年', 'H').replace('上', '1').replace('下', '2').replace('(', '_').replace(')', '').replace('至', 'to')}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # 选择要保存的列
        columns_to_save = ['sequence', 'open_time_china', 'close', 'ema9', 'ema26', 'crossover_type', 'price_diff_abs', 'prev_crossover_time']
        result_data[columns_to_save].to_csv(filepath, index=False, encoding='utf-8')
        
        print(f"分析结果已保存到: {filepath}")
        return filepath
    
    def print_period_summary(self, crossover_points, period_info):
        """打印单个时间段的分析摘要"""
        if crossover_points.empty:
            print(f"\n{period_info['name']} - 无交叉点数据")
            return
        
        golden_crosses = len(crossover_points[crossover_points['crossover_type'] == '金叉'])
        death_crosses = len(crossover_points[crossover_points['crossover_type'] == '死叉'])
        
        min_price = crossover_points['close'].min()
        max_price = crossover_points['close'].max()
        avg_price = crossover_points['close'].mean()
        
        print(f"\n============================================================")
        print(f"{period_info['name']} EMA交叉点分析摘要")
        print(f"============================================================")
        print(f"分析时间范围: {period_info['start']} 到 {period_info['end']}")
        print(f"交易对: {self.symbol}")
        print(f"K线周期: {self.interval}")
        print(f"总交叉点数量: {len(crossover_points)}")
        print(f"金叉数量: {golden_crosses}")
        print(f"死叉数量: {death_crosses}")
        print(f"价格范围: ${min_price:.2f} - ${max_price:.2f}")
        print(f"平均价格: ${avg_price:.2f}")
        
        if len(crossover_points) >= 5:
            print(f"\n前5个交叉点 (中国时间):")
            for i, (_, row) in enumerate(crossover_points.head().iterrows()):
                # 确保时间格式化正确处理时区
                if hasattr(row['open_time'], 'strftime'):
                    time_str = row['open_time'].strftime('%Y-%m-%d %H:%M')
                else:
                    time_str = str(row['open_time'])
                print(f"   {i+1}. {time_str} - {row['crossover_type']} - ${row['close']:.2f}")
        
        print(f"============================================================")
    
    def run_backtest(self):
        """运行完整的半年期回测分析"""
        print("开始EMA交叉点半年期回测分析...")
        
        # 创建输出目录
        output_dir = "/home/ubuntu/Code/quant/backtest_for_rule/period_analysis"
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成时间段
        periods = self.generate_periods()
        print(f"\n将分析 {len(periods)} 个时间段:")
        for period in periods:
            print(f"  - {period['name']}: {period['start']} 到 {period['end']}")
        
        # 为每个时间段进行分析
        all_results = []
        
        for i, period in enumerate(periods, 1):
            print(f"\n{'='*60}")
            print(f"正在分析第 {i}/{len(periods)} 个时间段: {period['name']}")
            print(f"{'='*60}")
            
            try:
                # 获取数据
                df = self.fetch_kline_data(period['start'], period['end'])
                
                if df.empty:
                    print(f"时间段 {period['name']} 没有数据，跳过")
                    continue
                
                # 找到交叉点
                crossover_points = self.find_crossover_points(df)
                
                if not crossover_points.empty:
                    # 生成图表并获取突兀点数据
                    chart_path, outlier_points = self.create_period_chart(crossover_points, period, output_dir)
                    
                    # 保存突兀点结果（而不是所有交叉点）
                    if not outlier_points.empty:
                        csv_path = self.save_period_results(outlier_points, period, output_dir, crossover_points)
                        print(f"分析结果已保存到: {csv_path}")
                    else:
                        csv_path = None
                        print("该时间段没有突兀点，未生成交叉记录文件")
                    
                    # 打印摘要
                    self.print_period_summary(crossover_points, period)
                    
                    all_results.append({
                        'period': period['name'],
                        'start_date': period['start'],
                        'end_date': period['end'],
                        'total_crossovers': len(crossover_points),
                        'golden_crosses': len(crossover_points[crossover_points['crossover_type'] == '金叉']),
                        'death_crosses': len(crossover_points[crossover_points['crossover_type'] == '死叉']),
                        'outlier_points': len(outlier_points) if not outlier_points.empty else 0,
                        'outlier_golden_crosses': len(outlier_points[outlier_points['crossover_type'] == '金叉']) if not outlier_points.empty else 0,
                        'outlier_death_crosses': len(outlier_points[outlier_points['crossover_type'] == '死叉']) if not outlier_points.empty else 0,
                        'chart_path': chart_path,
                        'csv_path': csv_path
                    })
                else:
                    print(f"时间段 {period['name']} 没有找到交叉点")
                
            except Exception as e:
                print(f"分析时间段 {period['name']} 时出错: {e}")
                continue
        
        # 生成总结报告
        self.generate_summary_report(all_results, output_dir)
        
        print(f"\n{'='*60}")
        print("半年期回测分析完成！")
        print(f"所有结果已保存到: {output_dir}")
        print(f"{'='*60}")
        
        return all_results
    
    def generate_summary_report(self, results, output_dir):
        """生成总结报告"""
        if not results:
            return
        
        report_path = os.path.join(output_dir, "backtest_summary_report.md")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# EMA交叉点半年期回测分析总结报告\n\n")
            f.write(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**交易对**: {self.symbol}\n")
            f.write(f"**K线周期**: {self.interval}\n")
            f.write(f"**分析期间数**: {len(results)}\n\n")
            
            f.write("## 各期间分析结果\n\n")
            f.write("| 时间段 | 开始日期 | 结束日期 | 总交叉点 | 金叉 | 死叉 |\n")
            f.write("|--------|----------|----------|----------|------|------|\n")
            
            total_crossovers = 0
            total_golden = 0
            total_death = 0
            
            for result in results:
                f.write(f"| {result['period']} | {result['start_date']} | {result['end_date']} | "
                       f"{result['total_crossovers']} | {result['golden_crosses']} | {result['death_crosses']} |\n")
                
                total_crossovers += result['total_crossovers']
                total_golden += result['golden_crosses']
                total_death += result['death_crosses']
            
            f.write(f"\n**总计**: {total_crossovers} 个交叉点 ({total_golden} 金叉, {total_death} 死叉)\n\n")
            
            f.write("## 生成的文件\n\n")
            f.write("### 图表文件\n")
            for result in results:
                if result['chart_path']:
                    f.write(f"- {os.path.basename(result['chart_path'])}\n")
            
            f.write("\n### 数据文件\n")
            for result in results:
                if result['csv_path']:
                    f.write(f"- {os.path.basename(result['csv_path'])}\n")
        
        print(f"总结报告已保存到: {report_path}")

def main():
    analyzer = EMABacktestPeriods()
    results = analyzer.run_backtest()
    
    if results:
        print(f"\n成功分析了 {len(results)} 个时间段")
        print("生成的图表和数据文件已保存到 period_analysis 目录")
    else:
        print("没有成功分析任何时间段")

if __name__ == "__main__":
    main()