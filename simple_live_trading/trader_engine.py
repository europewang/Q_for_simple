#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易引擎类 - 独立的开仓和平仓功能模块

功能说明：
- 提供独立的开仓和平仓功能
- 支持模拟交易和真实交易模式
- 可被web_trader.py或其他脚本调用
- 包含完整的风险管理和日志记录

作者: AI Assistant
创建时间: 2025-10-13
"""

import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class TraderEngine:
    """
    交易引擎类
    
    提供独立的开仓和平仓功能，支持：
    - 双向持仓模式
    - 杠杆交易
    - 模拟和真实交易
    - 完整的风险管理
    - 详细的日志记录
    """
    
    def __init__(self, config: Dict = None, logger: logging.Logger = None):
        """
        初始化交易引擎
        
        参数：
        - config: 配置字典，包含API密钥、杠杆等设置
        - logger: 日志记录器，如果不提供则创建新的
        """
        # 默认配置
        self.default_config = {
            "demo_mode": False,
            "api_key": os.getenv("API_KEY"),
            "api_secret": os.getenv("API_SECRET"),
            "leverage": 25,
            "symbol_allocation": {
                "BTCUSDT": 0.4,
                "ETHUSDT": 0.4
            },
            "position_percentage": 0.95
        }
        
        # 合并用户配置
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
        
        # 设置日志
        self.logger = logger if logger else self._setup_logger()
        
        # 初始化币安客户端
        self.client = None
        self._setup_binance_client()
        
        # 持仓记录
        self.positions = {}
        
        # 交易记录
        self.trades = []
        
        # 初始化时同步现有持仓
        self.logger.info("初始化交易引擎，同步现有持仓...")
        self.sync_positions_from_api()
    
    def _setup_logger(self) -> logging.Logger:
        """设置默认日志记录器"""
        logger = logging.getLogger('TraderEngine')
        logger.setLevel(logging.INFO)
        
        # 如果没有处理器，添加控制台处理器
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _setup_binance_client(self):
        """设置币安API客户端"""
        try:
            if not self.config['api_key'] or not self.config['api_secret']:
                raise ValueError("API密钥未配置")
            
            # 创建币安客户端
            self.client = Client(
                self.config['api_key'],
                self.config['api_secret']
            )
            
            # 测试连接
            self.client.ping()
            self.logger.info("✅ 币安API连接成功")
            
            # 设置双向持仓模式
            try:
                self.client.futures_change_position_mode(dualSidePosition=True)
                self.logger.info("✅ 双向持仓模式设置成功")
            except Exception as e:
                self.logger.info(f"ℹ️ 双向持仓模式设置: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ 币安API连接失败: {e}")
            raise
    
    def set_leverage(self, symbol: str, leverage: int = None) -> bool:
        """
        设置交易对杠杆
        
        参数：
        - symbol: 交易对符号
        - leverage: 杠杆倍数，默认使用配置中的值
        
        返回：
        - bool: 设置是否成功
        """
        # 步骤1: 验证参数
        try:
            leverage = leverage or self.config['leverage']
            if not isinstance(leverage, int) or leverage <= 0 or leverage > 125:
                self.logger.error(f"杠杆倍数无效: {symbol}, 杠杆: {leverage}")
                return False
        except Exception as e:
            self.logger.error(f"杠杆参数验证失败: {symbol}, 错误: {e}")
            return False
        
        # 步骤2: 调用币安API设置杠杆
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            self.logger.info(f"✅ {symbol} 杠杆设置为 {leverage}x")
            return True
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 杠杆设置失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return False
        except Exception as e:
            self.logger.error(f"网络异常 - 杠杆设置失败: {symbol}, 错误: {e}")
            return False
    
    def get_current_price(self, symbol: str) -> float:
        """
        获取当前价格
        
        参数：
        - symbol: 交易对符号
        
        返回：
        - float: 当前价格，获取失败返回0
        """
        # 步骤1: 获取价格信息
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            self.logger.info(f"成功获取价格信息: {symbol}")
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取价格失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return 0.0
        except Exception as e:
            self.logger.error(f"网络异常 - 获取价格失败: {symbol}, 错误: {e}")
            return 0.0
        
        # 步骤2: 解析价格数据
        try:
            if not ticker or 'price' not in ticker:
                self.logger.error(f"价格数据格式错误: {symbol}, 返回数据: {ticker}")
                return 0.0
            
            price = float(ticker['price'])
            
            if price <= 0:
                self.logger.error(f"价格数据无效: {symbol}, 价格: {price}")
                return 0.0
            
            self.logger.info(f"价格解析成功: {symbol}, 价格: {price}")
            return price
            
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"价格数据解析失败: {symbol}, 数据: {ticker}, 错误: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"价格处理异常: {symbol}, 错误: {e}")
            return 0.0
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        获取交易对信息
        
        参数：
        - symbol: 交易对符号
        
        返回：
        - Dict: 交易对信息，获取失败返回None
        """
        # 步骤1: 获取交易所信息
        try:
            exchange_info = self.client.futures_exchange_info()
            self.logger.info(f"成功获取交易所信息: {symbol}")
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取交易所信息失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return None
        except Exception as e:
            self.logger.error(f"网络异常 - 获取交易所信息失败: {symbol}, 错误: {e}")
            return None
        
        # 步骤2: 解析交易对信息
        try:
            if not exchange_info or 'symbols' not in exchange_info:
                self.logger.error(f"交易所信息格式错误: {symbol}, 返回数据: {exchange_info}")
                return None
            
            symbols = exchange_info['symbols']
            if not isinstance(symbols, list):
                self.logger.error(f"交易对列表格式错误: {symbol}, 数据类型: {type(symbols)}")
                return None
            
            symbol_info = next((s for s in symbols if s.get('symbol') == symbol), None)
            
            if symbol_info is None:
                self.logger.error(f"未找到交易对信息: {symbol}")
                return None
            
            self.logger.info(f"交易对信息解析成功: {symbol}")
            return symbol_info
            
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"交易对信息解析失败: {symbol}, 数据: {exchange_info}, 错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"交易对信息处理异常: {symbol}, 错误: {e}")
            return None
    
    def calculate_quantity(self, symbol: str, capital: float, price: float) -> Tuple[float, int]:
        """
        计算交易数量和精度
        
        参数：
        - symbol: 交易对符号
        - capital: 可用资金
        - price: 交易价格
        
        返回：
        - Tuple[float, int]: (调整后的数量, 精度位数)
        """
        # 验证输入参数
        try:
            if not isinstance(capital, (int, float)) or capital <= 0:
                raise ValueError(f"无效的资金数量: {capital}")
            if not isinstance(price, (int, float)) or price <= 0:
                raise ValueError(f"无效的价格: {price}")
        except (ValueError, TypeError) as e:
            self.logger.error(f"参数验证失败 - {symbol}: {e}")
            return 0.0, 0
        
        # 获取资金分配比例
        try:
            symbol_allocation = self.config['symbol_allocation'].get(
                symbol, self.config['position_percentage']
            )
        except (KeyError, AttributeError) as e:
            self.logger.error(f"获取资金分配配置失败 - {symbol}: {e}")
            return 0.0, 0
        
        # 计算分配资金和数量
        try:
            position_value = capital * symbol_allocation
            quantity = position_value * self.config['leverage'] / price
        except (TypeError, ZeroDivisionError, KeyError) as e:
            self.logger.error(f"计算交易数量失败 - {symbol}: {e}")
            return 0.0, 0
        
        # 获取精度信息
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            self.logger.error(f"无法获取交易对信息 - {symbol}")
            return 0.0, 0
        
        # 解析数量精度
        try:
            quantity_precision = 0
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'LOT_SIZE':
                    step_size = float(filter_info['stepSize'])
                    quantity_precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0
                    break
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            self.logger.error(f"解析数量精度失败 - {symbol}: {e}")
            return 0.0, 0
        
        # 调整精度
        try:
            quantity = round(quantity, quantity_precision)
        except (ValueError, TypeError) as e:
            self.logger.error(f"调整数量精度失败 - {symbol}: {e}")
            return 0.0, 0
        
        self.logger.info(f"💰 {symbol} 资金分配: {symbol_allocation*100}% = {position_value:.2f} USDT")
        
        return quantity, quantity_precision
    
    def open_position(self, symbol: str, side: str, quantity: float, current_leverage: int) -> Dict:
        """
        开仓操作
        
        参数：
        - symbol: 交易对符号 (如 'ETHUSDT')
        - side: 持仓方向 ('long' 或 'short')
        - quantity: 交易数量
        
        返回：
        - Dict: 交易结果信息
        """
        try:
            # 获取当前价格
            price = self.get_current_price(symbol)
            if price == 0:
                return {"success": False, "error": f"无法获取 {symbol} 当前价格"}
            
            # 计算所需保证金
            notional_value = quantity * price
            required_margin = (notional_value / current_leverage) + (notional_value * 0.001) # 加上0.1%的滑点缓冲
            
            # 获取账户余额并检查资金充足性
            if not self.config['demo_mode']:
                # 步骤1: 获取账户信息
                try:
                    account_info = self.client.futures_account()
                    self.logger.info(f"成功获取账户信息: {symbol}")
                except BinanceAPIException as e:
                    error_msg = f"币安API异常 - 获取账户信息失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"网络异常 - 获取账户信息失败: {symbol}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                
                # 步骤2: 解析账户余额
                try:
                    if not account_info or 'availableBalance' not in account_info:
                        error_msg = f"账户信息格式错误: {symbol}, 返回数据: {account_info}"
                        self.logger.error(error_msg)
                        return {"success": False, "error": error_msg}
                    
                    available_balance = float(account_info['availableBalance'])
                    
                    if available_balance < required_margin:
                        error_msg = f"余额不足: 可用余额 {available_balance:.2f} USDT, 需要保证金 {required_margin:.2f} USDT"
                        self.logger.warning(error_msg)
                        return {"success": False, "error": error_msg}
                    
                    self.logger.info(f"资金检查通过: 可用余额 {available_balance:.2f} USDT, 需要保证金 {required_margin:.2f} USDT")
                    
                except (ValueError, TypeError, KeyError) as e:
                    error_msg = f"账户余额解析失败: {symbol}, 数据: {account_info}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"账户余额处理异常: {symbol}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            
            # 设置杠杆
            self.set_leverage(symbol, current_leverage)
            
            # 获取交易对信息并调整数量精度
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info:
                # 获取数量精度
                quantity_precision = 0
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'LOT_SIZE':
                        step_size = float(filter_info['stepSize'])
                        quantity_precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0
                        break
                
                # 调整数量精度
                quantity = round(quantity, quantity_precision)
            
            # 使用之前计算的保证金
            margin = required_margin
            
            # 执行开仓
            if self.config['demo_mode']:
                # 模拟交易
                self.logger.info(f"🎯 [模拟] {symbol} 开 {side} 仓: 数量={quantity}, 价格={price}, 保证金={margin:.2f} USDT")
                order_id = f"DEMO_{int(time.time())}"
            else:
                # 真实交易 - 步骤1: 创建订单
                try:
                    order = self.client.futures_create_order(
                        symbol=symbol,
                        side='BUY' if side == 'long' else 'SELL',
                        type='MARKET',
                        quantity=quantity,
                        positionSide='LONG' if side == 'long' else 'SHORT'
                    )
                    self.logger.info(f"成功创建订单: {symbol}")
                except BinanceAPIException as e:
                    error_msg = f"币安API异常 - 创建订单失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except BinanceOrderException as e:
                    error_msg = f"币安订单异常 - 创建订单失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"网络异常 - 创建订单失败: {symbol}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                
                # 真实交易 - 步骤2: 解析订单结果
                try:
                    if not order or 'orderId' not in order:
                        error_msg = f"订单结果格式错误: {symbol}, 返回数据: {order}"
                        self.logger.error(error_msg)
                        return {"success": False, "error": error_msg}
                    
                    order_id = order['orderId']
                    
                    # 获取实际成交价格
                    if 'fills' in order and order['fills']:
                        try:
                            price = float(order['fills'][0]['price'])
                        except (ValueError, TypeError, KeyError, IndexError) as e:
                            self.logger.warning(f"无法解析成交价格，使用当前价格: {symbol}, 错误: {e}")
                    
                    self.logger.info(f"🎯 {symbol} 开 {side} 仓成功: 订单ID={order_id}, 数量={quantity}, 价格={price}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    error_msg = f"订单结果解析失败: {symbol}, 数据: {order}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"订单结果处理异常: {symbol}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
            
            # 创建止损订单
            stop_loss_result = self._create_stop_loss_order(symbol, side, quantity, price, margin)
            
            # 记录持仓
            position_info = {
                'side': side,
                'size': quantity,
                'entry_price': price,
                'margin': margin,
                'stop_loss_price': stop_loss_result.get('stop_price', 0),
                'stop_loss_order_id': stop_loss_result.get('order_id', None),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.positions[symbol] = position_info
            
            # 记录交易
            trade_record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'action': f'开{side}仓',
                'quantity': quantity,
                'price': price,
                'order_id': order_id,
                'type': '模拟' if self.config['demo_mode'] else '真实'
            }
            self.trades.append(trade_record)
            
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "margin": margin,
                "position": position_info,
                "stop_loss": stop_loss_result
            }
            
        except Exception as e:
            error_msg = f"开仓失败: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def _create_stop_loss_order(self, symbol: str, side: str, quantity: float, entry_price: float, margin: float) -> Dict:
        """
        创建止损订单
        
        参数：
        - symbol: 交易对符号
        - side: 持仓方向 ('long' 或 'short')
        - quantity: 持仓数量
        - entry_price: 开仓价格
        - margin: 开仓保证金（即开仓资金）
        
        返回：
        - Dict: 止损订单创建结果
        """
        try:
            # 计算止损价格：止损金额 = 开仓资金
            # 多仓止损价 = 开仓价 - (开仓资金/数量)
            # 空仓止损价 = 开仓价 + (开仓资金/数量)
            stop_loss_amount_per_unit = margin / quantity
            
            if side == 'long':
                stop_price = entry_price - stop_loss_amount_per_unit
                order_side = 'SELL'
                position_side = 'LONG'
            else:  # short
                stop_price = entry_price + stop_loss_amount_per_unit
                order_side = 'BUY'
                position_side = 'SHORT'
            
            # 确保止损价格为正数
            if stop_price <= 0:
                self.logger.warning(f"{symbol} 计算的止损价格无效: {stop_price}, 跳过止损订单创建")
                return {"success": False, "error": "止损价格无效"}
            
            # 获取价格精度
            symbol_info = self.get_symbol_info(symbol)
            price_precision = 2  # 默认精度
            if symbol_info:
                for filter_info in symbol_info['filters']:
                    if filter_info['filterType'] == 'PRICE_FILTER':
                        tick_size = float(filter_info['tickSize'])
                        price_precision = len(str(tick_size).split('.')[-1]) if '.' in str(tick_size) else 0
                        break
            
            # 调整止损价格精度
            stop_price = round(stop_price, price_precision)
            
            self.logger.info(f"💡 {symbol} 计算止损价格: {side}仓 @ {entry_price} → 止损 @ {stop_price} (止损金额: {margin:.2f} USDT)")
            
            if self.config['demo_mode']:
                # 模拟模式
                self.logger.info(f"🛡️ [模拟] {symbol} 创建止损订单: {side}仓止损价 {stop_price}")
                return {
                    "success": True,
                    "order_id": f"STOP_DEMO_{int(time.time())}",
                    "stop_price": stop_price,
                    "type": "模拟止损"
                }
            else:
                # 真实交易模式 - 创建止损订单
                try:
                    stop_order = self.client.futures_create_order(
                        symbol=symbol,
                        side=order_side,
                        type='STOP_MARKET',
                        quantity=quantity,
                        stopPrice=stop_price,
                        positionSide=position_side,
                        timeInForce='GTC'
                    )
                    
                    order_id = stop_order.get('orderId', 'UNKNOWN')
                    self.logger.info(f"🛡️ {symbol} 止损订单创建成功: 订单ID={order_id}, 止损价={stop_price}")
                    
                    return {
                        "success": True,
                        "order_id": order_id,
                        "stop_price": stop_price,
                        "type": "真实止损"
                    }
                    
                except BinanceAPIException as e:
                    error_msg = f"币安API异常 - 创建止损订单失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"创建止损订单失败: {symbol}, 错误: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                    
        except Exception as e:
            error_msg = f"止损订单处理异常: {symbol}, 错误: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def close_position(self, symbol: str, quantity: float = None) -> Dict:
        """
        平仓操作
        
        参数：
        - symbol: 交易对符号
        - quantity: 平仓数量（可选，如果不提供则全部平仓）
        
        返回：
        - Dict: 交易结果信息
        """
        try:
            # 检查持仓
            position = self.positions.get(symbol)
            if not position:
                return {"success": False, "error": f"{symbol} 无持仓需要平仓"}
            
            # 确定平仓数量
            if quantity is None:
                quantity = position['size']  # 全部平仓
            else:
                # 检查平仓数量是否超过持仓
                if quantity > position['size']:
                    return {"success": False, "error": f"平仓数量 {quantity} 超过持仓数量 {position['size']}"}
            
            # 获取当前价格
            current_price = self.get_current_price(symbol)
            if current_price == 0:
                return {"success": False, "error": f"无法获取 {symbol} 当前价格"}
            
            # 计算盈亏（基于平仓数量）
            pnl = self.calculate_pnl(position, current_price) * (quantity / position['size'])
            
            # 在平仓前取消相关的委托订单（特别是止损订单）
            if quantity == position['size']:  # 全部平仓时取消所有委托订单
                self.logger.info(f"🔄 {symbol} 全部平仓，取消所有相关委托订单")
                cancel_result = self.cancel_all_orders(symbol)
                if cancel_result['success']:
                    self.logger.info(f"✅ {symbol} 所有委托订单已取消")
                else:
                    self.logger.warning(f"⚠️ {symbol} 取消委托订单失败: {cancel_result.get('error', '未知错误')}")
            else:  # 部分平仓时，如果有止损订单ID，尝试取消止损订单
                stop_loss_order_id = position.get('stop_loss_order_id')
                if stop_loss_order_id and stop_loss_order_id != 'UNKNOWN':
                    self.logger.info(f"🔄 {symbol} 部分平仓，取消止损订单 {stop_loss_order_id}")
                    cancel_result = self.cancel_order(symbol, stop_loss_order_id)
                    if cancel_result['success']:
                        self.logger.info(f"✅ {symbol} 止损订单 {stop_loss_order_id} 已取消")
                    else:
                        self.logger.warning(f"⚠️ {symbol} 取消止损订单失败: {cancel_result.get('error', '未知错误')}")
            
            # 执行平仓
            if self.config['demo_mode']:
                # 模拟交易
                self.logger.info(f"🔄 [模拟] {symbol} 平 {position['side']} 仓: 数量={quantity}, 盈亏={pnl:.2f} USDT")
                order_id = f"DEMO_CLOSE_{int(time.time())}"
            else:
                # 真实交易
                side = 'SELL' if position['side'] == 'long' else 'BUY'
                try:
                    order = self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=quantity,
                        positionSide='LONG' if position['side'] == 'long' else 'SHORT'
                    )
                except BinanceAPIException as e:
                    error_msg = f"币安API平仓订单失败 - 错误代码: {e.code}, 消息: {e.message}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except BinanceOrderException as e:
                    error_msg = f"币安订单异常 - 平仓失败: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"网络或其他错误 - 平仓订单失败: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                
                # 解析订单结果
                try:
                    order_id = order['orderId']
                except (KeyError, TypeError) as e:
                    error_msg = f"解析平仓订单ID失败: {e}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                
                # 获取实际成交价格
                try:
                    if 'fills' in order and order['fills']:
                        current_price = float(order['fills'][0]['price'])
                except (ValueError, TypeError, KeyError, IndexError) as e:
                    self.logger.warning(f"解析平仓成交价格失败，使用当前市价: {e}")
                    # 继续使用之前获取的current_price
                
                self.logger.info(f"🔄 {symbol} 平 {position['side']} 仓成功: 订单ID={order_id}, 数量={quantity}, 价格={current_price}")
            
            # 记录交易
            trade_record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'action': f'平{position["side"]}仓',
                'quantity': quantity,
                'price': current_price,
                'order_id': order_id,
                'pnl': pnl,
                'type': '模拟' if self.config['demo_mode'] else '真实'
            }
            self.trades.append(trade_record)
            
            # 更新或清除持仓记录
            if quantity == position['size']:
                # 全部平仓，清除持仓记录
                closed_position = self.positions.pop(symbol)
            else:
                # 部分平仓，更新持仓数量
                self.positions[symbol]['size'] -= quantity
                closed_position = position.copy()
                closed_position['size'] = quantity
            
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "side": position['side'],
                "quantity": quantity,
                "entry_price": position['entry_price'],
                "price": current_price,
                "pnl": pnl,
                "closed_position": closed_position
            }
            
        except Exception as e:
            error_msg = f"平仓失败: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def calculate_pnl(self, position: Dict, current_price: float) -> float:
        """
        计算持仓盈亏
        
        参数：
        - position: 持仓信息
        - current_price: 当前价格
        
        返回：
        - float: 盈亏金额
        """
        try:
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']
            
            if side == 'long':
                # 多头盈亏 = (当前价格 - 开仓价格) * 数量
                pnl = (current_price - entry_price) * size
            else:
                # 空头盈亏 = (开仓价格 - 当前价格) * 数量
                pnl = (entry_price - current_price) * size
            
            return pnl
            
        except Exception as e:
            self.logger.error(f"计算盈亏失败: {e}")
            return 0.0
    
    def sync_positions_from_api(self) -> bool:
        """
        从币安API同步所有持仓信息到本地
        
        返回：
        - bool: 同步是否成功
        """
        try:
            if self.config['demo_mode']:
                self.logger.info("模拟模式，跳过API持仓同步")
                return True
            
            # 获取所有持仓信息
            positions = self.client.futures_position_information()
            synced_count = 0
            
            for pos in positions:
                symbol = pos['symbol']
                position_amt = float(pos['positionAmt'])
                
                # 只处理有持仓的交易对
                if position_amt != 0:
                    side = 'long' if position_amt > 0 else 'short'
                    entry_price = float(pos['entryPrice'])
                    
                    # 更新本地持仓记录
                    self.positions[symbol] = {
                        'side': side,
                        'size': abs(position_amt),
                        'entry_price': entry_price,
                        'margin': float(pos.get('isolatedMargin', 0)),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'unrealized_pnl': float(pos.get('unRealizedProfit', 0))
                    }
                    synced_count += 1
                    self.logger.info(f"同步持仓: {symbol} {side} {abs(position_amt)} @ {entry_price}")
                else:
                    # 清除本地记录中已平仓的持仓
                    if symbol in self.positions:
                        del self.positions[symbol]
            
            self.logger.info(f"持仓同步完成，共同步 {synced_count} 个持仓")
            return True
            
        except Exception as e:
            self.logger.error(f"同步持仓失败: {e}")
            return False
    
    def get_position_from_api(self, symbol: str) -> Optional[Dict]:
        """
        从币安API获取指定交易对的实时持仓信息
        
        参数：
        - symbol: 交易对符号
        
        返回：
        - Dict: 持仓信息，无持仓返回None
        """
        try:
            if self.config['demo_mode']:
                # 模拟模式返回本地记录
                return self.positions.get(symbol)
            
            # 从API获取持仓信息
            positions = self.client.futures_position_information(symbol=symbol)
            
            for pos in positions:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    side = 'long' if position_amt > 0 else 'short'
                    position_info = {
                        'side': side,
                        'size': abs(position_amt),
                        'entry_price': float(pos['entryPrice']),
                        'margin': float(pos.get('isolatedMargin', 0)),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'unrealized_pnl': float(pos.get('unRealizedProfit', 0))
                    }
                    
                    # 同步到本地记录
                    self.positions[symbol] = position_info
                    return position_info
            
            # 没有持仓，清除本地记录
            if symbol in self.positions:
                del self.positions[symbol]
            return None
            
        except Exception as e:
            self.logger.error(f"从API获取 {symbol} 持仓失败: {e}")
            # 发生错误时返回本地记录
            return self.positions.get(symbol)
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        获取持仓信息（优先从API获取实时数据）
        
        参数：
        - symbol: 交易对符号
        
        返回：
        - Dict: 持仓信息，无持仓返回None
        """
        # 优先从API获取实时持仓信息
        return self.get_position_from_api(symbol)
    
    def get_all_positions(self) -> Dict:
        """
        获取所有持仓信息
        
        返回：
        - Dict: 所有持仓信息
        """
        return self.positions.copy()
    
    def get_trade_history(self) -> list:
        """
        获取交易历史
        
        返回：
        - list: 交易记录列表
        """
        return self.trades.copy()
    
    def clear_positions(self):
        """清空持仓记录（仅用于测试）"""
        self.positions.clear()
        self.logger.info("已清空持仓记录")
    
    def clear_trades(self):
        """清空交易记录（仅用于测试）"""
        self.trades.clear()
        self.logger.info("已清空交易记录")
    
    def get_open_orders(self, symbol: str = None) -> Dict:
        """
        获取账户的未成交委托订单
        
        参数：
        - symbol: 交易对符号（可选，如果不提供则获取所有交易对的订单）
        
        返回：
        - Dict: 包含订单信息的字典
        """
        try:
            if self.config['demo_mode']:
                self.logger.info("🔍 [模拟] 查询委托订单")
                return {"success": True, "orders": [], "message": "模拟模式无委托订单"}
            
            # 真实交易模式 - 查询未成交订单
            if symbol:
                orders = self.client.futures_get_open_orders(symbol=symbol)
                self.logger.info(f"🔍 查询 {symbol} 的委托订单: 找到 {len(orders)} 个订单")
            else:
                orders = self.client.futures_get_open_orders()
                self.logger.info(f"🔍 查询所有委托订单: 找到 {len(orders)} 个订单")
            
            # 格式化订单信息
            formatted_orders = []
            for order in orders:
                formatted_order = {
                    'orderId': order.get('orderId'),
                    'symbol': order.get('symbol'),
                    'side': order.get('side'),
                    'type': order.get('type'),
                    'origQty': order.get('origQty'),
                    'price': order.get('price'),
                    'stopPrice': order.get('stopPrice'),
                    'status': order.get('status'),
                    'positionSide': order.get('positionSide'),
                    'time': order.get('time')
                }
                formatted_orders.append(formatted_order)
                
                # 记录订单详情
                if order.get('type') == 'STOP_MARKET':
                    self.logger.info(f"📋 止损订单: {order.get('symbol')} {order.get('side')} {order.get('origQty')} @ 止损价 {order.get('stopPrice')}")
                else:
                    self.logger.info(f"📋 委托订单: {order.get('symbol')} {order.get('side')} {order.get('origQty')} @ {order.get('price')}")
            
            return {
                "success": True,
                "orders": formatted_orders,
                "count": len(formatted_orders)
            }
            
        except BinanceAPIException as e:
            error_msg = f"币安API异常 - 查询委托订单失败: 错误码: {e.code}, 错误信息: {e.message}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"查询委托订单失败: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        取消指定的委托订单
        
        参数：
        - symbol: 交易对符号
        - order_id: 订单ID
        
        返回：
        - Dict: 取消结果
        """
        try:
            if self.config['demo_mode']:
                self.logger.info(f"❌ [模拟] 取消订单: {symbol} 订单ID {order_id}")
                return {"success": True, "message": "模拟模式订单取消成功"}
            
            # 真实交易模式 - 取消订单
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            
            self.logger.info(f"❌ 订单取消成功: {symbol} 订单ID {order_id}")
            
            return {
                "success": True,
                "orderId": result.get('orderId'),
                "symbol": result.get('symbol'),
                "status": result.get('status')
            }
            
        except BinanceAPIException as e:
            error_msg = f"币安API异常 - 取消订单失败: {symbol} 订单ID {order_id}, 错误码: {e.code}, 错误信息: {e.message}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"取消订单失败: {symbol} 订单ID {order_id}, 错误: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """
        取消指定交易对的所有委托订单
        
        参数：
        - symbol: 交易对符号
        
        返回：
        - Dict: 取消结果
        """
        try:
            if self.config['demo_mode']:
                self.logger.info(f"❌ [模拟] 取消 {symbol} 所有订单")
                return {"success": True, "message": "模拟模式所有订单取消成功"}
            
            # 真实交易模式 - 取消所有订单
            result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            
            self.logger.info(f"❌ {symbol} 所有订单取消成功")
            
            return {
                "success": True,
                "symbol": symbol,
                "message": f"{symbol} 所有委托订单已取消"
            }
            
        except BinanceAPIException as e:
            error_msg = f"币安API异常 - 取消所有订单失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"取消所有订单失败: {symbol}, 错误: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}


# 示例用法
if __name__ == "__main__":
    # 示例用法
    config = {
        "demo_mode": False,  # 真实交易模式
        "leverage": 25
    }
    
    # 创建交易引擎
    trader = TraderEngine(config)
    
    # 开仓示例 - 只需要传入币种、方向、数量
    result = trader.open_position("ETHUSDT", "long", 0.01)  # 开多仓 0.01 ETH
    print("开仓结果:", result)
    
    # 平仓示例 - 只需要传入币种，可选择平仓数量
    if result["success"]:
        close_result = trader.close_position("ETHUSDT")  # 全部平仓
        # 或者部分平仓: close_result = trader.close_position("ETHUSDT", 0.005)
        print("平仓结果:", close_result)
    
    # 查看交易历史
    print("交易历史:", trader.get_trade_history())