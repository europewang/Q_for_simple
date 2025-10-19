"""
实时市场数据获取模块
支持WebSocket和REST API数据获取
"""
import asyncio
import json
import websockets
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List
from binance.client import Client
from binance import ThreadedWebsocketManager
import threading
import queue

from shared.models.trade_models import MarketData
from shared.utils.logger import get_logger


class MarketDataFeed:
    """市场数据获取基类"""
    
    def __init__(self, symbol: str):
        """
        初始化市场数据获取器
        
        Args:
            symbol: 交易对符号
        """
        self.symbol = symbol
        self.logger = get_logger(f"MarketDataFeed_{symbol}")
        self.callbacks: List[Callable[[MarketData], None]] = []
        self.is_running = False
    
    def add_callback(self, callback: Callable[[MarketData], None]):
        """添加数据回调函数"""
        self.callbacks.append(callback)
    
    def set_callback(self, callback: Callable[[MarketData], None]):
        """设置数据回调函数（清除现有回调并设置新的）"""
        self.callbacks.clear()
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[MarketData], None]):
        """移除数据回调函数"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _notify_callbacks(self, market_data: MarketData):
        """通知所有回调函数"""
        for callback in self.callbacks:
            try:
                callback(market_data)
            except Exception as e:
                self.logger.error(f"回调函数执行错误: {e}")
    
    def start(self):
        """开始获取数据"""
        raise NotImplementedError
    
    def stop(self):
        """停止获取数据"""
        self.is_running = False


class BinanceDataFeed(MarketDataFeed):
    """币安市场数据获取器"""
    
    def __init__(self, symbol: str, api_key: str = None, api_secret: str = None, interval: str = "1m"):
        """
        初始化币安数据获取器
        
        Args:
            symbol: 交易对符号
            api_key: API密钥
            api_secret: API密钥
            interval: K线间隔
        """
        super().__init__(symbol)
        self.api_key = api_key
        self.api_secret = api_secret
        self.interval = interval
        self.client = None
        self.socket_manager = None
        self.conn_key = None
        self.data_queue = queue.Queue()
        self.worker_thread = None
        
        if api_key and api_secret:
            self.client = Client(api_key, api_secret)
    
    def _process_kline_data(self, msg):
        """处理K线数据"""
        try:
            if msg['e'] == 'kline':
                kline = msg['k']
                
                # 只处理已完成的K线
                if kline['x']:  # x表示K线是否已完成
                    market_data = MarketData(
                        symbol=kline['s'],
                        timestamp=datetime.fromtimestamp(kline['t'] / 1000, tz=timezone.utc),
                        open=float(kline['o']),
                        high=float(kline['h']),
                        low=float(kline['l']),
                        close=float(kline['c']),
                        volume=float(kline['v'])
                    )
                    
                    self.data_queue.put(market_data)
                    self.logger.info(f"接收到K线数据: {self.symbol} - {market_data.close}")
        
        except Exception as e:
            self.logger.error(f"处理K线数据错误: {e}")
    
    def _data_worker(self):
        """数据处理工作线程"""
        while self.is_running:
            try:
                # 从队列获取数据，超时1秒
                market_data = self.data_queue.get(timeout=1)
                self._notify_callbacks(market_data)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"数据处理工作线程错误: {e}")
    
    def start(self):
        """开始获取实时数据"""
        if self.is_running:
            self.logger.warning("数据获取已在运行中")
            return
        
        self.is_running = True
        self.logger.info(f"开始获取 {self.symbol} 的实时数据")
        
        try:
            # 启动数据处理工作线程
            self.worker_thread = threading.Thread(target=self._data_worker)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            
            # 启动WebSocket连接
            if self.client:
                self.socket_manager = ThreadedWebsocketManager(
                    api_key=self.client.API_KEY,
                    api_secret=self.client.API_SECRET
                )
                self.socket_manager.start()
                self.conn_key = self.socket_manager.start_kline_socket(
                    callback=self._process_kline_data,
                    symbol=self.symbol,
                    interval=self.interval
                )
            else:
                self.logger.warning("未提供API密钥，使用公共WebSocket连接")
                # 使用公共WebSocket连接
                asyncio.create_task(self._start_public_websocket())
        
        except Exception as e:
            self.logger.error(f"启动数据获取失败: {e}")
            self.is_running = False
    
    async def _start_public_websocket(self):
        """启动公共WebSocket连接"""
        uri = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@kline_{self.interval}"
        
        try:
            async with websockets.connect(uri) as websocket:
                self.logger.info(f"WebSocket连接已建立: {uri}")
                
                while self.is_running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        self._process_kline_data(data)
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.logger.error(f"WebSocket数据接收错误: {e}")
                        break
        
        except Exception as e:
            self.logger.error(f"WebSocket连接错误: {e}")
    
    def stop(self):
        """停止获取数据"""
        self.logger.info("停止数据获取")
        super().stop()
        
        if self.socket_manager:
            if self.conn_key:
                self.socket_manager.stop_socket(self.conn_key)
            self.socket_manager.stop()
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
    
    def get_historical_data(self, limit: int = 100) -> List[MarketData]:
        """
        获取历史数据
        
        Args:
            limit: 获取的数据条数
            
        Returns:
            历史市场数据列表
        """
        if not self.client:
            self.logger.error("需要API密钥才能获取历史数据")
            return []
        
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=limit
            )
            
            historical_data = []
            for kline in klines:
                market_data = MarketData(
                    symbol=self.symbol,
                    timestamp=datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5])
                )
                historical_data.append(market_data)
            
            self.logger.info(f"获取到 {len(historical_data)} 条历史数据")
            return historical_data
        
        except Exception as e:
            self.logger.error(f"获取历史数据失败: {e}")
            return []


class MockDataFeed(MarketDataFeed):
    """模拟市场数据获取器（用于测试）"""
    
    def __init__(self, symbol: str, base_price: float = 50000.0, interval: float = 1.0):
        """
        初始化模拟数据获取器
        
        Args:
            symbol: 交易对符号
            base_price: 基础价格
            interval: 数据推送间隔（秒）
        """
        super().__init__(symbol)
        self.interval = interval
        self.base_price = base_price
        self.current_price = self.base_price
        self.worker_thread = None
    
    def _generate_mock_data(self):
        """生成模拟数据"""
        import random
        
        # 模拟价格波动
        change_percent = random.uniform(-0.01, 0.01)  # ±1%的波动
        self.current_price *= (1 + change_percent)
        
        # 生成OHLCV数据
        open_price = self.current_price
        high_price = open_price * (1 + random.uniform(0, 0.005))
        low_price = open_price * (1 - random.uniform(0, 0.005))
        close_price = random.uniform(low_price, high_price)
        volume = random.uniform(100, 1000)
        
        self.current_price = close_price
        
        return MarketData(
            symbol=self.symbol,
            timestamp=datetime.now(timezone.utc),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        )
    
    def _data_worker(self):
        """数据生成工作线程"""
        while self.is_running:
            try:
                market_data = self._generate_mock_data()
                self._notify_callbacks(market_data)
                self.logger.info(f"生成模拟数据: {self.symbol} - {market_data.close:.2f}")
                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"模拟数据生成错误: {e}")
    
    def start(self):
        """开始生成模拟数据"""
        if self.is_running:
            self.logger.warning("模拟数据生成已在运行中")
            return
        
        self.is_running = True
        self.logger.info(f"开始生成 {self.symbol} 的模拟数据")
        
        self.worker_thread = threading.Thread(target=self._data_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def stop(self):
        """停止生成模拟数据"""
        self.logger.info("停止模拟数据生成")
        super().stop()
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)


def create_market_data_feed(source: str = None, config: Dict[str, Any] = None) -> MarketDataFeed:
    """
    工厂函数：根据配置创建市场数据源
    
    Args:
        source: 数据源类型 ('binance', 'mock')
        config: 数据源配置
        
    Returns:
        MarketDataFeed: 数据源实例
    """
    # 兼容两种调用方式
    if source is None and config is not None:
        source = config.get('source', 'mock')
    elif source is None:
        source = 'mock'
    
    if config is None:
        config = {}
    
    symbol = config.get('symbol', 'BTCUSDT')
    
    if source == 'binance':
        # 从环境变量或配置获取API密钥
        api_key = config.get('api_key')
        api_secret = config.get('api_secret')
        interval = config.get('interval', '1m')
        
        return BinanceDataFeed(
            symbol=symbol,
            api_key=api_key,
            api_secret=api_secret,
            interval=interval
        )
    elif source == 'mock':
        base_price = config.get('base_price', 50000.0)
        interval = config.get('update_interval', 1)
        
        return MockDataFeed(
            symbol=symbol,
            base_price=base_price,
            interval=interval
        )
    else:
        raise ValueError(f"不支持的数据源类型: {source}")


# 导出主要类和函数
__all__ = [
    'MarketDataFeed',
    'BinanceDataFeed', 
    'MockDataFeed',
    'create_market_data_feed'
]