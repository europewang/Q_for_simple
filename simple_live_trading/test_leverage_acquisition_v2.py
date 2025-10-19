import os
import logging
from dotenv import load_dotenv
from binance.um_futures import UMFutures

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(dotenv_path='/home/ubuntu/Code/quant/.env')

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

if not api_key or not api_secret:
    logger.error("请在 .env 文件中设置 BINANCE_API_KEY 和 BINANCE_API_SECRET")
    exit()

class MockWebTrader:
    def __init__(self, api_key, api_secret):
        self.client = UMFutures(key=api_key, secret=api_secret)
        self.logger = logger
        self.current_leverage = 25 # 初始值，用于模拟

    def get_leverage_from_api(self, symbol: str):
        try:
            account_info = self.client.futures_account()
            current_api_leverage = None
            for pos in account_info.get('positions', []):
                if pos.get('symbol') == symbol:
                    current_api_leverage = int(pos.get('leverage'))
                    break
            
            if current_api_leverage is not None:
                self.logger.info(f"✅ 成功从API获取 {symbol} 的实际杠杆: {current_api_leverage}x")
                return current_api_leverage
            else:
                self.logger.warning(f"⚠️ 未能从API获取 {symbol} 的实际杠杆（从 futures_account 未找到）")
                return None
        except Exception as e:
            self.logger.error(f"❌ 获取 {symbol} 实际杠杆失败: {e}")
            return None

if __name__ == "__main__":
    logger.info("开始测试 ETHUSDT 的杠杆获取逻辑 (v2)...")
    trader = MockWebTrader(api_key, api_secret)
    symbol_to_test = "ETHUSDT"
    leverage = trader.get_leverage_from_api(symbol_to_test)
    
    if leverage is not None:
        logger.info(f"最终获取到的 {symbol_to_test} 杠杆为: {leverage}x")
    else:
        logger.info(f"未能获取到 {symbol_to_test} 的杠杆。")