import unittest
from unittest.mock import MagicMock, patch
import os

# 模拟 CONFIG
CONFIG = {
    "api_key": "test_api_key",
    "api_secret": "test_api_secret",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "base_leverage": 25,
}

# 模拟 WebTrader 类
class WebTrader:
    def __init__(self):
        self.client = None
        self.logger = MagicMock() # 模拟 logger
        self.base_leverage = CONFIG["base_leverage"]
        self.symbol_leverages = {}

    def get_leverage_from_api(self, symbol: str):
        # 模拟从API获取杠杆的逻辑
        if symbol == "BTCUSDT":
            return 50
        elif symbol == "ETHUSDT":
            return 75
        return None

    def setup_binance_client(self):
        try:
            # 创建币安客户端实例
            self.client = MagicMock() # 模拟客户端
            
            # 测试API连接是否正常
            self.client.ping.return_value = None
            self.logger.info("币安API连接成功")
            
            # 设置单向持仓模式（禁用双向持仓）
            self.client.futures_change_position_mode.return_value = None
            self.logger.info("✅ 单向持仓模式设置成功")
            
            # 设置杠杆倍数（使用当前动态杠杆）
            for symbol in CONFIG['symbols']:
                try:
                    # 从API获取杠杆
                    leverage = self.get_leverage_from_api(symbol) or self.base_leverage
                    self.symbol_leverages[symbol] = leverage
                    self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
                    self.logger.info(f"✅ {symbol} 杠杆设置为 {leverage}x（动态杠杆）")
                except Exception as e:
                    self.logger.warning(f"⚠️ {symbol} 杠杆设置失败: {e}")
            
        except Exception as e:
            self.logger.error(f"币安API连接失败: {e}")
            raise  # 重新抛出异常，因为API连接是系统运行的前提

class TestWebTraderLeverage(unittest.TestCase):

    def setUp(self):
        self.trader = WebTrader()

    def test_setup_binance_client_leverage_acquisition(self):
        self.trader.setup_binance_client()

        # 验证 symbol_leverages 是否正确填充
        self.assertEqual(self.trader.symbol_leverages["BTCUSDT"], 50)
        self.assertEqual(self.trader.symbol_leverages["ETHUSDT"], 75)

        # 验证 client.futures_change_leverage 是否被正确调用
        self.trader.client.futures_change_leverage.assert_any_call(symbol="BTCUSDT", leverage=50)
        self.trader.client.futures_change_leverage.assert_any_call(symbol="ETHUSDT", leverage=75)
        
        # 验证日志是否正确记录
        self.trader.logger.info.assert_any_call("币安API连接成功")
        self.trader.logger.info.assert_any_call("✅ 单向持仓模式设置成功")
        self.trader.logger.info.assert_any_call("✅ BTCUSDT 杠杆设置为 50x（动态杠杆）")
        self.trader.logger.info.assert_any_call("✅ ETHUSDT 杠杆设置为 75x（动态杠杆）")

if __name__ == '__main__':
    unittest.main()