#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的策略运行脚本
用法：python run_strategy.py [策略名称]

支持的策略：
- simple_ema: 简单EMA交叉策略
- staged_ema: 分批入场EMA交叉策略  
- complex_ema: 复杂EMA交叉策略
- advanced_staged_ema: 高级分批入场EMA交叉策略

示例：
python run_strategy.py staged_ema
python run_strategy.py simple_ema
"""

import sys
import os
import argparse
from pathlib import Path

# 添加strategies目录到路径
strategies_dir = Path(__file__).parent / "strategies"
sys.path.insert(0, str(strategies_dir))

from strategy_runner import StrategyRunner

# 策略映射
STRATEGY_MAP = {
    'simple_ema': {
        'name': '简单EMA交叉策略',
        'description': '基于EMA交叉的简单策略，交叉进，反向交叉出'
    },
    'staged_ema': {
        'name': '分批入场EMA交叉策略',
        'description': '基于EMA交叉的分批入场策略，支持多次加仓'
    },

}

def print_available_strategies():
    """打印可用的策略列表"""
    print("\n可用的策略：")
    print("=" * 50)
    for key, info in STRATEGY_MAP.items():
        print(f"  {key:20} - {info['name']}")
        print(f"  {' ' * 20}   {info['description']}")
        print()

def run_strategy(strategy_name: str):
    """运行指定的策略"""
    if strategy_name not in STRATEGY_MAP:
        print(f"❌ 错误：未知的策略 '{strategy_name}'")
        print_available_strategies()
        return False
    
    try:
        print(f"\n🚀 开始运行策略: {STRATEGY_MAP[strategy_name]['name']}")
        print("=" * 60)
        
        # 创建策略运行器
        runner = StrategyRunner()
        
        # 运行策略
        result = runner.run_strategy(strategy_name)
        
        if result:
            print(f"\n✅ 策略 '{strategy_name}' 运行完成！")
            print(f"📊 详细结果请查看输出文件")
        else:
            print(f"\n❌ 策略 '{strategy_name}' 运行失败！")
            
        return result
        
    except Exception as e:
        print(f"\n❌ 运行策略时发生错误: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='简化的策略运行脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_strategy.py staged_ema     # 运行分批入场EMA策略
  python run_strategy.py simple_ema     # 运行简单EMA策略
  python run_strategy.py --list         # 显示所有可用策略
        """
    )
    
    parser.add_argument(
        'strategy', 
        nargs='?',
        help='要运行的策略名称'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='显示所有可用的策略'
    )
    
    args = parser.parse_args()
    
    # 如果指定了--list参数或没有提供策略名称
    if args.list or not args.strategy:
        print_available_strategies()
        if not args.strategy:
            print("请指定要运行的策略名称，例如：")
            print("python run_strategy.py staged_ema")
        return
    
    # 运行指定的策略
    success = run_strategy(args.strategy)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()