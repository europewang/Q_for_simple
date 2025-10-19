"""
仓位管理模块
负责管理交易仓位，包括开仓、平仓、仓位跟踪等
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from shared.models.trade_models import Position, Order, Signal, MarketData, PositionSide, OrderSide, OrderType, OrderStatus
from shared.utils.logger import get_logger


@dataclass
class PositionInfo:
    """仓位信息"""
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    margin: float
    percentage: float
    timestamp: datetime


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化仓位管理器
        
        Args:
            config: 仓位管理配置
        """
        self.config = config
        self.logger = get_logger("PositionManager")
        
        # 仓位存储
        self.positions: Dict[str, Position] = {}
        self.position_history: List[Position] = []
        
        # 配置参数
        self.max_positions = config.get('max_positions', 5)  # 最大同时持仓数
        self.position_timeout = config.get('position_timeout', 3600)  # 仓位超时时间（秒）
        
        self.logger.info("仓位管理器初始化完成")
    
    def has_position(self, symbol: str) -> bool:
        """
        检查是否有持仓
        
        Args:
            symbol: 交易对符号
            
        Returns:
            是否有持仓
        """
        return symbol in self.positions and self.positions[symbol].size > 0
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            持仓信息，如果没有持仓则返回None
        """
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """
        获取所有持仓
        
        Returns:
            所有持仓列表
        """
        return [pos for pos in self.positions.values() if pos.size > 0]
    
    def can_open_new_position(self) -> bool:
        """
        检查是否可以开新仓位
        
        Returns:
            是否可以开新仓位
        """
        active_positions = len([pos for pos in self.positions.values() if pos.size > 0])
        return active_positions < self.max_positions
    
    def open_position(self, symbol: str, side: PositionSide, size: float, entry_price: float, 
                     order_id: str = None) -> Position:
        """
        开仓
        
        Args:
            symbol: 交易对符号
            side: 持仓方向
            size: 仓位大小
            entry_price: 入场价格
            order_id: 订单ID
            
        Returns:
            新建的持仓
        """
        # 检查是否已有持仓
        if self.has_position(symbol):
            existing_position = self.positions[symbol]
            # 如果方向相同，增加仓位
            if existing_position.side == side:
                return self._add_to_position(symbol, size, entry_price, order_id)
            else:
                # 如果方向相反，先平掉原仓位
                self.close_position(symbol, "方向相反，平仓")
        
        # 创建新仓位
        position = Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            margin=size,  # 简化处理，实际应该根据杠杆计算
            percentage=0.0,
            timestamp=datetime.now(),
            order_id=order_id
        )
        
        self.positions[symbol] = position
        self.logger.info(f"开仓成功: {symbol} {side.value} {size:.4f} @ {entry_price:.4f}")
        
        return position
    
    def _add_to_position(self, symbol: str, additional_size: float, price: float, order_id: str = None) -> Position:
        """
        增加仓位
        
        Args:
            symbol: 交易对符号
            additional_size: 增加的仓位大小
            price: 成交价格
            order_id: 订单ID
            
        Returns:
            更新后的持仓
        """
        position = self.positions[symbol]
        
        # 计算新的平均入场价格
        total_cost = position.size * position.entry_price + additional_size * price
        new_size = position.size + additional_size
        new_entry_price = total_cost / new_size
        
        # 更新仓位
        position.size = new_size
        position.entry_price = new_entry_price
        position.margin += additional_size  # 简化处理
        position.timestamp = datetime.now()
        
        self.logger.info(f"增加仓位: {symbol} +{additional_size:.4f} @ {price:.4f}, 新平均价格: {new_entry_price:.4f}")
        
        return position
    
    def close_position(self, symbol: str, reason: str = "", close_price: float = None) -> Optional[Position]:
        """
        平仓
        
        Args:
            symbol: 交易对符号
            reason: 平仓原因
            close_price: 平仓价格
            
        Returns:
            已平仓的持仓信息
        """
        if not self.has_position(symbol):
            self.logger.warning(f"尝试平仓不存在的持仓: {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # 如果没有提供平仓价格，使用当前价格
        if close_price is None:
            close_price = position.current_price
        
        # 计算已实现盈亏
        if position.side == PositionSide.LONG:
            realized_pnl = (close_price - position.entry_price) * position.size
        else:
            realized_pnl = (position.entry_price - close_price) * position.size
        
        position.realized_pnl = realized_pnl
        position.unrealized_pnl = 0.0
        
        # 记录到历史
        closed_position = Position(
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            current_price=close_price,
            unrealized_pnl=0.0,
            realized_pnl=realized_pnl,
            margin=position.margin,
            percentage=(realized_pnl / (position.entry_price * position.size)) * 100,
            timestamp=datetime.now(),
            order_id=position.order_id
        )
        
        self.position_history.append(closed_position)
        
        # 清除当前仓位
        position.size = 0.0
        del self.positions[symbol]
        
        self.logger.info(f"平仓完成: {symbol} {reason}, 已实现盈亏: {realized_pnl:.4f}")
        
        return closed_position
    
    def reduce_position(self, symbol: str, reduce_size: float, price: float, reason: str = "") -> Optional[Position]:
        """
        减仓
        
        Args:
            symbol: 交易对符号
            reduce_size: 减少的仓位大小
            price: 成交价格
            reason: 减仓原因
            
        Returns:
            更新后的持仓信息
        """
        if not self.has_position(symbol):
            self.logger.warning(f"尝试减仓不存在的持仓: {symbol}")
            return None
        
        position = self.positions[symbol]
        
        if reduce_size >= position.size:
            # 如果减仓大小大于等于当前仓位，直接平仓
            return self.close_position(symbol, f"减仓完全平仓: {reason}", price)
        
        # 计算部分已实现盈亏
        if position.side == PositionSide.LONG:
            partial_pnl = (price - position.entry_price) * reduce_size
        else:
            partial_pnl = (position.entry_price - price) * reduce_size
        
        # 更新仓位
        position.size -= reduce_size
        position.margin -= reduce_size  # 简化处理
        position.realized_pnl += partial_pnl
        position.timestamp = datetime.now()
        
        self.logger.info(f"减仓完成: {symbol} -{reduce_size:.4f} @ {price:.4f}, {reason}")
        
        return position
    
    def update_position_price(self, symbol: str, current_price: float):
        """
        更新仓位当前价格和未实现盈亏
        
        Args:
            symbol: 交易对符号
            current_price: 当前价格
        """
        if not self.has_position(symbol):
            return
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # 计算未实现盈亏
        if position.side == PositionSide.LONG:
            unrealized_pnl = (current_price - position.entry_price) * position.size
        else:
            unrealized_pnl = (position.entry_price - current_price) * position.size
        
        position.unrealized_pnl = unrealized_pnl
        
        # 计算盈亏百分比
        if position.entry_price > 0:
            if position.side == PositionSide.LONG:
                position.percentage = ((current_price - position.entry_price) / position.entry_price) * 100
            else:
                position.percentage = ((position.entry_price - current_price) / position.entry_price) * 100
    
    def update_all_positions(self, market_data: MarketData):
        """
        更新所有仓位的价格信息
        
        Args:
            market_data: 市场数据
        """
        if market_data.symbol in self.positions:
            self.update_position_price(market_data.symbol, market_data.close)
    
    def get_total_unrealized_pnl(self) -> float:
        """
        获取总未实现盈亏
        
        Returns:
            总未实现盈亏
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values() if pos.size > 0)
    
    def get_total_realized_pnl(self) -> float:
        """
        获取总已实现盈亏
        
        Returns:
            总已实现盈亏
        """
        current_realized = sum(pos.realized_pnl for pos in self.positions.values())
        history_realized = sum(pos.realized_pnl for pos in self.position_history)
        return current_realized + history_realized
    
    def get_position_info(self, symbol: str) -> Optional[PositionInfo]:
        """
        获取仓位详细信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            仓位详细信息
        """
        if not self.has_position(symbol):
            return None
        
        position = self.positions[symbol]
        return PositionInfo(
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            current_price=position.current_price,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            margin=position.margin,
            percentage=position.percentage,
            timestamp=position.timestamp
        )
    
    def get_all_position_info(self) -> List[PositionInfo]:
        """
        获取所有仓位详细信息
        
        Returns:
            所有仓位详细信息列表
        """
        return [self.get_position_info(symbol) for symbol in self.positions.keys() 
                if self.has_position(symbol)]
    
    def cleanup_expired_positions(self):
        """清理过期的空仓位记录"""
        current_time = datetime.now()
        expired_symbols = []
        
        for symbol, position in self.positions.items():
            if position.size == 0:
                time_diff = (current_time - position.timestamp).total_seconds()
                if time_diff > self.position_timeout:
                    expired_symbols.append(symbol)
        
        for symbol in expired_symbols:
            del self.positions[symbol]
            self.logger.info(f"清理过期空仓位: {symbol}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取仓位管理状态
        
        Returns:
            仓位管理状态
        """
        active_positions = [pos for pos in self.positions.values() if pos.size > 0]
        
        return {
            'active_positions_count': len(active_positions),
            'max_positions': self.max_positions,
            'total_unrealized_pnl': self.get_total_unrealized_pnl(),
            'total_realized_pnl': self.get_total_realized_pnl(),
            'positions': [
                {
                    'symbol': pos.symbol,
                    'side': pos.side.value,
                    'size': pos.size,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'unrealized_pnl': pos.unrealized_pnl,
                    'percentage': pos.percentage
                }
                for pos in active_positions
            ],
            'position_history_count': len(self.position_history)
        }