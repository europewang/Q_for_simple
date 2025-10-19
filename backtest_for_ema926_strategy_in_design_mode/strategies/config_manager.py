#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器 - ConfigManager
统一管理所有交易策略的配置参数

该配置管理器提供：
1. 统一的配置文件格式
2. 策略特定的参数管理
3. 配置验证和默认值处理
4. 配置文件的读取和保存
5. 运行时配置的动态修改

作者：量化交易系统
版本：1.0
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import copy


@dataclass
class GlobalTradingConfig:
    """
    全局交易配置类 - 统一管理所有策略共用的交易参数
    
    注意：所有参数必须在config.json的global部分定义，此类仅用于类型定义
    """
    # 交易基础参数 - 必须在config.json中定义
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    
    # 统一的风险管理参数 - 不允许在单个策略中重写，必须在config.json中定义
    leverage: float  # 统一杠杆倍数
    fee: float  # 统一手续费率
    maintenance_margin_rate: float  # 统一维持保证金率
    position_percentage: float  # 统一仓位比例
    
    # 输出配置 - 必须在config.json中定义
    output_dir: str


@dataclass
class BaseConfig:
    """
    基础配置类 - 仅包含策略特定参数
    
    注意：所有参数必须在config.json的strategies部分定义，此类仅用于类型定义
    """
    # EMA参数 - 必须在config.json中定义
    ema_short: int
    ema_long: int


@dataclass
class LoggingConfig:
    """
    日志配置类
    
    注意：所有参数必须在config.json的logging部分定义，此类仅用于类型定义
    """
    enable_detailed_log: bool
    log_trades_to_file: bool
    log_file_prefix: str
    log_level: str
    save_txt_log: bool = True
    txt_log_format: str = "detailed"
    txt_log_include_summary: bool = True
    txt_log_real_time: bool = True


@dataclass
class ChartConfig:
    """
    图表配置类
    
    注意：所有参数必须在config.json的chart部分定义，此类仅用于类型定义
    """
    use_arrows_for_trades: bool
    avoid_text_overlap: bool
    chart_dpi: int
    save_chart: bool
    chart_width: int
    chart_height: int
    show_volume: bool


@dataclass
class SimpleEMAConfig(BaseConfig):
    """
    简单EMA策略配置
    
    注意：所有参数必须在config.json的strategies.simple_ema部分定义，此类仅用于类型定义
    """
    strategy_type: str
    strategy_name: str
    
    # 简单EMA策略特有参数
    # (简单策略没有特殊参数，使用基础配置即可)


@dataclass
class StagedEMAConfig(BaseConfig):
    """
    分批入场EMA策略配置
    
    注意：所有参数必须在config.json的strategies.staged_ema部分定义，此类仅用于类型定义
    """
    strategy_type: str
    strategy_name: str
    
    # 分批入场策略特有参数 - 必须在config.json中定义
    interval_30min: str
    interval_1min: str
    
    # 分批入场比例配置 - 必须在config.json中定义
    initial_entry_percentage: float
    staged_entry_percentages: List[float]


@dataclass
class ComplexEMAConfig(BaseConfig):
    """
    复杂EMA策略配置
    
    注意：所有参数必须在config.json的strategies.complex_ema部分定义，此类仅用于类型定义
    """
    strategy_type: str
    strategy_name: str
    
    # 复杂策略特有参数 - 必须在config.json中定义
    initial_entry_percentage: float
    staged_entry_percentages: List[float]
    
    # 风险控制参数 - 必须在config.json中定义
    max_position_ratio: float
    stop_loss_ratio: float


@dataclass
class AdvancedStagedEMAConfig(BaseConfig):
    """
    高级分批入场EMA策略配置
    
    注意：所有参数必须在config.json的strategies.advanced_staged_ema部分定义，此类仅用于类型定义
    """
    strategy_type: str
    strategy_name: str
    
    # 高级策略特有参数 - 必须在config.json中定义
    interval_1hour: str
    interval_1min: str
    
    # 分批入场配置 - 必须在config.json中定义
    initial_entry_percentage: float
    staged_entry_percentages: List[float]
    max_staged_entries: int
    
    # 高级风险控制参数 - 必须在config.json中定义
    allocated_capital_ratio: float
    risk_management_enabled: bool


class ConfigManager:
    """
    配置管理器
    
    负责管理所有策略的配置参数，提供配置的读取、保存、验证和修改功能。
    统一管理全局交易配置，确保杠杆、保证金比例等关键参数的一致性。
    """
    
    def __init__(self, config_dir: str = 'config'):
        """
        初始化配置管理器
        
        Args:
            config_dir (str): 配置文件目录
        """
        self.config_dir = config_dir
        # 使用统一配置文件
        self.config_file = os.path.join(os.path.dirname(config_dir), 'config.json')
        
        # 策略配置类映射
        self.strategy_config_classes = {
            'simple_ema': SimpleEMAConfig,
            'staged_ema': StagedEMAConfig,
            'complex_ema': ComplexEMAConfig,
            'advanced_staged_ema': AdvancedStagedEMAConfig
        }
        
        # 确保配置目录存在
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # 加载或创建默认配置
        self.configs = self._load_or_create_default_configs()
    
    def _load_or_create_default_configs(self) -> Dict[str, Dict]:
        """加载或创建默认配置"""
        if os.path.exists(self.config_file):
            return self._load_configs_from_file()
        else:
            return self._create_default_configs()
    
    def _load_configs_from_file(self) -> Dict[str, Dict]:
        """从统一配置文件加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                unified_config = json.load(f)
            
            print(f"配置文件加载成功: {self.config_file}")
            
            # 转换统一配置文件格式为原有格式
            configs_data = {}
            
            # 添加全局配置
            if 'global' in unified_config:
                configs_data['global_trading_config'] = unified_config['global']
            
            # 添加策略配置
            if 'strategies' in unified_config:
                for strategy_name, strategy_config in unified_config['strategies'].items():
                    # 合并全局配置和策略特定配置
                    merged_config = copy.deepcopy(unified_config.get('global', {}))
                    merged_config.update(strategy_config)
                    
                    # 处理override配置
                    if 'override' in strategy_config:
                        merged_config.update(strategy_config['override'])
                        # 移除override字段
                        if 'override' in merged_config:
                            del merged_config['override']
                    
                    configs_data[strategy_name] = merged_config
            
            # 添加其他配置
            if 'strategies_to_run' in unified_config:
                configs_data['strategies_to_run'] = unified_config['strategies_to_run']
            
            if 'logging' in unified_config:
                configs_data['logging'] = unified_config['logging']
            
            if 'chart' in unified_config:
                configs_data['chart'] = unified_config['chart']
            
            if 'backtest' in unified_config:
                configs_data['backtest'] = unified_config['backtest']
            
            return configs_data
            
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            print("使用默认配置...")
            return self._create_default_configs()
    
    def _create_default_configs(self) -> Dict[str, Dict]:
        """
        创建默认配置
        
        注意：由于所有配置都必须在config.json中定义，此方法现在只提供错误提示
        """
        error_message = f"""
配置文件不存在: {self.config_file}

所有配置参数必须在config.json文件中定义。请参考以下文件：
1. config_template_with_comments.jsonc - 详细的配置模板
2. docs/配置文件说明.md - 配置文件使用说明

请创建config.json文件并定义所有必要的配置参数。
        """
        
        print(error_message)
        raise FileNotFoundError(f"配置文件不存在: {self.config_file}。请创建config.json文件并定义所有必要的配置参数。")
    
    def _save_configs_to_file(self, configs: Dict[str, Dict]):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)
            print(f"配置文件保存成功: {self.config_file}")
        except Exception as e:
            print(f"配置文件保存失败: {e}")
    
    def get_strategy_config(self, strategy_type: str) -> Dict[str, Any]:
        """
        获取指定策略的配置
        
        Args:
            strategy_type (str): 策略类型
            
        Returns:
            Dict[str, Any]: 策略配置字典
        """
        if strategy_type not in self.configs:
            raise ValueError(f"未知的策略类型: {strategy_type}")
        
        # 合并全局交易配置和策略特定配置
        config = copy.deepcopy(self.configs[strategy_type])
        
        # 添加全局交易配置
        global_config = self.configs.get('global_trading_config', {})
        config.update(global_config)
        
        # 添加其他配置
        config['logging_config'] = self.configs.get('logging', {})
        config['chart_config'] = self.configs.get('chart', {})
        
        return config
    
    def update_strategy_config(self, strategy_type: str, updates: Dict[str, Any]):
        """
        更新指定策略的配置
        
        Args:
            strategy_type (str): 策略类型
            updates (Dict[str, Any]): 要更新的配置项
        """
        if strategy_type not in self.configs:
            raise ValueError(f"未知的策略类型: {strategy_type}")
        
        # 深度更新配置
        self._deep_update(self.configs[strategy_type], updates)
        
        # 保存到文件
        self._save_configs_to_file(self.configs)
        
        print(f"策略 {strategy_type} 配置更新成功")
    
    def _deep_update(self, target: Dict, source: Dict):
        """深度更新字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    def get_all_strategy_types(self) -> List[str]:
        """获取所有可用的策略类型"""
        return list(self.strategy_config_classes.keys())
    
    def validate_config(self, strategy_type: str, config: Dict[str, Any]) -> bool:
        """
        验证配置的有效性
        
        Args:
            strategy_type (str): 策略类型
            config (Dict[str, Any]): 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        try:
            if strategy_type not in self.strategy_config_classes:
                return False
            
            config_class = self.strategy_config_classes[strategy_type]
            
            # 尝试创建配置实例来验证
            config_class(**config)
            return True
            
        except Exception as e:
            print(f"配置验证失败: {e}")
            return False
    
    def create_strategy_config_instance(self, strategy_type: str, **kwargs) -> Any:
        """
        创建策略配置实例
        
        Args:
            strategy_type (str): 策略类型
            **kwargs: 额外的配置参数
            
        Returns:
            配置实例
        """
        if strategy_type not in self.strategy_config_classes:
            raise ValueError(f"未知的策略类型: {strategy_type}")
        
        config_class = self.strategy_config_classes[strategy_type]
        
        # 获取策略特定的配置，排除全局配置和其他配置
        strategy_config = {}
        full_config = self.configs[strategy_type]
        
        # 获取配置类的字段名
        import inspect
        config_fields = set(inspect.signature(config_class).parameters.keys())
        
        # 只包含配置类需要的字段
        for key, value in full_config.items():
            if key in config_fields:
                strategy_config[key] = value
        
        # 添加额外的参数
        strategy_config.update(kwargs)
        
        return config_class(**strategy_config)
    
    def export_config(self, strategy_type: str, filepath: str):
        """
        导出指定策略的配置到文件
        
        Args:
            strategy_type (str): 策略类型
            filepath (str): 导出文件路径
        """
        config = self.get_strategy_config(strategy_type)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"策略 {strategy_type} 配置已导出到: {filepath}")
    
    def import_config(self, strategy_type: str, filepath: str):
        """
        从文件导入策略配置
        
        Args:
            strategy_type (str): 策略类型
            filepath (str): 配置文件路径
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            imported_config = json.load(f)
        
        # 验证配置
        if self.validate_config(strategy_type, imported_config):
            self.configs[strategy_type] = imported_config
            self._save_configs_to_file(self.configs)
            print(f"策略 {strategy_type} 配置导入成功")
        else:
            raise ValueError("导入的配置文件格式不正确")
    
    def reset_to_default(self, strategy_type: str):
        """
        重置指定策略的配置为默认值
        
        注意：由于所有配置都必须在config.json中定义，此方法现在只提供提示信息
        
        Args:
            strategy_type (str): 策略类型
        """
        if strategy_type not in self.strategy_config_classes:
            raise ValueError(f"未知的策略类型: {strategy_type}")
        
        message = f"""
无法自动重置策略 {strategy_type} 的配置。

所有配置参数必须在config.json文件中手动定义。请参考：
1. config_template_with_comments.jsonc - 详细的配置模板
2. docs/配置文件说明.md - 配置文件使用说明

请手动编辑config.json文件来修改策略配置。
        """
        
        print(message)
        raise NotImplementedError("配置重置功能已禁用。请手动编辑config.json文件。")
    
    def print_config_chinese(self, strategy_type: str):
        """
        以中文形式打印指定策略的配置信息（简化版）
        
        Args:
            strategy_type (str): 策略类型
        """
        # 简化输出，不显示详细配置信息
        pass
    
    def print_config(self, strategy_type: str):
        """
        打印指定策略的配置（保持向后兼容）
        
        Args:
            strategy_type (str): 策略类型
        """
        self.print_config_chinese(strategy_type)


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager


if __name__ == '__main__':
    """
    配置管理器测试
    """
    print("配置管理器测试")
    print("=" * 50)
    
    # 获取配置管理器
    cm = get_config_manager()
    
    # 打印所有策略类型
    print("可用的策略类型:")
    for strategy_type in cm.get_all_strategy_types():
        print(f"  - {strategy_type}")
    
    # 打印各策略配置
    for strategy_type in cm.get_all_strategy_types():
        cm.print_config(strategy_type)
    
    print("配置管理器测试完成")