"""
图表生成器模块
用于生成策略交易的可视化图表，显示进场和出场点
"""

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os
import platform
from typing import List, Dict, Any, Optional
from font_config import setup_chinese_fonts, suppress_font_warnings


class ChartGenerator:
    """策略图表生成器"""
    
    def __init__(self, output_dir: str = "output/charts"):
        """
        初始化图表生成器
        
        Args:
            output_dir: 图表输出目录
        """
        self.output_dir = output_dir
        self._ensure_output_dir()
        
        # 配置中文字体和抑制字体警告
        suppress_font_warnings()
        self.main_font = setup_chinese_fonts()
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
    
    def _calculate_returns_indicator(self, price_data: pd.DataFrame, trades: List[Dict[str, Any]]) -> Optional[pd.Series]:
        """
        计算单笔交易收益率指标
        只在交易完成时显示该笔交易的收益率
        正收益在横轴上方，负收益在横轴下方
        
        Args:
            price_data: 价格数据DataFrame
            trades: 交易记录列表
            
        Returns:
            单笔交易收益率的Series，如果计算失败返回None
        """
        try:
            if not trades:
                return None
            
            # 初始化收益率序列，默认为NaN（不显示）
            returns_series = pd.Series(float('nan'), index=price_data.index)
            
            # 按交易ID分组，计算每个完整交易的收益率
            trade_groups = {}
            for trade in trades:
                if isinstance(trade, dict):
                    trade_id = trade.get('trade_id', 0)
                    if trade_id not in trade_groups:
                        trade_groups[trade_id] = []
                    trade_groups[trade_id].append(trade)
            
            for trade_id, trade_list in trade_groups.items():
                # 找到该交易组的出场时间和总收益
                exit_time = None
                total_profit = 0.0
                total_capital = 0.0
                
                for trade in trade_list:
                    if trade.get('status') == 'closed':
                        exit_time = trade.get('exit_time')
                        total_profit += trade.get('profit', 0.0)
                        total_capital += trade.get('capital_allocated', 0.0)
                
                if exit_time and total_capital > 0:
                    # 计算该交易的收益率（百分比）
                    trade_return_pct = (total_profit / total_capital) * 100
                    
                    # 转换时间格式
                    if isinstance(exit_time, str):
                        try:
                            exit_time = pd.to_datetime(exit_time)
                        except:
                            continue
                    elif isinstance(exit_time, (int, float)):
                        exit_time = pd.to_datetime(exit_time, unit='ms')
                    
                    # 找到最接近的时间点
                    try:
                        closest_idx = price_data.index.get_indexer([exit_time], method='nearest')[0]
                        if closest_idx >= 0 and closest_idx < len(price_data):
                            # 只在该时间点显示单笔交易收益率
                            # 正收益在上方，负收益在下方（通过正负值自然实现）
                            returns_series.iloc[closest_idx] = trade_return_pct
                    except:
                        continue
            
            return returns_series
            
        except Exception as e:
            print(f"⚠️ 计算收益率指标失败: {e}")
            return None
    
    def generate_strategy_chart(self, 
                              price_data: pd.DataFrame,
                              trades: List[Dict[str, Any]],
                              strategy_name: str,
                              ema_short: Optional[pd.Series] = None,
                              ema_long: Optional[pd.Series] = None,
                              timeframe: str = "30min") -> str:
        """
        生成策略交易图表
        
        Args:
            price_data: 价格数据 (OHLCV格式)
            trades: 交易记录列表
            strategy_name: 策略名称
            ema_short: 短期EMA数据
            ema_long: 长期EMA数据
            timeframe: 时间框架
            
        Returns:
            生成的图表文件路径
        """
        try:
            # 准备数据
            df = price_data.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'open_time' in df.columns:
                    df.set_index('open_time', inplace=True)
                elif 'timestamp' in df.columns:
                    df.set_index('timestamp', inplace=True)
            
            # 确保列名正确
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                # 尝试重命名列
                column_mapping = {
                    'Open': 'open', 'High': 'high', 'Low': 'low', 
                    'Close': 'close', 'Volume': 'volume'
                }
                df.rename(columns=column_mapping, inplace=True)
            
            # 准备交易标记
            buy_signals = []  # 买入信号 (entry_time, entry_price, action, trade_type, trade_index)
            sell_signals = []  # 卖出信号 (exit_time, exit_price, action, trade_type, trade_index)
            
            # 按交易ID分组，只对初始入场进行编号
            trade_groups = {}
            trade_index = 0
            processed_exits = set()  # 记录已处理的出场信号，避免重复
            
            for trade in trades:
                if isinstance(trade, dict):
                    trade_id = trade.get('trade_id', 0)
                    action = trade.get('action', '')
                    trade_type = trade.get('type', 'long')
                    
                    # 只对初始入场交易进行编号
                    if action == '初始入场':
                        if trade_id not in trade_groups:
                            trade_index += 1
                            trade_groups[trade_id] = trade_index
                    
                    # 处理入场信号 - 只处理初始入场
                    if action == '初始入场':
                        entry_time = trade.get('entry_time')
                        entry_price = trade.get('entry_price', 0)
                        
                        if entry_time and entry_price:
                            # 获取交易索引
                            current_trade_index = trade_groups.get(trade_id, trade_index)
                            
                            # 转换时间戳
                            if isinstance(entry_time, str):
                                try:
                                    entry_time = pd.to_datetime(entry_time)
                                except:
                                    continue
                            elif isinstance(entry_time, (int, float)):
                                entry_time = pd.to_datetime(entry_time, unit='ms')
                            
                            # 根据交易类型添加入场信号
                            if trade_type == 'long':
                                # 多头入场 = 买入信号
                                action_label = f"交易{current_trade_index}-多头入场"
                                buy_signals.append((entry_time, entry_price, action_label, trade_type, current_trade_index))
                            else:
                                # 空头入场 = 卖出信号
                                action_label = f"交易{current_trade_index}-空头入场"
                                sell_signals.append((entry_time, entry_price, action_label, trade_type, current_trade_index))
                    
                    # 处理出场信号 - 只处理初始入场的出场，避免重复
                    if action == '初始入场':
                        exit_time = trade.get('exit_time')
                        exit_price = trade.get('exit_price', 0)
                        
                        if exit_time and exit_price and trade_id not in processed_exits:
                            processed_exits.add(trade_id)
                            
                            # 获取交易索引
                            current_trade_index = trade_groups.get(trade_id, trade_index)
                            
                            # 转换时间戳
                            if isinstance(exit_time, str):
                                try:
                                    exit_time = pd.to_datetime(exit_time)
                                except:
                                    continue
                            elif isinstance(exit_time, (int, float)):
                                exit_time = pd.to_datetime(exit_time, unit='ms')
                            
                            # 根据交易类型添加出场信号
                            if trade_type == 'long':
                                # 多头出场 = 卖出信号
                                action_label = f"交易{current_trade_index}-多头出场"
                                sell_signals.append((exit_time, exit_price, action_label, trade_type, current_trade_index))
                            else:
                                # 空头出场 = 买入信号
                                action_label = f"交易{current_trade_index}-空头出场"
                                buy_signals.append((exit_time, exit_price, action_label, trade_type, current_trade_index))
            
            # 创建附加绘图数据
            addplot_data = []
            
            # 添加EMA线
            if ema_short is not None and len(ema_short) > 0:
                addplot_data.append(mpf.make_addplot(ema_short, color='blue', width=1.5, label='EMA短'))
            
            if ema_long is not None and len(ema_long) > 0:
                addplot_data.append(mpf.make_addplot(ema_long, color='red', width=1.5, label='EMA长'))
            
            # 不在这里添加交易信号标记，而是在绘制完成后使用matplotlib添加
            
            # 生成图表
            filename = f"{strategy_name}_{timeframe}_交易图表.png"
            filepath = os.path.join(self.output_dir, filename)
            
            # 设置图表样式
            style = mpf.make_mpf_style(
                base_mpf_style='charles',
                gridstyle='-',
                gridcolor='lightgray',
                facecolor='white'
            )
            
            # 确保中文字体配置与全局设置一致
            # 字体配置已在 _setup_chinese_font 中完成，这里无需重复设置
            
            # 计算收益率指标
            returns_data = self._calculate_returns_indicator(df, trades)
            
            # 如果有收益率数据，添加到附加绘图中
            if returns_data is not None and not returns_data.isna().all():
                # 分离正负收益率
                positive_returns = returns_data.copy()
                negative_returns = returns_data.copy()
                
                # 正收益率：保留正值，负值设为NaN
                positive_returns[positive_returns <= 0] = float('nan')
                # 负收益率：保留负值，正值设为NaN
                negative_returns[negative_returns > 0] = float('nan')
                
                # 创建正收益率柱状图（绿色）
                if not positive_returns.isna().all():
                    positive_plot = mpf.make_addplot(positive_returns, 
                                                   panel=1, 
                                                   type='bar',
                                                   color='green', 
                                                   alpha=0.8,
                                                   ylabel='单笔收益率 (%)')
                    if addplot_data:
                        addplot_data.append(positive_plot)
                    else:
                        addplot_data = [positive_plot]
                
                # 创建负收益率柱状图（红色）
                if not negative_returns.isna().all():
                    negative_plot = mpf.make_addplot(negative_returns, 
                                                   panel=1, 
                                                   type='bar',
                                                   color='red', 
                                                   alpha=0.8,
                                                   ylabel='单笔收益率 (%)')
                    if addplot_data:
                        addplot_data.append(negative_plot)
                    else:
                        addplot_data = [negative_plot]
            
            # 创建图表 - 移除成交量显示
            fig, axes = mpf.plot(df,
                               type='candle',
                               style=style,
                               addplot=addplot_data if addplot_data else None,
                               volume=False,  # 关闭成交量显示
                               title=f'{strategy_name} - {timeframe} 交易图表',
                               ylabel='价格 (USDT)',
                               ylabel_lower='累计收益率 (%)',
                               figsize=(16, 10),
                               returnfig=True)
            
            # 确保图表标题使用中文字体
            if hasattr(fig, 'suptitle'):
                fig.suptitle(f'{strategy_name} - {timeframe} 交易图表', 
                           fontsize=14, fontweight='bold')
            
            # 添加交易标记
            # mplfinance返回的axes可能是单个轴或轴数组
            main_ax = axes[0] if isinstance(axes, (list, tuple)) else axes
            self._add_trade_markers(main_ax, df, buy_signals, sell_signals)
            
            # 添加EMA交叉点标记
            if ema_short is not None and ema_long is not None:
                golden_crosses, death_crosses = self._detect_ema_crossovers(ema_short, ema_long)
                if golden_crosses or death_crosses:
                    self._add_ema_crossover_markers(main_ax, golden_crosses, death_crosses, df.index)
                    print(f"✅ 检测到 {len(golden_crosses)} 个金叉点和 {len(death_crosses)} 个死叉点")
            
            # 添加收益率数值标签
            if returns_data is not None and not returns_data.isna().all():
                # 获取收益率子图的轴（通常是第二个轴）
                if isinstance(axes, (list, tuple)) and len(axes) > 1:
                    returns_ax = axes[1]
                    self._add_returns_labels(returns_ax, returns_data)
            
            # 保存图表
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ 图表已生成: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ 生成图表时出错: {str(e)}")
            return None
    
    def generate_performance_chart(self, 
                                 capital_history: List[float],
                                 timestamps: List[Any],
                                 strategy_name: str) -> str:
        """
        生成资金曲线图表
        
        Args:
            capital_history: 资金历史记录
            timestamps: 时间戳列表
            strategy_name: 策略名称
            
        Returns:
            生成的图表文件路径
        """
        try:
            # 创建DataFrame
            df = pd.DataFrame({
                'timestamp': timestamps,
                'capital': capital_history
            })
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 创建图表
            plt.figure(figsize=(12, 6))
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            plt.plot(df['timestamp'], df['capital'], linewidth=2, color='blue')
            plt.title(f'{strategy_name} - 资金曲线', fontsize=16, fontweight='bold')
            plt.xlabel('时间', fontsize=12)
            plt.ylabel('资金 (USDT)', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # 格式化x轴
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=6))
            plt.xticks(rotation=45)
            
            # 添加统计信息
            initial_capital = capital_history[0] if capital_history else 0
            final_capital = capital_history[-1] if capital_history else 0
            total_return = ((final_capital - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0
            
            info_text = f'初始资金: ${initial_capital:,.2f}\n最终资金: ${final_capital:,.2f}\n总收益率: {total_return:.2f}%'
            plt.text(0.02, 0.98, info_text,
                    transform=plt.gca().transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            # 保存图表
            filename = f"{strategy_name}_资金曲线.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ 资金曲线图已生成: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ 生成资金曲线图时出错: {str(e)}")
            return None
    
    def generate_trade_analysis_chart(self, 
                                    trades: List[Dict[str, Any]], 
                                    strategy_name: str) -> str:
        """
        生成交易分析图表
        
        Args:
            trades: 交易记录列表
            strategy_name: 策略名称
            
        Returns:
            生成的图表文件路径
        """
        try:
            if not trades:
                print("⚠️ 没有交易记录，无法生成交易分析图表")
                return None
            
            # 提取盈亏数据 - 汇总完整交易的利润
            profits = []
            
            # 按trade_id分组计算完整交易的利润
            trade_groups = {}
            for trade in trades:
                if trade.get('status') == 'closed':
                    trade_id = trade.get('trade_id')
                    if trade_id not in trade_groups:
                        trade_groups[trade_id] = []
                    trade_groups[trade_id].append(trade)
            
            # 计算每个完整交易的总利润
            for trade_id, trade_list in trade_groups.items():
                total_profit = sum(t.get('profit', 0) for t in trade_list)
                profits.append(total_profit)
            
            if not profits:
                print("⚠️ 没有有效的盈亏数据")
                return None
            
            profits_for_stats = profits
            
            # 创建子图
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            fig.suptitle(f'{strategy_name} - 交易分析', fontsize=16, fontweight='bold')
            
            # 1. 盈亏分布直方图
            ax1.hist(profits_for_stats, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax1.set_title('盈亏分布')
            ax1.set_xlabel('盈亏 (USDT)')
            ax1.set_ylabel('频次')
            ax1.grid(True, alpha=0.3)
            
            # 2. 累计盈亏曲线
            cumulative_profits = pd.Series(profits_for_stats).cumsum()
            ax2.plot(range(len(cumulative_profits)), cumulative_profits, linewidth=2, color='green')
            ax2.set_title('累计盈亏曲线')
            ax2.set_xlabel('交易次数')
            ax2.set_ylabel('累计盈亏 (USDT)')
            ax2.grid(True, alpha=0.3)
            
            # 3. 盈亏比例饼图
            profitable_trades = sum(1 for p in profits_for_stats if p > 0)
            losing_trades = sum(1 for p in profits_for_stats if p < 0)
            breakeven_trades = sum(1 for p in profits_for_stats if p == 0)
            
            labels = ['盈利交易', '亏损交易', '平手交易']
            sizes = [profitable_trades, losing_trades, breakeven_trades]
            colors = ['green', 'red', 'gray']
            
            # 过滤掉为0的数据
            filtered_data = [(label, size, color) for label, size, color in zip(labels, sizes, colors) if size > 0]
            if filtered_data:
                labels, sizes, colors = zip(*filtered_data)
                ax3.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax3.set_title('交易结果分布')
            
            # 4. 交易统计表
            ax4.axis('off')
            stats_data = [
                ['总交易次数', len(profits_for_stats)],
                ['盈利交易', profitable_trades],
                ['亏损交易', losing_trades],
                ['胜率', f"{profitable_trades/len(profits_for_stats)*100:.2f}%" if profits_for_stats else "0%"],
                ['平均盈利', f"{sum(p for p in profits_for_stats if p > 0)/max(profitable_trades, 1):.2f}"],
                ['平均亏损', f"{sum(p for p in profits_for_stats if p < 0)/max(losing_trades, 1):.2f}"],
                ['最大盈利', f"{max(profits_for_stats):.2f}"],
                ['最大亏损', f"{min(profits_for_stats):.2f}"],
                ['总盈亏', f"{sum(profits_for_stats):.2f}"]
            ]
            
            table = ax4.table(cellText=stats_data, 
                            colLabels=['指标', '数值'],
                            cellLoc='center',
                            loc='center',
                            bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2)
            ax4.set_title('交易统计', pad=20)
            
            # 保存图表
            filename = f"{strategy_name}_交易分析.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ 交易分析图已生成: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ 生成交易分析图时出错: {str(e)}")
            return None
    
    def _add_trade_markers(self, ax, df, buy_signals, sell_signals):
        """
        在图表上添加交易标记（箭头和文字标签）
        
        Args:
            ax: matplotlib轴对象
            df: 价格数据DataFrame
            buy_signals: 买入信号列表 [(time, price, action, trade_type, trade_index), ...]
            sell_signals: 卖出信号列表 [(time, price, action, trade_type, trade_index), ...]
        """
        try:
            # 设置中文字体
            from matplotlib import font_manager
            import matplotlib.pyplot as plt
            
            # 确保中文字体配置
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 获取价格范围用于调整标签位置
            price_range = df['high'].max() - df['low'].min()
            offset_ratio = 0.02  # 偏移比例
            
            # 用于跟踪相近位置的标签，避免重叠
            nearby_positions = []
            
            # 处理买入信号
            for signal_data in buy_signals:
                if len(signal_data) >= 5:
                    time, price, action, trade_type, trade_index = signal_data
                else:
                    # 兼容旧格式
                    time, price, action = signal_data[:3]
                    trade_type = 'long'
                    trade_index = 1
                
                # 找到最接近的时间点在df中的位置
                try:
                    closest_idx = df.index.get_indexer([time], method='nearest')[0]
                    if closest_idx >= 0 and closest_idx < len(df):
                        x_pos = closest_idx
                        y_pos = price
                        
                        # 根据交易类型和动作确定标签
                        if '入场' in action:
                            # 入场标签
                            if trade_type == 'long':
                                label = f'{trade_index}多'
                                color = 'green'
                            else:
                                label = f'{trade_index}空'
                                color = 'red'
                        elif '出场' in action:
                            # 出场标签（空头出场 = 买入平仓）
                            label = f'{trade_index}平'
                            color = 'blue'
                        else:
                            label = '买'
                            color = 'green'
                        
                        # 计算偏移以避免重叠
                        horizontal_offset = 0
                        vertical_multiplier = 1
                        
                        for pos_x, pos_y, pos_type in nearby_positions:
                            if abs(pos_x - x_pos) <= 3 and pos_type == 'buy':  # 相近位置
                                vertical_multiplier += 0.8
                                if abs(pos_x - x_pos) <= 1:  # 非常接近
                                    horizontal_offset = 2 if horizontal_offset == 0 else -horizontal_offset
                        
                        vertical_offset = price_range * offset_ratio * vertical_multiplier
                        text_y = y_pos + vertical_offset
                        text_x = x_pos + horizontal_offset
                        
                        # 记录这个位置
                        nearby_positions.append((x_pos, y_pos, 'buy'))
                        
                        # 添加箭头标记
                        ax.annotate(label, 
                                  xy=(x_pos, y_pos), 
                                  xytext=(text_x, text_y),
                                  arrowprops=dict(arrowstyle='->', 
                                                color=color, 
                                                lw=1.5,
                                                connectionstyle="arc3,rad=0"),
                                  fontsize=9, 
                                  fontweight='bold',
                                  color=color,
                                  ha='center',
                                  va='bottom',
                                  fontfamily='SimHei',  # 明确指定中文字体
                                  bbox=dict(boxstyle='round,pad=0.2', 
                                          facecolor='white', 
                                          edgecolor=color,
                                          alpha=0.9,
                                          linewidth=1))
                except Exception as e:
                    continue
            
            # 处理卖出信号
            for signal_data in sell_signals:
                if len(signal_data) >= 5:
                    time, price, action, trade_type, trade_index = signal_data
                else:
                    # 兼容旧格式
                    time, price, action = signal_data[:3]
                    trade_type = 'short'
                    trade_index = 1
                
                try:
                    closest_idx = df.index.get_indexer([time], method='nearest')[0]
                    if closest_idx >= 0 and closest_idx < len(df):
                        x_pos = closest_idx
                        y_pos = price
                        
                        # 根据交易类型和动作确定标签
                        if '入场' in action:
                            # 入场标签（空头入场 = 卖出开仓）
                            if trade_type == 'short':
                                label = f'{trade_index}空'
                                color = 'red'
                            else:
                                label = f'{trade_index}多'
                                color = 'green'
                        elif '出场' in action:
                            # 出场标签（多头出场 = 卖出平仓）
                            label = f'{trade_index}平'
                            color = 'blue'
                        else:
                            label = '卖'
                            color = 'red'
                        
                        # 计算偏移以避免重叠
                        horizontal_offset = 0
                        vertical_multiplier = 1
                        
                        for pos_x, pos_y, pos_type in nearby_positions:
                            if abs(pos_x - x_pos) <= 3 and pos_type == 'sell':  # 相近位置
                                vertical_multiplier += 0.8
                                if abs(pos_x - x_pos) <= 1:  # 非常接近
                                    horizontal_offset = 2 if horizontal_offset == 0 else -horizontal_offset
                        
                        vertical_offset = price_range * offset_ratio * vertical_multiplier
                        text_y = y_pos - vertical_offset
                        text_x = x_pos + horizontal_offset
                        
                        # 记录这个位置
                        nearby_positions.append((x_pos, y_pos, 'sell'))
                        
                        # 添加箭头标记
                        ax.annotate(label, 
                                  xy=(x_pos, y_pos), 
                                  xytext=(text_x, text_y),
                                  arrowprops=dict(arrowstyle='->', 
                                                color=color, 
                                                lw=1.5,
                                                connectionstyle="arc3,rad=0"),
                                  fontsize=9, 
                                  fontweight='bold',
                                  color=color,
                                  ha='center',
                                  va='top',
                                  fontfamily='SimHei',  # 明确指定中文字体
                                  bbox=dict(boxstyle='round,pad=0.2', 
                                          facecolor='white', 
                                          edgecolor=color,
                                          alpha=0.9,
                                          linewidth=1))
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"❌ 添加交易标记时出错: {str(e)}")

    def _add_returns_labels(self, ax, returns_data: pd.Series):
        """
        在收益率柱状图上添加数值标签
        
        Args:
            ax: matplotlib轴对象（收益率子图）
            returns_data: 收益率数据Series
        """
        try:
            # 设置中文字体
            import matplotlib.pyplot as plt
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 遍历所有非NaN的收益率数据
            for timestamp, value in returns_data.items():
                if pd.notna(value) and value != 0:  # 只显示有效的非零收益率
                    # 格式化收益率为百分比
                    label_text = f"{value:.1f}%"
                    
                    # 使用时间戳作为x坐标
                    x_pos = timestamp
                    y_pos = value
                    
                    # 根据正负值调整标签位置
                    if value > 0:
                        # 正值：标签在柱子上方
                        va = 'bottom'
                        y_offset = abs(value) * 0.1  # 向上偏移
                        text_y = y_pos + y_offset
                        color = 'darkgreen'
                    else:
                        # 负值：标签在柱子下方
                        va = 'top'
                        y_offset = abs(value) * 0.1  # 向下偏移
                        text_y = y_pos - y_offset
                        color = 'darkred'
                    
                    # 添加文本标签
                    ax.text(x_pos, text_y, label_text,
                           ha='center', va=va,
                           fontsize=8,
                           fontweight='bold',
                           color=color,
                           fontfamily='SimHei',
                           bbox=dict(boxstyle='round,pad=0.2',
                                   facecolor='white',
                                   edgecolor=color,
                                   alpha=0.8,
                                   linewidth=0.8))
                           
        except Exception as e:
            print(f"❌ 添加收益率标签时出错: {str(e)}")

    def _detect_ema_crossovers(self, ema_short: pd.Series, ema_long: pd.Series) -> tuple:
        """
        检测EMA交叉点
        
        Args:
            ema_short: 短期EMA数据
            ema_long: 长期EMA数据
            
        Returns:
            tuple: (golden_crosses, death_crosses) 
                   golden_crosses: 金叉点列表 [(时间, 价格), ...]
                   death_crosses: 死叉点列表 [(时间, 价格), ...]
        """
        try:
            if ema_short is None or ema_long is None or len(ema_short) == 0 or len(ema_long) == 0:
                return [], []
            
            # 确保两个序列有相同的索引
            common_index = ema_short.index.intersection(ema_long.index)
            if len(common_index) < 2:
                return [], []
            
            ema_short_aligned = ema_short.reindex(common_index)
            ema_long_aligned = ema_long.reindex(common_index)
            
            # 计算差值
            diff = ema_short_aligned - ema_long_aligned
            
            # 检测交叉点
            golden_crosses = []  # 金叉：短期EMA从下方穿越长期EMA
            death_crosses = []   # 死叉：短期EMA从上方穿越长期EMA
            
            for i in range(1, len(diff)):
                prev_diff = diff.iloc[i-1]
                curr_diff = diff.iloc[i]
                
                # 跳过NaN值
                if pd.isna(prev_diff) or pd.isna(curr_diff):
                    continue
                
                # 金叉：前一个点短期EMA在长期EMA下方，当前点在上方
                if prev_diff <= 0 and curr_diff > 0:
                    cross_time = diff.index[i]
                    cross_price = (ema_short_aligned.iloc[i] + ema_long_aligned.iloc[i]) / 2
                    golden_crosses.append((cross_time, cross_price))
                
                # 死叉：前一个点短期EMA在长期EMA上方，当前点在下方
                elif prev_diff >= 0 and curr_diff < 0:
                    cross_time = diff.index[i]
                    cross_price = (ema_short_aligned.iloc[i] + ema_long_aligned.iloc[i]) / 2
                    death_crosses.append((cross_time, cross_price))
            
            return golden_crosses, death_crosses
            
        except Exception as e:
            print(f"❌ 检测EMA交叉点时出错: {str(e)}")
            return [], []

    def _add_ema_crossover_markers(self, ax, golden_crosses: list, death_crosses: list, df_index):
        """
        在图表上添加EMA交叉点标记
        
        Args:
            ax: matplotlib轴对象
            golden_crosses: 金叉点列表
            death_crosses: 死叉点列表
            df_index: DataFrame的索引，用于转换时间戳到数值位置
        """
        try:
            # 添加金叉标记（小绿色点）
            for cross_time, cross_price in golden_crosses:
                # 将时间戳转换为数值位置
                try:
                    if cross_time in df_index:
                        x_pos = df_index.get_loc(cross_time)
                        ax.scatter(x_pos, cross_price, 
                                  marker='o', s=20, color='green', 
                                  alpha=0.8, zorder=5)
                except Exception as e:
                    print(f"⚠️ 跳过金叉点 {cross_time}: {str(e)}")
                    continue
            
            # 添加死叉标记（小蓝色点）
            for cross_time, cross_price in death_crosses:
                # 将时间戳转换为数值位置
                try:
                    if cross_time in df_index:
                        x_pos = df_index.get_loc(cross_time)
                        ax.scatter(x_pos, cross_price, 
                                  marker='o', s=20, color='blue', 
                                  alpha=0.8, zorder=5)
                except Exception as e:
                    print(f"⚠️ 跳过死叉点 {cross_time}: {str(e)}")
                    continue
            
        except Exception as e:
            print(f"❌ 添加EMA交叉点标记时出错: {str(e)}")


def create_chart_for_strategy(strategy_instance, price_data: pd.DataFrame, timeframe: str = "30min"):
    """
    为策略实例创建图表的便捷函数
    
    Args:
        strategy_instance: 策略实例
        price_data: 价格数据
        timeframe: 时间框架
    """
    chart_gen = ChartGenerator()
    
    # 获取策略数据
    strategy_name = getattr(strategy_instance, 'strategy_name', '未知策略')
    trades = getattr(strategy_instance, 'detailed_trades', getattr(strategy_instance, 'trades', []))
    
    # 获取EMA数据（如果存在）
    ema_short = getattr(strategy_instance, 'ema_short_values', None)
    ema_long = getattr(strategy_instance, 'ema_long_values', None)
    
    # 生成主要交易图表
    chart_gen.generate_strategy_chart(
        price_data=price_data,
        trades=trades,
        strategy_name=strategy_name,
        ema_short=ema_short,
        ema_long=ema_long,
        timeframe=timeframe
    )
    
    # 生成交易分析图表
    chart_gen.generate_trade_analysis_chart(trades, strategy_name)
    
    # 生成资金曲线图（如果有资金历史记录）
    capital_history = getattr(strategy_instance, 'capital_history', None)
    timestamps = getattr(strategy_instance, 'timestamp_history', None)
    
    if capital_history and timestamps:
        chart_gen.generate_performance_chart(capital_history, timestamps, strategy_name)