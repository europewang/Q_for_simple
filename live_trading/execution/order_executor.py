"""
订单执行器
负责实际的订单执行、状态跟踪和交易所接口对接
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

from shared.models.trade_models import Order, OrderSide, OrderType, OrderStatus, Signal, Position, PositionSide
from shared.utils.logger import get_logger


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    order_id: str
    filled_price: float
    filled_quantity: float
    commission: float
    error_message: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class OrderExecutor:
    """订单执行器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化订单执行器
        
        Args:
            config: 执行器配置
        """
        self.config = config
        self.logger = get_logger("OrderExecutor")
        
        # 执行配置
        self.max_retry_count = config.get('max_retry_count', 3)
        self.retry_delay = config.get('retry_delay', 1.0)  # 重试延迟（秒）
        self.order_timeout = config.get('order_timeout', 30.0)  # 订单超时（秒）
        self.slippage_tolerance = config.get('slippage_tolerance', 0.001)  # 滑点容忍度
        
        # 订单管理
        self.pending_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        self.failed_orders: List[Order] = []
        
        # 模拟交易模式
        self.simulation_mode = config.get('simulation_mode', True)
        self.simulation_latency = config.get('simulation_latency', 0.1)  # 模拟延迟
        self.simulation_slippage = config.get('simulation_slippage', 0.0005)  # 模拟滑点
        
        # 回调函数
        self.order_filled_callback: Optional[Callable] = None
        self.order_failed_callback: Optional[Callable] = None
        
        self.logger.info(f"订单执行器初始化完成，模拟模式: {self.simulation_mode}")
    
    def set_callbacks(self, order_filled_callback: Callable = None, order_failed_callback: Callable = None):
        """
        设置回调函数
        
        Args:
            order_filled_callback: 订单成交回调
            order_failed_callback: 订单失败回调
        """
        self.order_filled_callback = order_filled_callback
        self.order_failed_callback = order_failed_callback
    
    async def execute_signal(self, signal: Signal, position_size: float, current_price: float) -> ExecutionResult:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            position_size: 仓位大小
            current_price: 当前价格
            
        Returns:
            执行结果
        """
        # 创建订单
        order = self._create_order_from_signal(signal, position_size, current_price)
        
        # 执行订单
        return await self.execute_order(order)
    
    async def execute_order(self, order: Order) -> ExecutionResult:
        """
        执行订单
        
        Args:
            order: 订单对象
            
        Returns:
            执行结果
        """
        self.logger.info(f"开始执行订单: {order.symbol} {order.side.value} {order.quantity} @ {order.price}")
        
        # 添加到待处理订单
        self.pending_orders[order.order_id] = order
        order.status = OrderStatus.PENDING
        
        try:
            # 执行订单（根据模式选择真实或模拟执行）
            if self.simulation_mode:
                result = await self._execute_order_simulation(order)
            else:
                result = await self._execute_order_real(order)
            
            # 处理执行结果
            if result.success:
                order.status = OrderStatus.FILLED
                order.filled_price = result.filled_price
                order.filled_quantity = result.filled_quantity
                order.commission = result.commission
                order.filled_time = result.timestamp
                
                self.completed_orders.append(order)
                
                # 调用成交回调
                if self.order_filled_callback:
                    await self._safe_callback(self.order_filled_callback, order, result)
                
                self.logger.info(f"订单执行成功: {order.order_id}")
            else:
                order.status = OrderStatus.FAILED
                self.failed_orders.append(order)
                
                # 调用失败回调
                if self.order_failed_callback:
                    await self._safe_callback(self.order_failed_callback, order, result)
                
                self.logger.error(f"订单执行失败: {order.order_id}, 错误: {result.error_message}")
            
            # 从待处理订单中移除
            if order.order_id in self.pending_orders:
                del self.pending_orders[order.order_id]
            
            return result
            
        except Exception as e:
            self.logger.error(f"订单执行异常: {order.order_id}, 错误: {str(e)}")
            order.status = OrderStatus.FAILED
            self.failed_orders.append(order)
            
            if order.order_id in self.pending_orders:
                del self.pending_orders[order.order_id]
            
            return ExecutionResult(
                success=False,
                order_id=order.order_id,
                filled_price=0.0,
                filled_quantity=0.0,
                commission=0.0,
                error_message=str(e)
            )
    
    async def _execute_order_simulation(self, order: Order) -> ExecutionResult:
        """
        模拟执行订单
        
        Args:
            order: 订单对象
            
        Returns:
            执行结果
        """
        # 模拟网络延迟
        await asyncio.sleep(self.simulation_latency)
        
        # 模拟滑点
        if order.side == OrderSide.BUY:
            filled_price = order.price * (1 + self.simulation_slippage)
        else:
            filled_price = order.price * (1 - self.simulation_slippage)
        
        # 模拟手续费（0.1%）
        commission = order.quantity * filled_price * 0.001
        
        # 模拟成功率（95%）
        import random
        if random.random() < 0.95:
            return ExecutionResult(
                success=True,
                order_id=order.order_id,
                filled_price=filled_price,
                filled_quantity=order.quantity,
                commission=commission
            )
        else:
            return ExecutionResult(
                success=False,
                order_id=order.order_id,
                filled_price=0.0,
                filled_quantity=0.0,
                commission=0.0,
                error_message="模拟执行失败"
            )
    
    async def _execute_order_real(self, order: Order) -> ExecutionResult:
        """
        真实执行订单（连接交易所API）
        
        Args:
            order: 订单对象
            
        Returns:
            执行结果
        """
        # TODO: 实现真实的交易所API调用
        # 这里需要根据具体的交易所API进行实现
        # 例如：Binance、OKX、Bybit等
        
        retry_count = 0
        while retry_count < self.max_retry_count:
            try:
                # 示例：调用交易所API
                # result = await self.exchange_client.create_order(
                #     symbol=order.symbol,
                #     side=order.side.value.lower(),
                #     type=order.type.value.lower(),
                #     amount=order.quantity,
                #     price=order.price if order.type == OrderType.LIMIT else None
                # )
                
                # 暂时返回模拟结果
                self.logger.warning("真实交易模式未实现，使用模拟执行")
                return await self._execute_order_simulation(order)
                
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"订单执行失败，重试 {retry_count}/{self.max_retry_count}: {str(e)}")
                
                if retry_count < self.max_retry_count:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return ExecutionResult(
                        success=False,
                        order_id=order.order_id,
                        filled_price=0.0,
                        filled_quantity=0.0,
                        commission=0.0,
                        error_message=f"重试{self.max_retry_count}次后仍然失败: {str(e)}"
                    )
    
    def _create_order_from_signal(self, signal: Signal, position_size: float, current_price: float) -> Order:
        """
        从信号创建订单
        
        Args:
            signal: 交易信号
            position_size: 仓位大小
            current_price: 当前价格
            
        Returns:
            订单对象
        """
        # 确定订单方向
        if signal.action == "BUY":
            side = OrderSide.BUY
        elif signal.action == "SELL":
            side = OrderSide.SELL
        else:
            raise ValueError(f"不支持的信号动作: {signal.action}")
        
        # 计算订单数量（基于USDT金额计算币的数量）
        quantity = position_size / current_price
        
        # 创建订单ID
        order_id = f"{signal.symbol}_{int(time.time() * 1000)}"
        
        return Order(
            order_id=order_id,
            symbol=signal.symbol,
            side=side,
            type=OrderType.MARKET,  # 默认使用市价单
            quantity=quantity,
            price=current_price,
            status=OrderStatus.CREATED,
            timestamp=datetime.now(),
            filled_price=0.0,
            filled_quantity=0.0,
            commission=0.0
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否取消成功
        """
        if order_id not in self.pending_orders:
            self.logger.warning(f"尝试取消不存在的订单: {order_id}")
            return False
        
        order = self.pending_orders[order_id]
        
        try:
            if self.simulation_mode:
                # 模拟取消
                order.status = OrderStatus.CANCELLED
                del self.pending_orders[order_id]
                self.logger.info(f"模拟取消订单成功: {order_id}")
                return True
            else:
                # TODO: 实现真实的取消订单API调用
                self.logger.warning("真实取消订单功能未实现")
                return False
                
        except Exception as e:
            self.logger.error(f"取消订单失败: {order_id}, 错误: {str(e)}")
            return False
    
    async def _safe_callback(self, callback: Callable, *args, **kwargs):
        """安全调用回调函数"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"回调函数执行失败: {str(e)}")
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        获取订单状态
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单状态
        """
        # 检查待处理订单
        if order_id in self.pending_orders:
            return self.pending_orders[order_id].status
        
        # 检查已完成订单
        for order in self.completed_orders:
            if order.order_id == order_id:
                return order.status
        
        # 检查失败订单
        for order in self.failed_orders:
            if order.order_id == order_id:
                return order.status
        
        return None
    
    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单列表"""
        return list(self.pending_orders.values())
    
    def get_completed_orders(self) -> List[Order]:
        """获取已完成订单列表"""
        return self.completed_orders.copy()
    
    def get_failed_orders(self) -> List[Order]:
        """获取失败订单列表"""
        return self.failed_orders.copy()
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        total_orders = len(self.completed_orders) + len(self.failed_orders)
        success_rate = len(self.completed_orders) / total_orders if total_orders > 0 else 0
        
        total_commission = sum(order.commission for order in self.completed_orders)
        
        return {
            'total_orders': total_orders,
            'completed_orders': len(self.completed_orders),
            'failed_orders': len(self.failed_orders),
            'pending_orders': len(self.pending_orders),
            'success_rate': success_rate,
            'total_commission': total_commission,
            'simulation_mode': self.simulation_mode
        }
    
    def cleanup_old_orders(self, max_age_hours: int = 24):
        """
        清理旧订单记录
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        # 清理已完成订单
        self.completed_orders = [
            order for order in self.completed_orders
            if order.timestamp.timestamp() > cutoff_time
        ]
        
        # 清理失败订单
        self.failed_orders = [
            order for order in self.failed_orders
            if order.timestamp.timestamp() > cutoff_time
        ]
        
        self.logger.info(f"清理了超过{max_age_hours}小时的旧订单记录")