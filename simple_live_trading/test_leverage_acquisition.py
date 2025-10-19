import os
import logging
from binance.client import Client
from dotenv import dotenv_values

# 从 .env 文件加载配置
config_env = dotenv_values("/home/ubuntu/Code/quant/.env")

api_key = config_env.get('API_KEY')
api_secret = config_env.get('API_SECRET')

if not api_key or not api_secret:
    print("错误：请设置 BINANCE_API_KEY 和 BINANCE_API_SECRET 环境变量")
    exit()

class MockWebTrader:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.logger = self._setup_logger()
        self.current_leverage = 25  # 初始内部记录杠杆值

    def _setup_logger(self):
        logger = logging.getLogger("MockWebTrader")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def test_leverage_acquisition_logic(self, symbol: str):
        self.logger.info(f"开始测试 {symbol} 的杠杆获取逻辑...")
        try:
            account_info = self.client.futures_account()
            current_api_leverage = None
            for pos in account_info.get('positions', []):
                if pos.get('symbol') == symbol:
                    current_api_leverage = int(pos.get('leverage'))
                    break
            
            if current_api_leverage is not None:
                old_leverage = self.current_leverage
                self.current_leverage = current_api_leverage
                self.logger.info(f"✅ 成功从API获取 {symbol} 的实际杠杆: {current_api_leverage}x")
                self.logger.info(f"内部记录杠杆已更新: {old_leverage}x -> {self.current_leverage}x")
            else:
                self.logger.warning(f"⚠️ 未能从API获取 {symbol} 的实际杠杆（从 futures_account 未找到），使用内部记录值 {self.current_leverage}x")
                old_leverage = self.current_leverage
                self.logger.info(f"内部记录杠杆保持不变: {old_leverage}x")
        except Exception as e:
            self.logger.error(f"❌ 获取 {symbol} 实际杠杆失败: {e}，使用内部记录值 {self.current_leverage}x")
            old_leverage = self.current_leverage
            self.logger.info(f"内部记录杠杆保持不变: {old_leverage}x")

# 实例化并运行测试
mock_trader = MockWebTrader(api_key, api_secret)
mock_trader.test_leverage_acquisition_logic(symbol='ETHUSDT')