"""
简单EMA交叉策略 - 实时交易版本
基于快慢EMA交叉的实时交易策略
"""
from datetime import datetime
from typing import Optional, Dict, Any

from .base_live_strategy import BaseLiveStrategy
from shared.models.trade_models import MarketData, Signal, PositionSide
from shared.indicators.ema import EMAStrategy


class LiveSimpleEMAStrategy(BaseLiveStrategy):
    """简单EMA交叉策略 - 实时版本"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        """
        初始化EMA策略
        
        Args:
            symbol: 交易对符号
            config: 策略配置
        """
        super().__init__("LiveSimpleEMA", symbol, config)
        
        # EMA参数
        self.fast_period = config.get('fast_period', 12)
        self.slow_period = config.get('slow_period', 26)
        self.position_percentage = config.get('position_percentage', 0.95)
        self.min_signal_strength = config.get('min_signal_strength', 0.5)
        
        # 初始化EMA策略
        self.ema_strategy = EMAStrategy(self.fast_period, self.slow_period)
        
        # 策略状态
        self.last_signal_action = None
        self.signal_count = 0
        
        self.logger.info(f"EMA策略参数: 快线={self.fast_period}, 慢线={self.slow_period}")
    
    def on_market_data(self, market_data: MarketData) -> Optional[Signal]:
        """
        处理市场数据并生成交易信号
        
        Args:
            market_data: 市场数据
            
        Returns:
            交易信号（如果有）
        """
        # 更新EMA策略
        signal_action = self.ema_strategy.update(market_data.close)
        
        # 只有在信号发生变化时才生成信号
        if signal_action != 'HOLD' and signal_action != self.last_signal_action:
            self.last_signal_action = signal_action
            self.signal_count += 1
            
            # 计算信号强度
            ema_values = self.ema_strategy.get_ema_values()
            if ema_values['fast_ema'] and ema_values['slow_ema']:
                # 基于EMA差值计算信号强度
                price_diff = abs(ema_values['fast_ema'] - ema_values['slow_ema'])
                strength = min(price_diff / market_data.close, 1.0)
            else:
                strength = 0.5
            
            # 只有信号强度足够时才生成信号
            if strength >= self.min_signal_strength:
                signal = Signal(
                    symbol=self.symbol,
                    action=signal_action,
                    strength=strength,
                    price=market_data.close,
                    timestamp=market_data.timestamp,
                    strategy_name=self.strategy_name,
                    metadata={
                        'fast_ema': ema_values['fast_ema'],
                        'slow_ema': ema_values['slow_ema'],
                        'signal_count': self.signal_count
                    }
                )
                
                self.logger.info(f"生成EMA交叉信号: {signal_action} @ {market_data.close:.2f}, 强度: {strength:.3f}")
                return signal
        
        return None
    
    def calculate_position_size(self, signal: Signal, account_balance: float) -> float:
        """
        计算仓位大小
        
        Args:
            signal: 交易信号
            account_balance: 账户余额
            
        Returns:
            仓位大小（USDT金额）
        """
        # 基础仓位大小
        base_position_size = account_balance * self.position_percentage
        
        # 根据信号强度调整仓位
        adjusted_size = base_position_size * signal.strength
        
        # 确保最小仓位大小
        min_position_size = self.config.get('min_position_size', 10.0)
        adjusted_size = max(adjusted_size, min_position_size)
        
        # 确保不超过最大仓位大小
        max_position_size = self.config.get('max_position_size', account_balance * 0.95)
        adjusted_size = min(adjusted_size, max_position_size)
        
        self.logger.info(f"计算仓位大小: {adjusted_size:.2f} USDT (信号强度: {signal.strength:.3f})")
        return adjusted_size
    
    def should_close_position(self, current_price: float) -> bool:
        """
        判断是否应该平仓
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否应该平仓
        """
        if not self.current_position:
            return False
        
        # 获取当前EMA值
        ema_values = self.ema_strategy.get_ema_values()
        if not ema_values['fast_ema'] or not ema_values['slow_ema']:
            return False
        
        # 检查是否出现反向信号
        if self.current_position.side == PositionSide.LONG:
            # 多头持仓，检查是否出现空头信号
            return ema_values['fast_ema'] < ema_values['slow_ema']
        else:
            # 空头持仓，检查是否出现多头信号
            return ema_values['fast_ema'] > ema_values['slow_ema']
    
    def get_stop_loss_price(self, entry_price: float, position_side: PositionSide) -> Optional[float]:
        """
        计算止损价格
        
        Args:
            entry_price: 入场价格
            position_side: 持仓方向
            
        Returns:
            止损价格
        """
        stop_loss_percentage = self.config.get('stop_loss_percentage', 0.02)  # 2%止损
        
        if position_side == PositionSide.LONG:
            return entry_price * (1 - stop_loss_percentage)
        else:
            return entry_price * (1 + stop_loss_percentage)
    
    def get_take_profit_price(self, entry_price: float, position_side: PositionSide) -> Optional[float]:
        """
        计算止盈价格
        
        Args:
            entry_price: 入场价格
            position_side: 持仓方向
            
        Returns:
            止盈价格
        """
        take_profit_percentage = self.config.get('take_profit_percentage', 0.06)  # 6%止盈
        
        if position_side == PositionSide.LONG:
            return entry_price * (1 + take_profit_percentage)
        else:
            return entry_price * (1 - take_profit_percentage)
    
    def reset_strategy(self):
        """重置策略状态"""
        self.ema_strategy.reset()
        self.last_signal_action = None
        self.signal_count = 0
        self.market_data_history.clear()
        self.signals_history.clear()
        self.logger.info("策略状态已重置")
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        ema_values = self.ema_strategy.get_ema_values()
        
        return {
            **self.get_strategy_info(),
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'fast_ema': ema_values['fast_ema'],
            'slow_ema': ema_values['slow_ema'],
            'last_signal_action': self.last_signal_action,
            'signal_count': self.signal_count,
            'position_percentage': self.position_percentage
        }