#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略运行器测试脚本
测试StrategyRunner的各项功能

作者：量化交易系统
版本：1.0
"""

import os
import sys
import traceback
from datetime import datetime

# 添加当前目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy_runner import StrategyRunner, StrategyFactory, get_strategy_runner


def test_strategy_registration():
    """测试策略注册功能"""
    print("\n=== 测试策略注册功能 ===")
    try:
        runner = get_strategy_runner()
        available_strategies = StrategyFactory.get_available_strategies()
        
        print(f"已注册的策略数量: {len(available_strategies)}")
        print("已注册的策略类型:")
        for strategy_type in available_strategies:
            print(f"  - {strategy_type}")
        
        # 验证预期的策略都已注册
        expected_strategies = ['simple_ema', 'staged_ema', 'complex_ema', 'advanced_staged_ema']
        missing_strategies = [s for s in expected_strategies if s not in available_strategies]
        
        if missing_strategies:
            print(f"❌ 缺少策略: {missing_strategies}")
            return False
        else:
            print("✅ 所有预期策略都已正确注册")
            return True
            
    except Exception as e:
        print(f"❌ 策略注册测试失败: {e}")
        traceback.print_exc()
        return False


def test_strategy_creation():
    """测试策略创建功能"""
    print("\n=== 测试策略创建功能 ===")
    try:
        runner = get_strategy_runner()
        
        # 测试创建每种策略
        strategies_to_test = ['simple_ema', 'staged_ema', 'complex_ema']
        
        for strategy_type in strategies_to_test:
            try:
                print(f"正在测试创建策略: {strategy_type}")
                strategy = runner.create_strategy(strategy_type)
                
                if strategy is not None:
                    print(f"  ✅ {strategy_type} 策略创建成功")
                    print(f"     策略类型: {type(strategy).__name__}")
                else:
                    print(f"  ❌ {strategy_type} 策略创建失败: 返回None")
                    return False
                    
            except Exception as e:
                print(f"  ❌ {strategy_type} 策略创建失败: {e}")
                return False
        
        print("✅ 所有策略创建测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 策略创建测试失败: {e}")
        traceback.print_exc()
        return False


def test_runner_status():
    """测试运行器状态功能"""
    print("\n=== 测试运行器状态功能 ===")
    try:
        runner = get_strategy_runner()
        
        # 获取运行状态
        status = runner.get_running_status()
        
        print("运行器状态信息:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # 验证状态结构
        expected_keys = ['is_running', 'running_strategies', 'completed_strategies', 
                        'registered_strategies', 'start_time', 'end_time']
        
        missing_keys = [key for key in expected_keys if key not in status]
        if missing_keys:
            print(f"❌ 状态信息缺少字段: {missing_keys}")
            return False
        
        print("✅ 运行器状态测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 运行器状态测试失败: {e}")
        traceback.print_exc()
        return False


def test_results_management():
    """测试结果管理功能"""
    print("\n=== 测试结果管理功能 ===")
    try:
        runner = get_strategy_runner()
        
        # 测试获取结果
        results = runner.get_strategy_results()
        print(f"当前结果数量: {len(results)}")
        
        # 测试获取执行日志
        log = runner.get_execution_log()
        print(f"执行日志条目数: {len(log)}")
        
        # 测试清除结果
        runner.clear_results()
        print("✅ 结果清除成功")
        
        # 验证清除后的状态
        results_after_clear = runner.get_strategy_results()
        log_after_clear = runner.get_execution_log()
        
        if len(results_after_clear) == 0 and len(log_after_clear) == 0:
            print("✅ 结果管理测试通过")
            return True
        else:
            print("❌ 结果清除后仍有残留数据")
            return False
        
    except Exception as e:
        print(f"❌ 结果管理测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("策略运行器功能测试")
    print("=" * 50)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行所有测试
    tests = [
        ("策略注册", test_strategy_registration),
        ("策略创建", test_strategy_creation),
        ("运行器状态", test_runner_status),
        ("结果管理", test_results_management),
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n开始测试: {test_name}")
        try:
            if test_func():
                passed_tests += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            traceback.print_exc()
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("测试总结")
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！策略运行器功能正常")
    else:
        print("⚠️  部分测试失败，请检查相关功能")


if __name__ == '__main__':
    main()