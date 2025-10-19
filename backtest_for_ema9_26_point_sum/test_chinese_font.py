#!/usr/bin/env python3
"""
测试中文字体显示
"""

import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 创建测试数据
x = np.linspace(0, 10, 100)
y = np.sin(x)

# 创建图表
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', label='正弦波')
plt.title('中文字体测试 - EMA交叉点分析')
plt.xlabel('时间（天）')
plt.ylabel('价格（美元）')
plt.legend()
plt.grid(True, alpha=0.3)

# 添加一些中文注释
plt.text(2, 0.5, '金叉信号', fontsize=12, color='red')
plt.text(6, -0.5, '死叉信号', fontsize=12, color='green')

plt.tight_layout()
plt.savefig('/home/ubuntu/Code/quant/backtest_for_rule/chinese_font_test.png', dpi=300, bbox_inches='tight')
plt.close()

print("中文字体测试完成！")
print("测试图表已保存到: chinese_font_test.png")