"""
实时交易系统主启动脚本
整合所有模块，启动实时交易系统
"""
import asyncio
import signal
import sys
import os
from datetime import datetime
from typing import Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_trading.config.config_loader import load_live_trading_config, LiveTradingConfig
from live_trading.data.market_data_feed import create_market_data_feed
from live_trading.strategies.live_simple_ema_strategy import LiveSimpleEMAStrategy
from live_trading.risk_management.risk_manager import RiskManager
from live_trading.risk_management.position_manager import PositionManager
from live_trading.execution.order_executor import OrderExecutor
from live_trading.execution.exchange_connector import create_exchange_connector
from shared.utils.logger import get_logger, setup_logging
from shared.models.trade_models import MarketData, Signal


class LiveTradingSystem:
    """实时交易系统"""
    
    def __init__(self, config_path: str = None):
        """
        初始化实时交易系统
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_live_trading_config(config_path)
        
        # 设置日志
        setup_logging(
            level=self.config.logging.level,
            log_to_file=self.config.logging.log_to_file,
            log_directory=self.config.logging.log_directory
        )
        
        self.logger = get_logger("LiveTradingSystem")
        self.logger.info("实时交易系统初始化开始")
        
        # 系统状态
        self.running = False
        self.last_update_time = None
        
        # 初始化各个模块
        self._initialize_modules()
        
        self.logger.info("实时交易系统初始化完成")
    
    def _initialize_modules(self):
        """初始化各个模块"""
        try:
            # 初始化数据源
            self.data_feed = create_market_data_feed(
                source=self.config.data_feed.source,
                config=self.config.data_feed.__dict__
            )
            
            # 初始化交易所连接器
            self.exchange = create_exchange_connector(
                exchange_name=self.config.exchange.name,
                config=self.config.exchange.__dict__
            )
            
            # 初始化策略
            self.strategy = LiveSimpleEMAStrategy(
                symbol=self.config.trading.symbol,
                config=self.config.strategy.__dict__
            )
            
            # 初始化风险管理器
            self.risk_manager = RiskManager(self.config.risk_management.__dict__)
            
            # 初始化仓位管理器
            self.position_manager = PositionManager(self.config.position_management.__dict__)
            
            # 初始化订单执行器
            self.order_executor = OrderExecutor(self.config.execution.__dict__)
            
            # 设置回调函数
            self.order_executor.set_callbacks(
                order_filled_callback=self._on_order_filled,
                order_failed_callback=self._on_order_failed
            )
            
            # 设置数据源回调
            self.data_feed.set_callback(self._on_market_data)
            
            self.logger.info("所有模块初始化完成")
            
        except Exception as e:
            self.logger.error(f"模块初始化失败: {str(e)}")
            raise
    
    async def start(self):
        """启动交易系统"""
        if self.running:
            self.logger.warning("交易系统已在运行")
            return
        
        try:
            self.logger.info("启动实时交易系统")
            self.running = True
            
            # 保存事件循环引用
            self._event_loop = asyncio.get_event_loop()
            
            # 启动数据源
            self.data_feed.start()
            
            # 获取初始账户信息
            account_info = await self.exchange.get_account_info()
            self.risk_manager.update_account_info(account_info)
            self.risk_manager.reset_daily_stats()
            
            self.logger.info(f"初始账户余额: {account_info.total_wallet_balance:.2f} USDT")
            
            # 启动主循环
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"启动交易系统失败: {str(e)}")
            await self.stop()
            raise
    
    async def stop(self):
        """停止交易系统"""
        if not self.running:
            return
        
        self.logger.info("停止实时交易系统")
        self.running = False
        
        try:
            # 停止数据源
            self.data_feed.stop()
            
            # 关闭交易所连接
            await self.exchange.close()
            
            # 保存最终状态
            await self._save_final_state()
            
            self.logger.info("交易系统已停止")
            
        except Exception as e:
            self.logger.error(f"停止交易系统时出错: {str(e)}")
    
    async def _main_loop(self):
        """主循环"""
        self.logger.info("进入主循环")
        
        while self.running:
            try:
                # 更新账户信息
                account_info = await self.exchange.get_account_info()
                self.risk_manager.update_account_info(account_info)
                
                # 更新持仓信息
                positions = await self.exchange.get_positions()
                for position in positions:
                    # 更新仓位管理器中的持仓信息
                    pass  # 这里需要根据实际情况更新
                
                # 清理过期订单和仓位
                self.position_manager.cleanup_expired_positions()
                self.order_executor.cleanup_old_orders()
                
                # 检查是否需要强制平仓
                await self._check_force_close_positions()
                
                # 等待下一次更新
                await asyncio.sleep(self.config.monitoring.update_interval)
                
            except Exception as e:
                self.logger.error(f"主循环执行出错: {str(e)}")
                await asyncio.sleep(1)  # 出错时短暂等待
    
    def _on_market_data(self, market_data: MarketData):
        """处理市场数据（同步回调）"""
        try:
            # 如果事件循环正在运行，创建任务
            if self.running and hasattr(self, '_event_loop') and self._event_loop:
                asyncio.run_coroutine_threadsafe(
                    self._process_market_data_async(market_data), 
                    self._event_loop
                )
        except Exception as e:
            self.logger.error(f"市场数据处理错误: {e}")
    
    async def _process_market_data_async(self, market_data: MarketData):
        """异步处理市场数据"""
        try:
            self.last_update_time = datetime.now()
            
            # 更新策略
            signal = self.strategy.on_market_data(market_data)
            
            # 更新仓位价格
            self.position_manager.update_all_positions(market_data)
            
            # 如果有信号，处理交易逻辑
            if signal:
                await self._process_signal(signal, market_data)
            
            # 检查是否需要平仓
            await self._check_position_management(market_data)
            
        except Exception as e:
            self.logger.error(f"处理市场数据时出错: {str(e)}")
    
    async def _process_signal(self, signal: Signal, market_data: MarketData):
        """处理交易信号"""
        try:
            # 获取当前账户信息
            account_info = await self.exchange.get_account_info()
            current_position = self.position_manager.get_position(signal.symbol)
            
            # 风险管理验证
            if not self.risk_manager.validate_signal(signal, account_info, current_position):
                self.logger.warning(f"信号被风险管理器拒绝: {signal.symbol} {signal.action}")
                return
            
            # 计算仓位大小
            position_size = self.risk_manager.calculate_position_size(signal, account_info)
            
            # 检查是否可以开新仓位
            if signal.action in ["BUY", "SELL"] and not self.position_manager.has_position(signal.symbol):
                if not self.position_manager.can_open_new_position():
                    self.logger.warning("已达到最大持仓数量限制")
                    return
            
            # 执行信号
            result = await self.order_executor.execute_signal(signal, position_size, market_data.close)
            
            if result.success:
                self.logger.info(f"信号执行成功: {signal.symbol} {signal.action} {position_size:.2f}")
            else:
                self.logger.error(f"信号执行失败: {result.error_message}")
            
        except Exception as e:
            self.logger.error(f"处理交易信号时出错: {str(e)}")
    
    async def _check_position_management(self, market_data: MarketData):
        """检查仓位管理"""
        try:
            position = self.position_manager.get_position(market_data.symbol)
            if not position:
                return
            
            # 检查是否需要强制平仓（止损/止盈）
            if self.risk_manager.should_force_close_position(position, market_data.close):
                await self._close_position(position, market_data.close, "风险管理强制平仓")
            
            # 检查策略是否建议平仓
            elif self.strategy.should_close_position(position, market_data.close):
                await self._close_position(position, market_data.close, "策略建议平仓")
            
        except Exception as e:
            self.logger.error(f"检查仓位管理时出错: {str(e)}")
    
    async def _close_position(self, position, close_price: float, reason: str):
        """平仓"""
        try:
            # 创建平仓信号
            close_signal = Signal(
                symbol=position.symbol,
                action="SELL" if position.side.value == "LONG" else "BUY",
                strength=1.0,
                price=close_price,
                timestamp=datetime.now(),
                reason=reason
            )
            
            # 执行平仓
            result = await self.order_executor.execute_signal(
                close_signal, 
                position.size * close_price, 
                close_price
            )
            
            if result.success:
                # 更新仓位管理器
                closed_position = self.position_manager.close_position(
                    position.symbol, 
                    reason, 
                    close_price
                )
                
                # 记录交易
                if closed_position:
                    self.risk_manager.record_trade({
                        'symbol': closed_position.symbol,
                        'side': closed_position.side.value,
                        'size': closed_position.size,
                        'entry_price': closed_position.entry_price,
                        'exit_price': close_price,
                        'pnl': closed_position.realized_pnl,
                        'reason': reason
                    })
                
                self.logger.info(f"平仓成功: {position.symbol} {reason}")
            else:
                self.logger.error(f"平仓失败: {result.error_message}")
            
        except Exception as e:
            self.logger.error(f"平仓时出错: {str(e)}")
    
    async def _check_force_close_positions(self):
        """检查是否需要强制平仓所有持仓"""
        try:
            # 如果交易被禁用，平掉所有仓位
            if not self.risk_manager.trading_enabled:
                positions = self.position_manager.get_all_positions()
                for position in positions:
                    market_data = await self.exchange.get_market_data(position.symbol)
                    await self._close_position(position, market_data.close, "交易被禁用")
            
        except Exception as e:
            self.logger.error(f"检查强制平仓时出错: {str(e)}")
    
    async def _on_order_filled(self, order, result):
        """订单成交回调"""
        try:
            # 更新仓位管理器
            if order.side.value == "BUY":
                self.position_manager.open_position(
                    order.symbol,
                    "LONG",
                    result.filled_quantity,
                    result.filled_price,
                    order.order_id
                )
            else:
                # 这里需要更复杂的逻辑来处理卖出订单
                pass
            
            self.logger.info(f"订单成交: {order.symbol} {order.side.value} {result.filled_quantity}")
            
        except Exception as e:
            self.logger.error(f"处理订单成交回调时出错: {str(e)}")
    
    async def _on_order_failed(self, order, result):
        """订单失败回调"""
        self.logger.warning(f"订单失败: {order.symbol} {order.side.value} - {result.error_message}")
    
    async def _save_final_state(self):
        """保存最终状态"""
        try:
            # 获取最终统计信息
            risk_metrics = self.risk_manager.get_risk_metrics()
            execution_stats = self.order_executor.get_execution_statistics()
            position_status = self.position_manager.get_status()
            
            final_state = {
                'timestamp': datetime.now().isoformat(),
                'risk_metrics': risk_metrics.__dict__,
                'execution_statistics': execution_stats,
                'position_status': position_status,
                'strategy_status': self.strategy.get_strategy_status()
            }
            
            # 保存到文件
            import json
            state_file = os.path.join(self.config.logging.log_directory, 'final_state.json')
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(final_state, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"最终状态已保存: {state_file}")
            
        except Exception as e:
            self.logger.error(f"保存最终状态时出错: {str(e)}")
    
    def get_system_status(self) -> dict:
        """获取系统状态"""
        return {
            'running': self.running,
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
            'risk_manager_status': self.risk_manager.get_status(),
            'position_manager_status': self.position_manager.get_status(),
            'execution_statistics': self.order_executor.get_execution_statistics(),
            'strategy_status': self.strategy.get_strategy_status()
        }


async def main():
    """主函数"""
    # 设置信号处理
    trading_system: Optional[LiveTradingSystem] = None
    
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在停止交易系统...")
        if trading_system:
            asyncio.create_task(trading_system.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 创建并启动交易系统
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'live_trading_config.json')
        trading_system = LiveTradingSystem(config_path)
        
        print("启动实时交易系统...")
        await trading_system.start()
        
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
    except Exception as e:
        print(f"系统错误: {str(e)}")
    finally:
        if trading_system:
            await trading_system.stop()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())