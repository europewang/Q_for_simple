#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字体测试脚本
验证中文字体显示效果
"""

import matplotlib.pyplot as plt
import numpy as np
from font_config import setup_chinese_fonts, suppress_font_warnings

def test_chinese_font():
    """测试中文字体显示效果"""
    
    # 配置字体
    suppress_font_warnings()
    main_font = setup_chinese_fonts()
    
    # 创建测试数据
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 绘制数据
    ax.plot(x, y1, label='正弦波', linewidth=2, color='blue')
    ax.plot(x, y2, label='余弦波', linewidth=2, color='red')
    
    # 设置中文标题和标签
    ax.set_title('中文字体测试 - 数学函数图表', fontsize=16, fontweight='bold')
    ax.set_xlabel('时间 (秒)', fontsize=12)
    ax.set_ylabel('幅度', fontsize=12)
    
    # 添加图例
    ax.legend(fontsize=12)
    
    # 添加网格
    ax.grid(True, alpha=0.3)
    
    # 添加文本注释
    ax.text(2, 0.8, '这是中文注释文本', fontsize=12, 
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))
    
    # 保存图表
    plt.tight_layout()
    plt.savefig('output/charts/中文字体测试.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("✅ 中文字体测试完成！")
    print(f"   使用字体: {main_font}")
    print("   测试图表已保存到: output/charts/中文字体测试.png")

if __name__ == "__main__":
    test_chinese_font()