#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略管理器
用于管理和对比多个交易策略的性能
功能：
1. 运行多个策略
2. 生成对比报告
3. 可视化策略表现
4. 导出详细结果
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

import os
import sys

# 添加strategies目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'strategies'))

# 导入配置管理器
from strategies.config_manager import get_config_manager

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class StrategyManager:
    def __init__(self):
        self.strategies = {}
        self.results = []
        
        # 使用统一配置管理器
        self.config_manager = get_config_manager()
        
        # 获取输出目录
        global_config = self.config_manager.configs.get('global_trading_config', {})
        self.output_dir = global_config.get('output_directory', 'output')

        # 确保输出目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def register_strategy(self, strategy_name, strategy_class):
        self.strategies[strategy_name] = strategy_class

    def run_strategies(self):
        print("\n" + "=" * 60)
        print("开始运行策略回测...")
        print("=" * 60)

        # 获取要运行的策略列表
        strategies_to_run = self.config_manager.configs.get('strategies_to_run', [])
        print(f"策略列表: {strategies_to_run}")
        
        # 策略类型映射
        strategy_mapping = {
            'complex_ema': ('strategies.complex_ema_strategy', 'ComplexEMAStrategy'),
            'simple_ema': ('strategies.simple_ema_strategy', 'SimpleEMAStrategy'),
            'staged_ema': ('strategies.staged_ema_strategy', 'StagedEMAStrategy'),
            'advanced_staged_ema': ('strategies.advanced_staged_ema_strategy', 'AdvancedStagedEMAStrategy')
        }

        # 动态导入和注册策略
        for strategy_type in strategies_to_run:
            try:
                if strategy_type in strategy_mapping:
                    module_name, class_name = strategy_mapping[strategy_type]
                    
                    # 动态导入策略类
                    module = __import__(module_name, fromlist=[class_name])
                    strategy_class = getattr(module, class_name)
                    
                    # 获取策略配置
                    config = self.config_manager.get_strategy_config(strategy_type)
                    
                    # 创建策略实例
                    strategy_instance = strategy_class(config=config)
                    
                    self.register_strategy(strategy_type, strategy_instance)
                    print(f"✓ 策略注册成功: {strategy_type}")
                else:
                    print(f"✗ 未知策略: {strategy_type}")
                    continue

            except Exception as e:
                print(f"✗ 策略 {strategy_type} 初始化失败: {e}")

        # 运行所有注册的策略
        for name, strategy in self.strategies.items():
            print(f"\n正在运行策略: {name}")
            result = strategy.run_backtest()
            if result:
                print(f"✓ {name} 回测完成")
            self.results.append(result)

    def generate_comparison_report(self):
        if not self.results:
            print("没有策略运行结果可供生成报告。")
            return

        print("\n" + "=" * 60)
        print("生成策略对比报告...")
        print("=" * 60)

        # 准备数据
        report_data = []
        for res in self.results:
            report_data.append({
                '策略名称': res['strategy_name'],
                '总交易次数': res['total_trades'],
                '胜率': f"{res['win_rate']:.2%}",
                '总收益率': f"{res['total_return']:.2%}",
                '平均收益率': f"{res['avg_profit']:.2%}",
                '最大单笔盈利': f"{res['max_profit']:.2%}",
                '最大单笔亏损': f"{res['max_loss']:.2%}",
                '最终资金': f"{res['final_capital']:.2f}"
            })

        df_report = pd.DataFrame(report_data)
        print(df_report.to_string(index=False))

        # 保存为CSV
        csv_path = os.path.join(self.output_dir, 'strategy_comparison.csv')
        df_report.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✓ 策略对比报告已保存")

        # 识别最佳策略
        best_strategy = None
        max_return = -float('inf')
        for res in self.results:
            if res['total_return'] > max_return:
                max_return = res['total_return']
                best_strategy = res['strategy_name']
        if best_strategy:
            print(f"最佳策略: {best_strategy} (总收益率: {max_return:.2%})")

        # 绘制对比图表
        print("正在生成图表和详细报告...")
        self._plot_comparison_charts(df_report)
        self._plot_cumulative_returns()
        self._export_detailed_results()
        print("✓ 所有报告生成完成")

    def _plot_comparison_charts(self, df_report):
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(16, 12))
        fig.suptitle('策略性能对比', fontsize=18, fontweight='bold')

        # 总收益率
        returns = [float(r.strip('%')) for r in df_report['总收益率']]
        axes[0, 0].bar(df_report['策略名称'], returns, color=['skyblue', 'lightcoral'])
        axes[0, 0].set_title('总收益率')
        axes[0, 0].set_ylabel('收益率 (%)')
        for i, v in enumerate(returns):
            axes[0, 0].text(i, v + 0.1, f'{v:.2f}%', ha='center', va='bottom')

        # 胜率
        win_rates = [float(w.strip('%')) for w in df_report['胜率']]
        axes[0, 1].bar(df_report['策略名称'], win_rates, color=['lightgreen', 'orange'])
        axes[0, 1].set_title('胜率')
        axes[0, 1].set_ylabel('胜率 (%)')
        for i, v in enumerate(win_rates):
            axes[0, 1].text(i, v + 0.1, f'{v:.2f}%', ha='center', va='bottom')

        # 总交易次数
        axes[1, 0].bar(df_report['策略名称'], df_report['总交易次数'], color=['lightgray', 'gold'])
        axes[1, 0].set_title('总交易次数')
        axes[1, 0].set_ylabel('次数')
        for i, v in enumerate(df_report['总交易次数']):
            axes[1, 0].text(i, v + 0.1, str(v), ha='center', va='bottom')

        # 最终资金
        final_capitals = [float(c) for c in df_report['最终资金']]
        axes[1, 1].bar(df_report['策略名称'], final_capitals, color=['plum', 'teal'])
        axes[1, 1].set_title('最终资金')
        axes[1, 1].set_ylabel('资金 (USDT)')
        for i, v in enumerate(final_capitals):
            axes[1, 1].text(i, v + 0.1, f'{v:.2f}', ha='center', va='bottom')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        chart_path = os.path.join(self.output_dir, 'strategy_comparison_charts.png')
        plt.savefig(chart_path, dpi=300)
        plt.close()

    def _plot_cumulative_returns(self):
        plt.figure(figsize=(15, 8))

        for res in self.results:
            strategy_name = res['strategy_name']
            # 使用配置中的初始资金，若不存在则默认10000
            global_config = self.config_manager.configs.get('global_trading_config', {})
            initial_capital = global_config.get('initial_capital', 10000)
            cumulative_returns = [initial_capital]
            current_capital = initial_capital

            # 仅统计已完成交易，按退出时间排序
            sorted_trades = sorted([
                t for t in res['detailed_trades']
                if t.get('exit_time') is not None
            ], key=lambda x: x['exit_time'])

            trade_dates = []
            for trade in sorted_trades:
                exit_time = pd.to_datetime(trade['exit_time'])

                # 兼容不同策略的方向字段：simple/complex 使用 'type'，advanced 使用 'direction' 或 'type' 为 '平仓'
                direction = trade.get('type')
                if direction not in ['long', 'short']:
                    direction = trade.get('direction')

                profit_amount = None
                # 对于高级策略的平仓记录，直接使用金额型利润字段
                if trade.get('type') == '平仓' and trade.get('profit') is not None:
                    profit_amount = trade['profit']
                # 对于 simple/complex 关闭交易或含方向记录，按价差与仓位计算利润金额
                elif direction in ['long', 'short'] and all(k in trade for k in ['entry_price', 'exit_price', 'position_size']):
                    entry_price = trade['entry_price']
                    exit_price = trade['exit_price']
                    position_size = abs(trade['position_size'])
                    profit_amount = (exit_price - entry_price) * position_size if direction == 'long' else (entry_price - exit_price) * position_size

                # 无法计算的记录跳过（避免对回填的开/加仓记录重复累计）
                if profit_amount is None:
                    continue

                current_capital += profit_amount
                cumulative_returns.append(current_capital)
                trade_dates.append(exit_time)

            if trade_dates:
                plt.plot(trade_dates, cumulative_returns[1:], label=strategy_name, marker='o', markersize=4)

        plt.title('策略累计收益率对比', fontsize=16, fontweight='bold')
        plt.xlabel('日期', fontsize=12)
        plt.ylabel('累计资金 (USDT)', fontsize=12)
        plt.legend(fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        cumulative_returns_path = os.path.join(self.output_dir, 'cumulative_returns_comparison.png')
        plt.savefig(cumulative_returns_path, dpi=300)
        plt.close()

    def _export_detailed_results(self):
        all_detailed_results = {}
        for res in self.results:
            strategy_name = res['strategy_name']
            # 转换Timestamp对象为字符串
            processed_trades = []
            for trade in res['detailed_trades']:
                processed_trade = trade.copy()
                if isinstance(processed_trade.get('entry_time'), pd.Timestamp):
                    processed_trade['entry_time'] = processed_trade['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
                if isinstance(processed_trade.get('exit_time'), pd.Timestamp):
                    processed_trade['exit_time'] = processed_trade['exit_time'].strftime('%Y-%m-%d %H:%M:%S')
                processed_trades.append(processed_trade)
            all_detailed_results[strategy_name] = processed_trades

        json_path = os.path.join(self.output_dir, 'strategy_detailed_results.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_detailed_results, f, ensure_ascii=False, indent=4)
        
        # 生成详细的交易日志文本文件
        global_config = self.config_manager.configs.get('global_trading_config', {})
        logging_config = global_config.get('logging', {})
        if logging_config.get('log_trades_to_file', True):
            self._generate_trade_log_files()
    
    def _generate_trade_log_files(self):
        """生成详细的交易日志文本文件"""
        
        # 获取配置
        global_config = self.config_manager.configs.get('global_trading_config', {})
        logging_config = global_config.get('logging', {})
        
        for res in self.results:
            strategy_name = res['strategy_name']
            log_filename = f"{logging_config.get('log_file_prefix', 'trades_detailed_log')}_{strategy_name}.txt"
            log_path = os.path.join(self.output_dir, log_filename)
            
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"=== {strategy_name} 详细交易日志 ===\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"回测期间: {global_config.get('start_date', 'N/A')} 至 {global_config.get('end_date', 'N/A')}\n")
                f.write(f"交易币种: {global_config.get('symbol', 'BTCUSDT')}\n")
                f.write(f"初始资金: {global_config.get('initial_capital', 10000):.2f} USDT\n")
                f.write(f"杠杆倍数: {global_config.get('leverage', 1)}x\n")
                f.write("=" * 80 + "\n\n")
                
                f.write("策略总结:\n")
                f.write(f"总交易次数: {res['total_trades']}\n")
                f.write(f"胜率: {res['win_rate']:.2%}\n")
                f.write(f"总收益率: {res['total_return']:.2%}\n")
                f.write(f"平均收益率: {res['avg_profit']:.2%}\n")
                f.write(f"最大单笔盈利: {res['max_profit']:.2%}\n")
                f.write(f"最大单笔亏损: {res['max_loss']:.2%}\n")
                f.write(f"最终资金: {res['final_capital']:.2f} USDT\n")
                f.write("\n" + "=" * 80 + "\n\n")
                
                f.write("详细交易记录:\n")
                f.write("-" * 80 + "\n")
                
                for i, trade in enumerate(res['detailed_trades'], 1):
                    if trade.get('exit_time') is None:
                        continue  # 跳过未完成的交易
                    
                    entry_time = trade['entry_time']
                    exit_time = trade['exit_time']
                    if isinstance(entry_time, pd.Timestamp):
                        entry_time = entry_time.strftime('%Y-%m-%d %H:%M:%S')
                    if isinstance(exit_time, pd.Timestamp):
                        exit_time = exit_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    f.write(f"交易 #{i:03d}\n")
                    trade_type = trade.get('type', trade.get('direction', 'unknown'))
                    f.write(f"  交易类型: {'做多' if trade_type == 'long' else '做空'}\n")
                    f.write(f"  开仓时间: {entry_time}\n")
                    f.write(f"  开仓价格: {trade['entry_price']:.4f} USDT\n")
                    f.write(f"  平仓时间: {exit_time}\n")
                    f.write(f"  平仓价格: {trade['exit_price']:.4f} USDT\n")
                    symbol = global_config.get('symbol', 'BTCUSDT')
                    f.write(f"  仓位大小: {trade['position_size']:.6f} {symbol[:-4]}\n")
                    f.write(f"  投入资金: {trade.get('position_value', 0):.2f} USDT\n")
                    
                    profit_pct = trade.get('profit_percentage', 0)
                    profit_amount = trade.get('profit_amount', 0)
                    f.write(f"  收益金额: {profit_amount:.2f} USDT\n")
                    f.write(f"  收益率: {profit_pct:.2%}\n")
                    
                    if profit_pct > 0:
                        f.write("  结果: ✓ 盈利\n")
                    else:
                        f.write("  结果: ✗ 亏损\n")
                    
                    f.write("-" * 80 + "\n")
                
                f.write(f"\n日志文件生成完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    manager = StrategyManager()
    manager.run_strategies()
    manager.generate_comparison_report()