"""
配置加载器
负责加载和验证实时交易配置
"""
import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from shared.utils.logger import get_logger


@dataclass
class TradingConfig:
    """交易配置"""
    symbol: str
    simulation_mode: bool
    initial_balance: float
    max_position_percentage: float
    leverage: float


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    fast_ema_period: int
    slow_ema_period: int
    signal_strength_threshold: float
    min_signal_strength: float
    max_signal_strength: float


@dataclass
class RiskConfig:
    """风险管理配置"""
    max_position_percentage: float
    max_daily_loss_percentage: float
    max_drawdown_percentage: float
    stop_loss_percentage: float
    take_profit_percentage: float
    min_position_size: float
    max_leverage: float
    max_trades_per_day: int


@dataclass
class PositionConfig:
    """仓位管理配置"""
    max_positions: int
    position_timeout: int


@dataclass
class ExecutionConfig:
    """执行配置"""
    max_retry_count: int
    retry_delay: float
    order_timeout: float
    slippage_tolerance: float
    simulation_mode: bool
    simulation_latency: float
    simulation_slippage: float


@dataclass
class ExchangeConfig:
    """交易所配置"""
    name: str
    api_key: str
    api_secret: str
    testnet: bool
    initial_balance: float


@dataclass
class DataFeedConfig:
    """数据源配置"""
    source: str
    update_interval: float
    websocket_url: str
    rest_api_url: str
    mock_volatility: float
    mock_trend: float


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str
    log_to_file: bool
    log_directory: str
    max_log_files: int
    max_log_size_mb: int


@dataclass
class MonitoringConfig:
    """监控配置"""
    enable_web_interface: bool
    web_port: int
    update_interval: float
    save_state_interval: float


@dataclass
class LiveTradingConfig:
    """完整的实时交易配置"""
    trading: TradingConfig
    strategy: StrategyConfig
    risk_management: RiskConfig
    position_management: PositionConfig
    execution: ExecutionConfig
    exchange: ExchangeConfig
    data_feed: DataFeedConfig
    logging: LoggingConfig
    monitoring: MonitoringConfig


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self):
        self.logger = get_logger("ConfigLoader")
    
    def load_config(self, config_path: str) -> LiveTradingConfig:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            实时交易配置对象
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 验证配置
            self._validate_config(config_data)
            
            # 创建配置对象
            config = self._create_config_objects(config_data)
            
            self.logger.info(f"配置加载成功: {config_path}")
            return config
            
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON格式错误: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            raise
    
    def _validate_config(self, config_data: Dict[str, Any]):
        """验证配置数据"""
        required_sections = [
            'trading', 'strategy', 'risk_management', 'position_management',
            'execution', 'exchange', 'data_feed', 'logging', 'monitoring'
        ]
        
        for section in required_sections:
            if section not in config_data:
                raise ValueError(f"缺少必需的配置节: {section}")
        
        # 验证交易配置
        trading_config = config_data['trading']
        if trading_config.get('initial_balance', 0) <= 0:
            raise ValueError("初始余额必须大于0")
        
        if not 0 < trading_config.get('max_position_percentage', 0) <= 1:
            raise ValueError("最大仓位比例必须在0-1之间")
        
        # 验证策略配置
        strategy_config = config_data['strategy']
        if strategy_config.get('fast_ema_period', 0) <= 0:
            raise ValueError("快速EMA周期必须大于0")
        
        if strategy_config.get('slow_ema_period', 0) <= strategy_config.get('fast_ema_period', 0):
            raise ValueError("慢速EMA周期必须大于快速EMA周期")
        
        # 验证风险管理配置
        risk_config = config_data['risk_management']
        if not 0 < risk_config.get('max_position_percentage', 0) <= 1:
            raise ValueError("风险管理最大仓位比例必须在0-1之间")
        
        if not 0 < risk_config.get('max_daily_loss_percentage', 0) <= 1:
            raise ValueError("最大日损失比例必须在0-1之间")
        
        if not 0 < risk_config.get('stop_loss_percentage', 0) <= 1:
            raise ValueError("止损比例必须在0-1之间")
        
        # 验证交易所配置
        exchange_config = config_data['exchange']
        supported_exchanges = ['binance', 'mock']
        if exchange_config.get('name', '').lower() not in supported_exchanges:
            raise ValueError(f"不支持的交易所: {exchange_config.get('name')}")
    
    def _create_config_objects(self, config_data: Dict[str, Any]) -> LiveTradingConfig:
        """创建配置对象"""
        return LiveTradingConfig(
            trading=TradingConfig(**config_data['trading']),
            strategy=StrategyConfig(**config_data['strategy']),
            risk_management=RiskConfig(**config_data['risk_management']),
            position_management=PositionConfig(**config_data['position_management']),
            execution=ExecutionConfig(**config_data['execution']),
            exchange=ExchangeConfig(**config_data['exchange']),
            data_feed=DataFeedConfig(**config_data['data_feed']),
            logging=LoggingConfig(**config_data['logging']),
            monitoring=MonitoringConfig(**config_data['monitoring'])
        )
    
    def save_config(self, config: LiveTradingConfig, config_path: str):
        """
        保存配置到文件
        
        Args:
            config: 配置对象
            config_path: 保存路径
        """
        try:
            config_dict = {
                'trading': config.trading.__dict__,
                'strategy': config.strategy.__dict__,
                'risk_management': config.risk_management.__dict__,
                'position_management': config.position_management.__dict__,
                'execution': config.execution.__dict__,
                'exchange': config.exchange.__dict__,
                'data_feed': config.data_feed.__dict__,
                'logging': config.logging.__dict__,
                'monitoring': config.monitoring.__dict__
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置保存成功: {config_path}")
            
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {str(e)}")
            raise
    
    def create_default_config(self, config_path: str):
        """
        创建默认配置文件
        
        Args:
            config_path: 配置文件路径
        """
        default_config = {
            "trading": {
                "symbol": "BTCUSDT",
                "simulation_mode": True,
                "initial_balance": 10000.0,
                "max_position_percentage": 0.95,
                "leverage": 1.0
            },
            "strategy": {
                "name": "SimpleEMAStrategy",
                "fast_ema_period": 12,
                "slow_ema_period": 26,
                "signal_strength_threshold": 0.5,
                "min_signal_strength": 0.3,
                "max_signal_strength": 1.0
            },
            "risk_management": {
                "max_position_percentage": 0.95,
                "max_daily_loss_percentage": 0.05,
                "max_drawdown_percentage": 0.10,
                "stop_loss_percentage": 0.02,
                "take_profit_percentage": 0.06,
                "min_position_size": 10.0,
                "max_leverage": 20.0,
                "max_trades_per_day": 50
            },
            "position_management": {
                "max_positions": 5,
                "position_timeout": 3600
            },
            "execution": {
                "max_retry_count": 3,
                "retry_delay": 1.0,
                "order_timeout": 30.0,
                "slippage_tolerance": 0.001,
                "simulation_mode": True,
                "simulation_latency": 0.1,
                "simulation_slippage": 0.0005
            },
            "exchange": {
                "name": "mock",
                "api_key": "",
                "api_secret": "",
                "testnet": True,
                "initial_balance": 10000.0
            },
            "data_feed": {
                "source": "mock",
                "update_interval": 1.0,
                "websocket_url": "",
                "rest_api_url": "",
                "mock_volatility": 0.02,
                "mock_trend": 0.0
            },
            "logging": {
                "level": "INFO",
                "log_to_file": True,
                "log_directory": "live_trading/logs",
                "max_log_files": 10,
                "max_log_size_mb": 50
            },
            "monitoring": {
                "enable_web_interface": True,
                "web_port": 8080,
                "update_interval": 5.0,
                "save_state_interval": 60.0
            }
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"默认配置文件创建成功: {config_path}")
            
        except Exception as e:
            self.logger.error(f"创建默认配置文件失败: {str(e)}")
            raise


def load_live_trading_config(config_path: str = None) -> LiveTradingConfig:
    """
    便捷函数：加载实时交易配置
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        实时交易配置对象
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'live_trading_config.json')
    
    loader = ConfigLoader()
    return loader.load_config(config_path)