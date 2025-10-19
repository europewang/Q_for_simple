#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def analyze_price_diff_distribution():
    """分析价格差值分布并提供突兀点识别建议"""
    
    # 读取所有CSV文件
    period_dir = Path("period_analysis")
    csv_files = list(period_dir.glob("ema_results_*.csv"))
    
    all_data = []
    period_stats = []
    
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        # 排除第一个点（价格差为0）
        valid_data = df[df['price_diff_abs'] > 0]['price_diff_abs']
        
        if len(valid_data) > 0:
            period_name = csv_file.stem.replace('ema_results_', '')
            
            stats = {
                'period': period_name,
                'count': len(valid_data),
                'mean': valid_data.mean(),
                'median': valid_data.median(),
                'std': valid_data.std(),
                'min': valid_data.min(),
                'max': valid_data.max(),
                'q25': valid_data.quantile(0.25),
                'q75': valid_data.quantile(0.75),
                'q90': valid_data.quantile(0.90),
                'q95': valid_data.quantile(0.95),
                'q99': valid_data.quantile(0.99)
            }
            
            period_stats.append(stats)
            all_data.extend(valid_data.tolist())
    
    # 整体统计
    all_data = np.array(all_data)
    overall_stats = {
        'count': len(all_data),
        'mean': np.mean(all_data),
        'median': np.median(all_data),
        'std': np.std(all_data),
        'min': np.min(all_data),
        'max': np.max(all_data),
        'q25': np.percentile(all_data, 25),
        'q75': np.percentile(all_data, 75),
        'q90': np.percentile(all_data, 90),
        'q95': np.percentile(all_data, 95),
        'q99': np.percentile(all_data, 99)
    }
    
    # 打印统计结果
    print("=" * 80)
    print("价格差值分布分析报告")
    print("=" * 80)
    
    print(f"\n整体统计 (总计 {overall_stats['count']} 个有效数据点):")
    print(f"平均值: {overall_stats['mean']:.2f}")
    print(f"中位数: {overall_stats['median']:.2f}")
    print(f"标准差: {overall_stats['std']:.2f}")
    print(f"最小值: {overall_stats['min']:.2f}")
    print(f"最大值: {overall_stats['max']:.2f}")
    print(f"25%分位数: {overall_stats['q25']:.2f}")
    print(f"75%分位数: {overall_stats['q75']:.2f}")
    print(f"90%分位数: {overall_stats['q90']:.2f}")
    print(f"95%分位数: {overall_stats['q95']:.2f}")
    print(f"99%分位数: {overall_stats['q99']:.2f}")
    
    # 计算IQR
    iqr = overall_stats['q75'] - overall_stats['q25']
    print(f"四分位距(IQR): {iqr:.2f}")
    
    print("\n各期间统计:")
    print("-" * 100)
    print(f"{'期间':<20} {'数量':<6} {'均值':<8} {'中位数':<8} {'标准差':<8} {'90%':<8} {'95%':<8} {'99%':<8}")
    print("-" * 100)
    
    for stats in period_stats:
        print(f"{stats['period']:<20} {stats['count']:<6} {stats['mean']:<8.1f} {stats['median']:<8.1f} "
              f"{stats['std']:<8.1f} {stats['q90']:<8.1f} {stats['q95']:<8.1f} {stats['q99']:<8.1f}")
    
    # 突兀点识别方法建议
    print("\n" + "=" * 80)
    print("突兀点识别方法建议")
    print("=" * 80)
    
    # 方法1: 标准差法
    threshold_1std = overall_stats['mean'] + overall_stats['std']
    threshold_2std = overall_stats['mean'] + 2 * overall_stats['std']
    threshold_3std = overall_stats['mean'] + 3 * overall_stats['std']
    
    outliers_1std = np.sum(all_data > threshold_1std)
    outliers_2std = np.sum(all_data > threshold_2std)
    outliers_3std = np.sum(all_data > threshold_3std)
    
    print(f"\n方法1: 标准差法")
    print(f"均值 + 1σ = {threshold_1std:.2f}, 突兀点数量: {outliers_1std} ({outliers_1std/len(all_data)*100:.1f}%)")
    print(f"均值 + 2σ = {threshold_2std:.2f}, 突兀点数量: {outliers_2std} ({outliers_2std/len(all_data)*100:.1f}%)")
    print(f"均值 + 3σ = {threshold_3std:.2f}, 突兀点数量: {outliers_3std} ({outliers_3std/len(all_data)*100:.1f}%)")
    
    # 方法2: 四分位数法 (IQR)
    threshold_iqr_15 = overall_stats['q75'] + 1.5 * iqr
    threshold_iqr_3 = overall_stats['q75'] + 3 * iqr
    
    outliers_iqr_15 = np.sum(all_data > threshold_iqr_15)
    outliers_iqr_3 = np.sum(all_data > threshold_iqr_3)
    
    print(f"\n方法2: 四分位数法 (IQR)")
    print(f"Q3 + 1.5×IQR = {threshold_iqr_15:.2f}, 突兀点数量: {outliers_iqr_15} ({outliers_iqr_15/len(all_data)*100:.1f}%)")
    print(f"Q3 + 3×IQR = {threshold_iqr_3:.2f}, 突兀点数量: {outliers_iqr_3} ({outliers_iqr_3/len(all_data)*100:.1f}%)")
    
    # 方法3: 百分位数法
    outliers_90 = np.sum(all_data > overall_stats['q90'])
    outliers_95 = np.sum(all_data > overall_stats['q95'])
    outliers_99 = np.sum(all_data > overall_stats['q99'])
    
    print(f"\n方法3: 百分位数法")
    print(f"90%分位数 = {overall_stats['q90']:.2f}, 突兀点数量: {outliers_90} ({outliers_90/len(all_data)*100:.1f}%)")
    print(f"95%分位数 = {overall_stats['q95']:.2f}, 突兀点数量: {outliers_95} ({outliers_95/len(all_data)*100:.1f}%)")
    print(f"99%分位数 = {overall_stats['q99']:.2f}, 突兀点数量: {outliers_99} ({outliers_99/len(all_data)*100:.1f}%)")
    
    # 推荐方案
    print(f"\n" + "=" * 80)
    print("推荐方案")
    print("=" * 80)
    print(f"基于数据分析，推荐以下突兀点识别方案：")
    print(f"")
    print(f"1. 保守方案 (约1-2%突兀点): 使用99%分位数 = {overall_stats['q99']:.2f}")
    print(f"2. 中等方案 (约5%突兀点): 使用95%分位数 = {overall_stats['q95']:.2f}")
    print(f"3. 宽松方案 (约10%突兀点): 使用90%分位数 = {overall_stats['q90']:.2f}")
    print(f"4. IQR方案 (经典统计): Q3 + 1.5×IQR = {threshold_iqr_15:.2f}")
    print(f"5. 标准差方案: 均值 + 2σ = {threshold_2std:.2f}")
    
    # 创建分布图
    create_distribution_plot(all_data, overall_stats, threshold_2std, threshold_iqr_15)
    
    return {
        'overall_stats': overall_stats,
        'period_stats': period_stats,
        'thresholds': {
            'q90': overall_stats['q90'],
            'q95': overall_stats['q95'],
            'q99': overall_stats['q99'],
            'mean_2std': threshold_2std,
            'iqr_15': threshold_iqr_15
        }
    }

def create_distribution_plot(data, stats, threshold_2std, threshold_iqr):
    """创建数据分布图"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # 直方图
    ax1.hist(data, bins=50, alpha=0.7, color='skyblue', edgecolor='black')
    ax1.axvline(stats['mean'], color='red', linestyle='-', label=f'均值 ({stats["mean"]:.1f})')
    ax1.axvline(stats['median'], color='green', linestyle='-', label=f'中位数 ({stats["median"]:.1f})')
    ax1.axvline(stats['q90'], color='orange', linestyle='--', label=f'90%分位数 ({stats["q90"]:.1f})')
    ax1.axvline(stats['q95'], color='purple', linestyle='--', label=f'95%分位数 ({stats["q95"]:.1f})')
    ax1.axvline(stats['q99'], color='brown', linestyle='--', label=f'99%分位数 ({stats["q99"]:.1f})')
    
    ax1.set_xlabel('价格差值绝对值 (USDT)')
    ax1.set_ylabel('频次')
    ax1.set_title('价格差值分布直方图')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 箱线图
    ax2.boxplot(data, vert=True)
    ax2.set_ylabel('价格差值绝对值 (USDT)')
    ax2.set_title('价格差值分布箱线图')
    ax2.grid(True, alpha=0.3)
    
    # 添加统计信息
    textstr = f'总数据点: {len(data)}\n均值: {stats["mean"]:.1f}\n中位数: {stats["median"]:.1f}\n标准差: {stats["std"]:.1f}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax2.text(0.02, 0.98, textstr, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig('period_analysis/price_diff_distribution_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\n分布图已保存到: period_analysis/price_diff_distribution_analysis.png")

if __name__ == "__main__":
    analyze_price_diff_distribution()