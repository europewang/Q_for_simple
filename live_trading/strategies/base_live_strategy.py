"""
实时交易策略基类
定义实时交易策略的通用接口和功能
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List

from shared.models.trade_models import MarketData, Signal, Order, Position
from shared.utils.logger import get_logger


class BaseLiveStrategy(ABC):
    """实时交易策略基类"""
    
    def __init__(self, strategy_name: str, symbol: str, config: Dict[str, Any]):
        """
        初始化策略
        
        Args:
            strategy_name: 策略名称
            symbol: 交易对符号
            config: 策略配置
        """
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.config = config
        self.logger = get_logger(f"Strategy_{strategy_name}")
        
        # 策略状态
        self.is_running = False
        self.current_position: Optional[Position] = None
        self.market_data_history: List[MarketData] = []
        self.signals_history: List[Signal] = []
        
        # 策略参数
        self.max_history_length = config.get('max_history_length', 1000)
        
        self.logger.info(f"策略 {strategy_name} 初始化完成")
    
    @abstractmethod
    def on_market_data(self, market_data: MarketData) -> Optional[Signal]:
        """
        处理市场数据并生成交易信号
        
        Args:
            market_data: 市场数据
            
        Returns:
            交易信号（如果有）
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Signal, account_balance: float) -> float:
        """
        计算仓位大小
        
        Args:
            signal: 交易信号
            account_balance: 账户余额
            
        Returns:
            仓位大小
        """
        pass
    
    def update_market_data(self, market_data: MarketData):
        """
        更新市场数据
        
        Args:
            market_data: 新的市场数据
        """
        # 添加到历史数据
        self.market_data_history.append(market_data)
        
        # 限制历史数据长度
        if len(self.market_data_history) > self.max_history_length:
            self.market_data_history = self.market_data_history[-self.max_history_length:]
        
        self.logger.debug(f"更新市场数据: {market_data.symbol} - {market_data.close}")
    
    def generate_signal(self, market_data: MarketData) -> Optional[Signal]:
        """
        生成交易信号
        
        Args:
            market_data: 市场数据
            
        Returns:
            交易信号（如果有）
        """
        # 更新市场数据
        self.update_market_data(market_data)
        
        # 调用策略具体实现
        signal = self.on_market_data(market_data)
        
        if signal:
            # 记录信号
            self.signals_history.append(signal)
            self.logger.info(f"生成交易信号: {signal.action} - 强度: {signal.strength}")
        
        return signal
    
    def update_position(self, position: Optional[Position]):
        """
        更新当前持仓
        
        Args:
            position: 当前持仓
        """
        self.current_position = position
        if position:
            self.logger.info(f"更新持仓: {position.side.value} {position.size} @ {position.entry_price}")
        else:
            self.logger.info("清空持仓")
    
    def get_latest_price(self) -> Optional[float]:
        """获取最新价格"""
        if self.market_data_history:
            return self.market_data_history[-1].close
        return None
    
    def get_price_history(self, length: int = 100) -> List[float]:
        """
        获取价格历史
        
        Args:
            length: 获取的长度
            
        Returns:
            价格历史列表
        """
        if not self.market_data_history:
            return []
        
        start_idx = max(0, len(self.market_data_history) - length)
        return [data.close for data in self.market_data_history[start_idx:]]
    
    def start(self):
        """启动策略"""
        self.is_running = True
        self.logger.info(f"策略 {self.strategy_name} 已启动")
    
    def stop(self):
        """停止策略"""
        self.is_running = False
        self.logger.info(f"策略 {self.strategy_name} 已停止")
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        return {
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'is_running': self.is_running,
            'current_position': self.current_position.to_dict() if self.current_position else None,
            'latest_price': self.get_latest_price(),
            'signals_count': len(self.signals_history),
            'data_points': len(self.market_data_history)
        }