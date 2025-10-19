"""
实时交易系统启动脚本
简化的启动接口，支持不同的启动模式
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_trading.main import LiveTradingSystem
from live_trading.config.config_loader import load_live_trading_config


def print_banner():
    """打印启动横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    实时量化交易系统                          ║
    ║                   Live Trading System                        ║
    ║                                                              ║
    ║  版本: 1.0.0                                                 ║
    ║  作者: MyQuant Team                                          ║
    ║  时间: {}                                    ║
    ╚══════════════════════════════════════════════════════════════╝
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print(banner)


def print_config_summary(config):
    """打印配置摘要"""
    print("\n配置摘要:")
    print("=" * 50)
    print(f"交易对: {config.trading.symbol}")
    print(f"模拟模式: {'是' if config.trading.simulation_mode else '否'}")
    print(f"初始余额: {config.trading.initial_balance:.2f} USDT")
    print(f"策略: {config.strategy.name}")
    print(f"快速EMA: {config.strategy.fast_ema_period}")
    print(f"慢速EMA: {config.strategy.slow_ema_period}")
    print(f"最大仓位比例: {config.risk_management.max_position_percentage * 100:.1f}%")
    print(f"止损比例: {config.risk_management.stop_loss_percentage * 100:.1f}%")
    print(f"止盈比例: {config.risk_management.take_profit_percentage * 100:.1f}%")
    print(f"数据源: {config.data_feed.source}")
    print(f"交易所: {config.exchange.name}")
    print("=" * 50)


async def start_trading_system(config_path: str = None, mode: str = "normal"):
    """启动交易系统"""
    try:
        # 加载配置
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'live_trading_config.json')
        
        config = load_live_trading_config(config_path)
        
        # 根据模式调整配置
        if mode == "demo":
            config.trading.simulation_mode = True
            config.data_feed.source = "mock"
            config.exchange.name = "mock"
            print("启动演示模式（模拟交易）")
        elif mode == "test":
            config.trading.simulation_mode = True
            config.exchange.testnet = True
            print("启动测试模式（测试网）")
        elif mode == "live":
            config.trading.simulation_mode = False
            config.exchange.testnet = False
            print("启动实盘模式（真实交易）")
            
            # 实盘模式需要用户确认
            confirm = input("您确定要启动实盘交易吗？这将使用真实资金！(yes/no): ")
            if confirm.lower() != "yes":
                print("已取消启动")
                return
        
        # 打印配置摘要
        print_config_summary(config)
        
        # 创建并启动交易系统
        trading_system = LiveTradingSystem(config_path)
        
        print(f"\n正在启动交易系统...")
        print("按 Ctrl+C 停止交易系统")
        print("-" * 50)
        
        await trading_system.start()
        
    except KeyboardInterrupt:
        print("\n\n用户中断，正在安全停止交易系统...")
    except Exception as e:
        print(f"\n启动失败: {str(e)}")
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="实时量化交易系统")
    parser.add_argument(
        "--config", 
        type=str, 
        help="配置文件路径"
    )
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["demo", "test", "live", "normal"],
        default="normal",
        help="启动模式: demo(演示), test(测试网), live(实盘), normal(按配置文件)"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="仅检查配置文件是否有效"
    )
    
    args = parser.parse_args()
    
    # 打印横幅
    print_banner()
    
    # 如果只是检查配置
    if args.check_config:
        try:
            config_path = args.config or os.path.join(os.path.dirname(__file__), 'config', 'live_trading_config.json')
            config = load_live_trading_config(config_path)
            print("✓ 配置文件有效")
            print_config_summary(config)
        except Exception as e:
            print(f"✗ 配置文件无效: {str(e)}")
            sys.exit(1)
        return
    
    # 启动交易系统
    try:
        asyncio.run(start_trading_system(args.config, args.mode))
    except Exception as e:
        print(f"启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()