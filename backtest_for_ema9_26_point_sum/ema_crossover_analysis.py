#!/usr/bin/env python3
"""
EMA交叉点分析脚本
从币安获取ETHUSDT的30分钟K线数据，计算EMA9和EMA26的交叉点
生成序号vs价格和时间vs价格的图表
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class EMACrossoverAnalyzer:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.symbol = "ETHUSDT"
        self.interval = "30m"  # 30分钟K线
        self.start_date = "2025-02-01"
        self.end_date = "2025-10-15"
        
    def get_timestamp(self, date_str):
        """将日期字符串转换为时间戳"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    
    def fetch_kline_data(self):
        """从币安API获取K线数据"""
        print(f"正在获取 {self.symbol} 的 {self.interval} K线数据...")
        print(f"时间范围: {self.start_date} 到 {self.end_date}")
        
        start_time = self.get_timestamp(self.start_date)
        end_time = self.get_timestamp(self.end_date)
        
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            # 每次最多获取1000条数据
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
                
                # 更新下一次请求的开始时间
                current_start = data[-1][6] + 1  # 使用最后一条数据的关闭时间+1
                
                print(f"已获取 {len(all_data)} 条数据...")
                time.sleep(0.1)  # 避免请求过于频繁
                
            except requests.exceptions.RequestException as e:
                print(f"请求失败: {e}")
                break
        
        # 转换为DataFrame
        df = pd.DataFrame(all_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # 转换数据类型
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        
        # 按时间排序
        df = df.sort_values('open_time').reset_index(drop=True)
        
        print(f"总共获取到 {len(df)} 条K线数据")
        return df
    
    def calculate_ema(self, prices, period):
        """计算指数移动平均线"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def find_crossover_points(self, df):
        """找到EMA9和EMA26的交叉点"""
        print("正在计算EMA9和EMA26...")
        
        # 计算EMA
        df['ema9'] = self.calculate_ema(df['close'], 9)
        df['ema26'] = self.calculate_ema(df['close'], 26)
        
        # 计算EMA差值
        df['ema_diff'] = df['ema9'] - df['ema26']
        df['ema_diff_prev'] = df['ema_diff'].shift(1)
        
        # 找到交叉点（符号变化的点）
        crossover_mask = (
            (df['ema_diff'] > 0) & (df['ema_diff_prev'] <= 0) |  # 金叉
            (df['ema_diff'] < 0) & (df['ema_diff_prev'] >= 0)    # 死叉
        )
        
        crossover_points = df[crossover_mask].copy()
        
        # 添加交叉类型
        crossover_points['crossover_type'] = np.where(
            crossover_points['ema_diff'] > 0, '金叉', '死叉'
        )
        
        # 重置索引并添加序号
        crossover_points = crossover_points.reset_index(drop=True)
        crossover_points['sequence'] = range(1, len(crossover_points) + 1)
        
        print(f"找到 {len(crossover_points)} 个EMA交叉点")
        print(f"金叉: {len(crossover_points[crossover_points['crossover_type'] == '金叉'])} 个")
        print(f"死叉: {len(crossover_points[crossover_points['crossover_type'] == '死叉'])} 个")
        
        return crossover_points
    
    def create_charts(self, crossover_points):
        """创建两个图表"""
        print("正在生成图表...")
        
        # 计算相对时间（从统计开始时间的天数）
        start_datetime = datetime.strptime(self.start_date, "%Y-%m-%d")
        crossover_points['days_from_start'] = (
            crossover_points['open_time'] - start_datetime
        ).dt.total_seconds() / (24 * 3600)
        
        # 计算与前一交叉点的价格差值绝对值
        crossover_points['price_diff_abs'] = crossover_points['close'].diff().abs()
        # 第一个交叉点没有前一个交叉点，设为0
        crossover_points.loc[0, 'price_diff_abs'] = 0
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
        
        # 图表1: 序号 vs 价格差值绝对值
        # 绘制折线图
        ax1.plot(crossover_points['sequence'], crossover_points['price_diff_abs'], 
                'b-', alpha=0.7, linewidth=1.5, label='价格差值变化')
        
        # 添加不同颜色的小点标记金叉和死叉
        golden_cross = crossover_points[crossover_points['crossover_type'] == '金叉']
        death_cross = crossover_points[crossover_points['crossover_type'] == '死叉']
        
        ax1.scatter(golden_cross['sequence'], golden_cross['price_diff_abs'], 
                   c='red', alpha=0.8, s=20, label='金叉', zorder=5)
        ax1.scatter(death_cross['sequence'], death_cross['price_diff_abs'], 
                   c='green', alpha=0.8, s=20, label='死叉', zorder=5)
        
        # 添加趋势线
        # 排除第一个点（差值为0）来计算趋势线
        valid_data = crossover_points[crossover_points['sequence'] > 1]
        if len(valid_data) > 1:
            z = np.polyfit(valid_data['sequence'], valid_data['price_diff_abs'], 1)
            p = np.poly1d(z)
            ax1.plot(valid_data['sequence'], p(valid_data['sequence']), 
                    "orange", linestyle='--', alpha=0.8, linewidth=1, label='趋势线')
        
        ax1.set_xlabel('交叉点序号')
        ax1.set_ylabel('与前一交叉点价格差值绝对值 (USDT)')
        ax1.set_title('EMA9/EMA26交叉点 - 序号 vs 价格差值绝对值')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # 图表2: 时间 vs 价格差值绝对值
        # 绘制折线图
        ax2.plot(crossover_points['days_from_start'], crossover_points['price_diff_abs'], 
                'b-', alpha=0.7, linewidth=1.5, label='价格差值变化')
        
        # 添加不同颜色的小点标记金叉和死叉
        ax2.scatter(golden_cross['days_from_start'], golden_cross['price_diff_abs'], 
                   c='red', alpha=0.8, s=20, label='金叉', zorder=5)
        ax2.scatter(death_cross['days_from_start'], death_cross['price_diff_abs'], 
                   c='green', alpha=0.8, s=20, label='死叉', zorder=5)
        
        # 添加趋势线
        # 排除第一个点（差值为0）来计算趋势线
        if len(valid_data) > 1:
            z2 = np.polyfit(valid_data['days_from_start'], valid_data['price_diff_abs'], 1)
            p2 = np.poly1d(z2)
            ax2.plot(valid_data['days_from_start'], p2(valid_data['days_from_start']), 
                    "orange", linestyle='--', alpha=0.8, linewidth=1, label='趋势线')
        
        ax2.set_xlabel('时间 (从统计开始的天数)')
        ax2.set_ylabel('与前一交叉点价格差值绝对值 (USDT)')
        ax2.set_title('EMA9/EMA26交叉点 - 时间 vs 价格差值绝对值')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        
        # 保存图表
        chart_path = '/home/ubuntu/Code/quant/backtest_for_rule/ema_crossover_analysis.png'
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"图表已保存到: {chart_path}")
        
        plt.show()
        
        return chart_path
    
    def save_results(self, crossover_points):
        """保存分析结果到CSV文件"""
        output_path = '/home/ubuntu/Code/quant/backtest_for_rule/ema_crossover_results.csv'
        
        # 选择要保存的列
        result_df = crossover_points[[
            'sequence', 'open_time', 'close', 'ema9', 'ema26', 
            'crossover_type', 'days_from_start', 'price_diff_abs'
        ]].copy()
        
        # 格式化时间
        result_df['open_time'] = result_df['open_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存到CSV
        result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"分析结果已保存到: {output_path}")
        
        return output_path
    
    def print_summary(self, crossover_points):
        """打印分析摘要"""
        print("\n" + "="*60)
        print("EMA交叉点分析摘要")
        print("="*60)
        print(f"分析时间范围: {self.start_date} 到 {self.end_date}")
        print(f"交易对: {self.symbol}")
        print(f"K线周期: {self.interval}")
        print(f"总交叉点数量: {len(crossover_points)}")
        
        if len(crossover_points) > 0:
            print(f"金叉数量: {len(crossover_points[crossover_points['crossover_type'] == '金叉'])}")
            print(f"死叉数量: {len(crossover_points[crossover_points['crossover_type'] == '死叉'])}")
            print(f"价格范围: ${crossover_points['close'].min():.2f} - ${crossover_points['close'].max():.2f}")
            print(f"平均价格: ${crossover_points['close'].mean():.2f}")
            
            print("\n前5个交叉点:")
            for _, row in crossover_points.head().iterrows():
                print(f"  {row['sequence']:2d}. {row['open_time'].strftime('%Y-%m-%d %H:%M')} - "
                      f"{row['crossover_type']} - ${row['close']:.2f}")
        
        print("="*60)
    
    def run_analysis(self):
        """运行完整的分析流程"""
        try:
            # 1. 获取K线数据
            df = self.fetch_kline_data()
            
            if df.empty:
                print("未获取到数据，请检查网络连接或API参数")
                return
            
            # 2. 找到交叉点
            crossover_points = self.find_crossover_points(df)
            
            if crossover_points.empty:
                print("未找到EMA交叉点")
                return
            
            # 3. 生成图表
            chart_path = self.create_charts(crossover_points)
            
            # 4. 保存结果
            csv_path = self.save_results(crossover_points)
            
            # 5. 打印摘要
            self.print_summary(crossover_points)
            
            return {
                'crossover_points': crossover_points,
                'chart_path': chart_path,
                'csv_path': csv_path
            }
            
        except Exception as e:
            print(f"分析过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """主函数"""
    print("开始EMA交叉点分析...")
    
    analyzer = EMACrossoverAnalyzer()
    results = analyzer.run_analysis()
    
    if results:
        print("\n分析完成！")
        print(f"图表文件: {results['chart_path']}")
        print(f"数据文件: {results['csv_path']}")
    else:
        print("分析失败，请检查错误信息")

if __name__ == "__main__":
    main()