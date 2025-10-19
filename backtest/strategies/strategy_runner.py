#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略运行器 - StrategyRunner
统一运行和管理各种交易策略

该运行器提供：
1. 策略的统一运行接口
2. 批量策略执行
3. 策略结果的收集和管理
4. 策略运行状态监控
5. 异常处理和错误恢复

作者：量化交易系统
版本：1.0
"""

import os
import sys
import time
import traceback
from typing import Dict, List, Optional, Any, Type
from datetime import datetime
import json
import pandas as pd

# 添加当前目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import get_config_manager, ConfigManager
from base_strategy import BaseStrategy


class StrategyRunner:
    """
    策略运行器
    
    负责策略的创建、运行、监控和结果管理。
    支持单个策略运行和批量策略执行。
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        初始化策略运行器
        
        Args:
            config_manager (ConfigManager, optional): 配置管理器实例
        """
        self.config_manager = config_manager or get_config_manager()
        self.strategy_registry = {}  # 策略类注册表
        self.running_strategies = {}  # 正在运行的策略实例
        self.strategy_results = {}   # 策略运行结果
        self.execution_log = []      # 执行日志
        
        # 运行状态
        self.is_running = False
        self.start_time = None
        self.end_time = None
        
        # 注册策略类
        self._register_strategy_classes()
    
    def _register_strategy_classes(self):
        """注册策略类"""
        try:
            # 导入重构后的策略类
            from simple_ema_strategy import SimpleEMAStrategy
            from staged_ema_strategy import StagedEMAStrategy
            
            # 注册策略类
            self.register_strategy('simple_ema', SimpleEMAStrategy)
            self.register_strategy('staged_ema', StagedEMAStrategy)
            
            print("已注册策略类:")
            print("  - simple_ema: SimpleEMAStrategy")
            print("  - staged_ema: StagedEMAStrategy")
            
        except ImportError as e:
            print(f"策略类导入失败: {e}")
            print("请确保所有策略类都已正确实现")
    
    def register_strategy(self, strategy_type: str, strategy_class: Type[BaseStrategy]):
        """
        注册策略类
        
        Args:
            strategy_type (str): 策略类型标识
            strategy_class (Type[BaseStrategy]): 策略类
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"策略类 {strategy_class.__name__} 必须继承自 BaseStrategy")
        
        self.strategy_registry[strategy_type] = strategy_class
        print(f"策略类 {strategy_type} 注册成功")
    
    def create_strategy(self, strategy_type: str, config_overrides: Optional[Dict] = None) -> BaseStrategy:
        """
        创建策略实例
        
        Args:
            strategy_type (str): 策略类型
            config_overrides (Dict, optional): 配置覆盖参数
            
        Returns:
            BaseStrategy: 策略实例
        """
        if strategy_type not in self.strategy_registry:
            raise ValueError(f"未注册的策略类型: {strategy_type}")
        
        # 获取策略配置
        config = self.config_manager.get_strategy_config(strategy_type)
        
        # 应用配置覆盖
        if config_overrides:
            config.update(config_overrides)
        
        # 创建策略实例
        strategy_class = self.strategy_registry[strategy_type]
        strategy = strategy_class(config=config)
        
        return strategy
    
    def run_strategy(self, strategy_type: str, config_overrides: Optional[Dict] = None) -> Dict[str, Any]:
        """
        运行单个策略
        
        Args:
            strategy_type (str): 策略类型
            config_overrides (Dict, optional): 配置覆盖参数
            
        Returns:
            Dict[str, Any]: 策略运行结果
        """
        start_time = time.time()
        
        try:
            print(f"\n{'=' * 60}")
            print(f"开始运行策略: {strategy_type}")
            print(f"{'=' * 60}")
            
            # 打印策略配置信息（中文）
            self.config_manager.print_config_chinese(strategy_type)
            
            # 创建策略实例
            strategy = self.create_strategy(strategy_type, config_overrides)
            
            # 记录运行中的策略
            self.running_strategies[strategy_type] = strategy
            
            # 执行策略回测
            results = strategy.run_backtest()
            
            # 记录结果
            execution_time = time.time() - start_time
            results['execution_time'] = execution_time
            results['strategy_type'] = strategy_type
            results['execution_timestamp'] = datetime.now().isoformat()
            
            self.strategy_results[strategy_type] = results
            
            # 记录执行日志
            log_entry = {
                'strategy_type': strategy_type,
                'status': 'success',
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'total_trades': results.get('total_trades', 0),
                'total_return': results.get('total_return', 0),
                'final_capital': results.get('final_capital', 0)
            }
            self.execution_log.append(log_entry)
            
            print(f"\\n策略 {strategy_type} 运行完成，耗时: {execution_time:.2f}秒")
            
            return results
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"策略 {strategy_type} 运行失败: {str(e)}"
            print(f"\\n❌ {error_msg}")
            print(f"错误详情: {traceback.format_exc()}")
            
            # 记录错误日志
            log_entry = {
                'strategy_type': strategy_type,
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat()
            }
            self.execution_log.append(log_entry)
            
            # 返回错误结果
            return {
                'strategy_type': strategy_type,
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }
        
        finally:
            # 清理运行中的策略记录
            if strategy_type in self.running_strategies:
                del self.running_strategies[strategy_type]
    
    def run_multiple_strategies(self, strategy_types: List[str], 
                              config_overrides: Optional[Dict[str, Dict]] = None) -> Dict[str, Dict]:
        """
        批量运行多个策略
        
        Args:
            strategy_types (List[str]): 策略类型列表
            config_overrides (Dict[str, Dict], optional): 各策略的配置覆盖参数
            
        Returns:
            Dict[str, Dict]: 各策略的运行结果
        """
        self.is_running = True
        self.start_time = time.time()
        
        print(f"\\n{'=' * 80}")
        print(f"开始批量运行策略")
        print(f"策略数量: {len(strategy_types)}")
        print(f"策略列表: {', '.join(strategy_types)}")
        print(f"{'=' * 80}")
        
        results = {}
        
        try:
            for i, strategy_type in enumerate(strategy_types, 1):
                print(f"\\n[{i}/{len(strategy_types)}] 运行策略: {strategy_type}")
                
                # 获取该策略的配置覆盖
                strategy_config_overrides = None
                if config_overrides and strategy_type in config_overrides:
                    strategy_config_overrides = config_overrides[strategy_type]
                
                # 运行策略
                result = self.run_strategy(strategy_type, strategy_config_overrides)
                results[strategy_type] = result
                
                # 打印进度
                print(f"策略 {strategy_type} 完成 ({i}/{len(strategy_types)})")
        
        finally:
            self.is_running = False
            self.end_time = time.time()
            total_time = self.end_time - self.start_time
            
            print(f"\\n{'=' * 80}")
            print(f"批量策略运行完成")
            print(f"总耗时: {total_time:.2f}秒")
            print(f"{'=' * 80}")
        
        return results
    
    def run_all_strategies(self, config_overrides: Optional[Dict[str, Dict]] = None) -> Dict[str, Dict]:
        """
        运行所有已注册的策略
        
        Args:
            config_overrides (Dict[str, Dict], optional): 各策略的配置覆盖参数
            
        Returns:
            Dict[str, Dict]: 所有策略的运行结果
        """
        strategy_types = list(self.strategy_registry.keys())
        return self.run_multiple_strategies(strategy_types, config_overrides)
    
    def get_strategy_results(self, strategy_type: Optional[str] = None) -> Dict:
        """
        获取策略运行结果
        
        Args:
            strategy_type (str, optional): 策略类型，如果为None则返回所有结果
            
        Returns:
            Dict: 策略运行结果
        """
        if strategy_type:
            return self.strategy_results.get(strategy_type, {})
        else:
            return self.strategy_results.copy()
    
    def get_execution_log(self) -> List[Dict]:
        """获取执行日志"""
        return self.execution_log.copy()
    
    def clear_results(self):
        """清空运行结果和日志"""
        self.strategy_results.clear()
        self.execution_log.clear()
        print("运行结果和日志已清空")
    
    def save_results_to_file(self, filepath: Optional[str] = None):
        """
        保存运行结果到文件
        
        Args:
            filepath (str, optional): 保存文件路径
        """
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"strategy_results_{timestamp}.json"
        
        # 准备保存数据
        save_data = {
            'execution_summary': {
                'total_strategies': len(self.strategy_results),
                'execution_time': getattr(self, 'end_time', time.time()) - getattr(self, 'start_time', time.time()),
                'timestamp': datetime.now().isoformat()
            },
            'strategy_results': self.strategy_results,
            'execution_log': self.execution_log
        }
        
        # 保存到文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
            print(f"运行结果已保存到: {filepath}")
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def print_summary(self):
        """打印运行摘要"""
        if not self.strategy_results:
            print("暂无策略运行结果")
            return
        
        print(f"\\n{'=' * 80}")
        print(f"策略运行摘要")
        print(f"{'=' * 80}")
        
        # 统计信息
        total_strategies = len(self.strategy_results)
        successful_strategies = len([r for r in self.strategy_results.values() if r.get('status') != 'error'])
        failed_strategies = total_strategies - successful_strategies
        
        print(f"总策略数: {total_strategies}")
        print(f"成功运行: {successful_strategies}")
        print(f"运行失败: {failed_strategies}")
        
        if successful_strategies > 0:
            print(f"\\n{'策略名称':<20} {'总收益率':<12} {'交易次数':<10} {'胜率':<10} {'最终资金':<12}")
            print("-" * 80)
            
            for strategy_type, result in self.strategy_results.items():
                if result.get('status') == 'error':
                    continue
                
                strategy_name = result.get('strategy_name', strategy_type)[:18]
                total_return = result.get('total_return', 0)
                total_trades = result.get('total_trades', 0)
                win_rate = result.get('win_rate', 0)
                final_capital = result.get('final_capital', 0)
                
                print(f"{strategy_name:<20} {total_return:>10.2%} {total_trades:>8} {win_rate:>8.2%} ${final_capital:>10.2f}")
        
        if failed_strategies > 0:
            print(f"\\n失败的策略:")
            for strategy_type, result in self.strategy_results.items():
                if result.get('status') == 'error':
                    print(f"  - {strategy_type}: {result.get('error_message', '未知错误')}")
        
        print(f"\\n{'=' * 80}")
    
    def get_running_status(self) -> Dict[str, Any]:
        """获取运行状态"""
        return {
            'is_running': self.is_running,
            'running_strategies': list(self.running_strategies.keys()),
            'completed_strategies': list(self.strategy_results.keys()),
            'registered_strategies': list(self.strategy_registry.keys()),
            'start_time': self.start_time,
            'end_time': self.end_time
        }


class StrategyFactory:
    """
    策略工厂类
    
    提供策略的创建和管理功能
    """
    
    @staticmethod
    def create_runner(config_manager: Optional[ConfigManager] = None) -> StrategyRunner:
        """
        创建策略运行器
        
        Args:
            config_manager (ConfigManager, optional): 配置管理器
            
        Returns:
            StrategyRunner: 策略运行器实例
        """
        return StrategyRunner(config_manager)
    
    @staticmethod
    def get_available_strategies() -> List[str]:
        """获取可用的策略类型列表"""
        cm = get_config_manager()
        return cm.get_all_strategy_types()


# 全局策略运行器实例
_global_runner = None


def get_strategy_runner() -> StrategyRunner:
    """获取全局策略运行器实例"""
    global _global_runner
    if _global_runner is None:
        _global_runner = StrategyFactory.create_runner()
    return _global_runner


if __name__ == '__main__':
    """
    策略运行器测试
    """
    print("策略运行器测试")
    print("=" * 50)
    
    # 创建运行器
    runner = get_strategy_runner()
    
    # 打印可用策略
    print("可用的策略类型:")
    for strategy_type in StrategyFactory.get_available_strategies():
        print(f"  - {strategy_type}")
    
    # 打印运行状态
    status = runner.get_running_status()
    print(f"\\n运行状态: {status}")
    
    print("\\n策略运行器测试完成")
    print("注意: 需要先重构具体策略类并注册到运行器中才能运行策略")