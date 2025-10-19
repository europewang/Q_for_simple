#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字体配置模块
统一管理matplotlib和mplfinance的中文字体设置
"""

import os
import platform
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import warnings

def setup_chinese_fonts():
    """
    配置中文字体支持，消除字体警告
    """
    try:
        # 根据操作系统选择合适的中文字体
        system = platform.system()
        if system == "Windows":
            fonts = ['Microsoft YaHei', 'SimSun', 'KaiTi', 'FangSong', 'SimHei']
        elif system == "Darwin":  # macOS
            fonts = ['PingFang SC', 'Hiragino Sans GB', 'STHeiti', 'Arial Unicode MS']
        else:  # Linux
            fonts = [
                'WenQuanYi Micro Hei',  # 文泉驿微米黑
                'WenQuanYi Zen Hei',    # 文泉驿正黑
                'Noto Sans CJK SC',     # Google Noto字体
                'Source Han Sans SC',   # 思源黑体
                'DejaVu Sans'           # 备用字体
            ]
        
        # 检查可用字体
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        selected_font = None
        
        for font_name in fonts:
            if font_name in available_fonts:
                selected_font = font_name
                break
            # 尝试模糊匹配
            for available in available_fonts:
                if font_name.lower().replace(' ', '') in available.lower().replace(' ', ''):
                    selected_font = available
                    break
            if selected_font:
                break
        
        # 如果没有找到中文字体，尝试直接使用字体文件路径
        if not selected_font and system == "Linux":
            font_paths = [
                '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        # 添加字体到matplotlib
                        fm.fontManager.addfont(font_path)
                        # 获取字体名称
                        font_prop = fm.FontProperties(fname=font_path)
                        selected_font = font_prop.get_name()
                        break
                    except Exception:
                        continue
        
        # 设置字体配置
        if selected_font:
            font_list = [selected_font] + fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
        else:
            font_list = fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
        
        # 设置matplotlib全局字体配置
        plt.rcParams['font.sans-serif'] = font_list
        plt.rcParams['axes.unicode_minus'] = False
        
        # 抑制字体警告
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.font_manager')
        
        # 设置日志级别以减少字体相关的警告信息
        import logging
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
        
        print(f"✅ 中文字体配置完成")
        print(f"   主要字体: {font_list[0]}")
        print(f"   备用字体: {font_list[1:4]}")
        
        return selected_font or font_list[0]
        
    except Exception as e:
        print(f"⚠️ 中文字体配置失败: {e}")
        # 使用默认字体
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        return 'DejaVu Sans'

def suppress_font_warnings():
    """
    抑制matplotlib字体相关的警告信息
    """
    import warnings
    import logging
    
    # 抑制matplotlib字体警告
    warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
    warnings.filterwarnings('ignore', message='.*font.*not found.*')
    warnings.filterwarnings('ignore', message='.*findfont.*')
    
    # 设置matplotlib日志级别
    logging.getLogger('matplotlib').setLevel(logging.ERROR)
    logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

# 在模块导入时自动配置字体
if __name__ != "__main__":
    suppress_font_warnings()
    setup_chinese_fonts()