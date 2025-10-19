"""
交易所连接器
提供统一的交易所接口，支持多个交易所
"""
import asyncio
import hmac
import hashlib
import time
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

import aiohttp
import websockets

from shared.models.trade_models import MarketData, Order, Position, AccountInfo, OrderSide, OrderType, OrderStatus, PositionSide
from shared.utils.logger import get_logger


class ExchangeConnector(ABC):
    """交易所连接器基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(f"{self.__class__.__name__}")
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.testnet = config.get('testnet', True)
        
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """获取持仓信息"""
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                          quantity: float, price: float = None) -> Order:
        """创建订单"""
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        pass
    
    @abstractmethod
    async def get_order_status(self, symbol: str, order_id: str) -> Order:
        """获取订单状态"""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """获取市场数据"""
        pass


class BinanceConnector(ExchangeConnector):
    """币安交易所连接器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if self.testnet:
            self.base_url = "https://testnet.binancefuture.com"
            self.ws_url = "wss://stream.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
            self.ws_url = "wss://fstream.binance.com"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger.info(f"币安连接器初始化完成，测试网: {self.testnet}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                           signed: bool = False) -> Dict[str, Any]:
        """发送HTTP请求"""
        if params is None:
            params = {}
        
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                async with session.get(url, params=params, headers=headers) as response:
                    return await response.json()
            elif method.upper() == 'POST':
                async with session.post(url, data=params, headers=headers) as response:
                    return await response.json()
            elif method.upper() == 'DELETE':
                async with session.delete(url, params=params, headers=headers) as response:
                    return await response.json()
        except Exception as e:
            self.logger.error(f"请求失败: {method} {endpoint}, 错误: {str(e)}")
            raise
    
    async def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        try:
            response = await self._make_request('GET', '/fapi/v2/account', signed=True)
            
            total_wallet_balance = float(response.get('totalWalletBalance', 0))
            available_balance = float(response.get('availableBalance', 0))
            total_unrealized_pnl = float(response.get('totalUnrealizedProfit', 0))
            total_margin_balance = float(response.get('totalMarginBalance', 0))
            
            return AccountInfo(
                total_wallet_balance=total_wallet_balance,
                total_unrealized_pnl=total_unrealized_pnl,
                total_margin_balance=total_margin_balance,
                total_position_initial_margin=float(response.get('totalPositionInitialMargin', 0)),
                total_open_order_initial_margin=float(response.get('totalOpenOrderInitialMargin', 0)),
                available_balance=available_balance,
                max_withdraw_amount=float(response.get('maxWithdrawAmount', available_balance)),
                timestamp=datetime.now()
            )
        except Exception as e:
            self.logger.error(f"获取账户信息失败: {str(e)}")
            raise
    
    async def get_positions(self) -> List[Position]:
        """获取持仓信息"""
        try:
            response = await self._make_request('GET', '/fapi/v2/positionRisk', signed=True)
            
            positions = []
            for pos_data in response:
                position_amt = float(pos_data.get('positionAmt', 0))
                if position_amt != 0:  # 只返回有持仓的
                    side = PositionSide.LONG if position_amt > 0 else PositionSide.SHORT
                    
                    position = Position(
                        symbol=pos_data.get('symbol'),
                        side=side,
                        size=abs(position_amt),
                        entry_price=float(pos_data.get('entryPrice', 0)),
                        current_price=float(pos_data.get('markPrice', 0)),
                        unrealized_pnl=float(pos_data.get('unRealizedProfit', 0)),
                        realized_pnl=0.0,  # 需要从其他接口获取
                        margin=float(pos_data.get('isolatedMargin', 0)),
                        percentage=float(pos_data.get('percentage', 0)),
                        timestamp=datetime.now()
                    )
                    positions.append(position)
            
            return positions
        except Exception as e:
            self.logger.error(f"获取持仓信息失败: {str(e)}")
            raise
    
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                          quantity: float, price: float = None) -> Order:
        """创建订单"""
        try:
            params = {
                'symbol': symbol,
                'side': side.value,
                'type': order_type.value,
                'quantity': str(quantity)
            }
            
            if order_type == OrderType.LIMIT and price is not None:
                params['price'] = str(price)
                params['timeInForce'] = 'GTC'  # Good Till Cancel
            
            response = await self._make_request('POST', '/fapi/v1/order', params, signed=True)
            
            return Order(
                order_id=str(response.get('orderId')),
                symbol=response.get('symbol'),
                side=OrderSide(response.get('side')),
                type=OrderType(response.get('type')),
                quantity=float(response.get('origQty', 0)),
                price=float(response.get('price', 0)) if response.get('price') else 0.0,
                status=OrderStatus.PENDING,
                timestamp=datetime.now(),
                filled_price=0.0,
                filled_quantity=0.0,
                commission=0.0
            )
        except Exception as e:
            self.logger.error(f"创建订单失败: {str(e)}")
            raise
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            await self._make_request('DELETE', '/fapi/v1/order', params, signed=True)
            return True
        except Exception as e:
            self.logger.error(f"取消订单失败: {str(e)}")
            return False
    
    async def get_order_status(self, symbol: str, order_id: str) -> Order:
        """获取订单状态"""
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            response = await self._make_request('GET', '/fapi/v1/order', params, signed=True)
            
            # 映射订单状态
            status_mapping = {
                'NEW': OrderStatus.PENDING,
                'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
                'FILLED': OrderStatus.FILLED,
                'CANCELED': OrderStatus.CANCELLED,
                'REJECTED': OrderStatus.FAILED,
                'EXPIRED': OrderStatus.FAILED
            }
            
            return Order(
                order_id=str(response.get('orderId')),
                symbol=response.get('symbol'),
                side=OrderSide(response.get('side')),
                type=OrderType(response.get('type')),
                quantity=float(response.get('origQty', 0)),
                price=float(response.get('price', 0)) if response.get('price') else 0.0,
                status=status_mapping.get(response.get('status'), OrderStatus.UNKNOWN),
                timestamp=datetime.fromtimestamp(response.get('time', 0) / 1000),
                filled_price=float(response.get('avgPrice', 0)) if response.get('avgPrice') else 0.0,
                filled_quantity=float(response.get('executedQty', 0)),
                commission=0.0  # 需要从其他接口获取
            )
        except Exception as e:
            self.logger.error(f"获取订单状态失败: {str(e)}")
            raise
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """获取市场数据"""
        try:
            # 获取24小时价格变动统计
            response = await self._make_request('GET', '/fapi/v1/ticker/24hr', {'symbol': symbol})
            
            return MarketData(
                symbol=symbol,
                open=float(response.get('openPrice', 0)),
                high=float(response.get('highPrice', 0)),
                low=float(response.get('lowPrice', 0)),
                close=float(response.get('lastPrice', 0)),
                volume=float(response.get('volume', 0)),
                timestamp=datetime.now()
            )
        except Exception as e:
            self.logger.error(f"获取市场数据失败: {str(e)}")
            raise
    
    async def close(self):
        """关闭连接"""
        if self.session and not self.session.closed:
            await self.session.close()


class MockExchangeConnector(ExchangeConnector):
    """模拟交易所连接器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # 模拟账户状态
        self.mock_balance = config.get('initial_balance', 10000.0)
        self.mock_positions: Dict[str, Position] = {}
        self.mock_orders: Dict[str, Order] = {}
        self.order_counter = 1
        
        self.logger.info("模拟交易所连接器初始化完成")
    
    async def get_account_info(self) -> AccountInfo:
        """获取模拟账户信息"""
        # 计算总未实现盈亏
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.mock_positions.values())
        
        return AccountInfo(
            total_wallet_balance=self.mock_balance,
            total_unrealized_pnl=total_unrealized_pnl,
            total_margin_balance=self.mock_balance + total_unrealized_pnl,
            total_position_initial_margin=0.0,  # 模拟环境暂设为0
            total_open_order_initial_margin=0.0,  # 模拟环境暂设为0
            available_balance=self.mock_balance * 0.9,  # 假设90%可用
            max_withdraw_amount=self.mock_balance * 0.9,  # 与可用余额相同
            timestamp=datetime.now()
        )
    
    async def get_positions(self) -> List[Position]:
        """获取模拟持仓信息"""
        return list(self.mock_positions.values())
    
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                          quantity: float, price: float = None) -> Order:
        """创建模拟订单"""
        order_id = f"MOCK_{self.order_counter}"
        self.order_counter += 1
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price or 0.0,
            status=OrderStatus.PENDING,
            timestamp=datetime.now(),
            filled_price=0.0,
            filled_quantity=0.0,
            commission=0.0
        )
        
        self.mock_orders[order_id] = order
        
        # 模拟立即成交（市价单）
        if order_type == OrderType.MARKET:
            await asyncio.sleep(0.1)  # 模拟延迟
            order.status = OrderStatus.FILLED
            order.filled_price = price or 0.0
            order.filled_quantity = quantity
            order.commission = quantity * (price or 0.0) * 0.001  # 0.1% 手续费
        
        return order
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消模拟订单"""
        if order_id in self.mock_orders:
            order = self.mock_orders[order_id]
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                return True
        return False
    
    async def get_order_status(self, symbol: str, order_id: str) -> Order:
        """获取模拟订单状态"""
        if order_id in self.mock_orders:
            return self.mock_orders[order_id]
        else:
            raise ValueError(f"订单不存在: {order_id}")
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """获取模拟市场数据"""
        # 生成模拟价格数据
        import random
        base_price = 50000.0 if 'BTC' in symbol else 3000.0  # BTC或ETH基础价格
        
        current_price = base_price * (1 + random.uniform(-0.02, 0.02))  # ±2%波动
        
        return MarketData(
            symbol=symbol,
            open=current_price * 0.99,
            high=current_price * 1.01,
            low=current_price * 0.98,
            close=current_price,
            volume=random.uniform(1000, 10000),
            timestamp=datetime.now()
        )
    
    async def close(self):
        """关闭模拟连接"""
        pass


def create_exchange_connector(exchange_name: str, config: Dict[str, Any]) -> ExchangeConnector:
    """
    创建交易所连接器工厂函数
    
    Args:
        exchange_name: 交易所名称
        config: 配置信息
        
    Returns:
        交易所连接器实例
    """
    if exchange_name.lower() == 'binance':
        return BinanceConnector(config)
    elif exchange_name.lower() == 'mock':
        return MockExchangeConnector(config)
    else:
        raise ValueError(f"不支持的交易所: {exchange_name}")