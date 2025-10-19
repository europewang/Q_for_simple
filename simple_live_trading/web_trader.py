#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web实时交易监控系统
====================

基于EMA9/EMA26交叉策略的自动化交易系统，提供Web界面实时监控
支持币安期货交易，具备模拟交易和真实交易模式

主要功能：
- EMA9/EMA26交叉信号检测
- 自动开仓/平仓交易执行
- 实时Web监控界面
- WebSocket数据推送
- 风险控制和资金管理
- 详细交易日志记录

作者: AI Assistant
版本: 2.0
更新时间: 2024-10-12
"""

# ============================================================================
# 导入必要的库和模块
# ============================================================================

import os              # 操作系统接口，用于环境变量和文件操作
import time            # 时间相关功能，用于延时等操作
import json            # JSON数据处理
import logging         # 日志记录系统
import threading       # 多线程支持
from datetime import datetime  # 日期时间处理

# 第三方库导入
from flask import Flask, render_template, jsonify  # Flask Web框架
from flask_socketio import SocketIO, emit          # WebSocket支持

# 数据处理库
import pandas as pd    # 数据分析库，用于K线数据处理
import numpy as np     # 数值计算库

# 币安API相关
from dotenv import load_dotenv                                    # 环境变量加载
from binance.client import Client                                 # 币安API客户端
from binance.exceptions import BinanceAPIException, BinanceOrderException  # 币安API异常

# 本地模块导入
from trader_engine import TraderEngine  # 独立的交易引擎类

# ============================================================================
# 环境变量加载
# ============================================================================
# 从.env文件加载API密钥等敏感信息
load_dotenv()

# ============================================================================
# 系统配置参数
# ============================================================================
CONFIG = {
    # 交易模式设置
    "demo_mode": False,  # False=真实交易模式, True=模拟交易模式
    
    # 币安API配置
    "api_key": os.getenv("API_KEY"),        # 币安API密钥
    "api_secret": os.getenv("API_SECRET"),  # 币安API私钥
    
    # 交易对配置
    "symbols": ["ETHUSDT"],  # 只交易ETH
    
    # 技术指标参数
    "timeframe": "30m",    # K线时间周期（30分钟）
    "ema_short": 9,        # 短期EMA周期
    "ema_long": 26,        # 长期EMA周期
    
    # 风险管理参数
    "base_leverage": 25,               # 基础杠杆倍数
    "leverage": 25,                    # 当前杠杆倍数（动态调整）
    "leverage_increment": 2,           # 亏损后杠杆增加量
    "position_percentage": 0.95,       # 默认仓位比例（已弃用，保留兼容性）
    "fixed_trade_amount": 10.0,        # 固定交易金额（USDT）
    
    # 资金分配策略（新版本）
    "symbol_allocation": {
        "ETHUSDT": 0.8     # ETH交易使用80%全仓资金
        # 保留20%作为风险缓冲
    },
    
    # 系统参数
    "initial_capital": 1000,  # 初始资金（用于计算收益率）
    "check_interval": 3       # 数据更新间隔（秒）
}

# ============================================================================
# Flask Web应用初始化
# ============================================================================
# 创建Flask应用实例，用于提供Web界面和API服务
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Flask会话密钥

# 创建SocketIO实例，用于实时数据推送
# cors_allowed_origins="*" 允许所有来源的跨域请求
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================================
# 自定义日志处理器
# ============================================================================

class WebSocketLogHandler(logging.Handler):
    """
    自定义日志处理器，将日志发送到WebSocket
    """
    def __init__(self, trader_instance):
        super().__init__()
        self.trader = trader_instance
    
    def emit(self, record):
        """
        处理日志记录
        """
        try:
            # 格式化日志消息
            message = self.format(record)
            
            # 确定日志级别
            level_mapping = {
                'INFO': 'info',
                'WARNING': 'warning', 
                'ERROR': 'error',
                'CRITICAL': 'error'
            }
            level = level_mapping.get(record.levelname, 'info')
            
            # 添加到日志缓冲区并发送到前端
            if self.trader:
                self.trader.add_log_entry(level, message)
        except Exception:
            # 避免日志处理错误导致系统崩溃
            pass

# ============================================================================
# 主要交易类定义
# ============================================================================
class WebTrader:
    """
    Web实时交易系统核心类
    
    功能说明：
    - 管理币安API连接和账户信息
    - 执行EMA交叉策略的自动交易
    - 提供实时数据获取和处理
    - 管理持仓和交易记录
    - 支持模拟交易和真实交易模式
    """
    
    def __init__(self):
        """
        初始化交易系统
        
        初始化内容：
        - 币安API客户端连接
        - 账户资金和持仓信息同步
        - 日志系统设置
        - 交易状态变量初始化
        """
        # ========== 核心组件初始化 ==========
        self.client = None          # 币安API客户端实例
        self.capital = 0            # 账户总资金（USDT）
        
        # ========== 交易状态管理 ==========
        self.positions = {}         # 当前持仓信息 {symbol: position_info}
        self.trade_count = 0        # 交易次数统计
        self.trades = []            # 交易历史记录列表
        self.running = False        # 系统运行状态标志
        self.trade_records_file = "/home/ubuntu/Code/quant/simple_live_trading/logs/trade_records.txt"  # 交易记录文本文件路径
        
        # ========== 动态杠杆管理 ==========
        self.base_leverage = CONFIG["base_leverage"]        # 基础杠杆倍数
        self.current_leverage = CONFIG["base_leverage"]     # 当前杠杆倍数
        self.leverage_increment = CONFIG["leverage_increment"]  # 杠杆增加量
        self.last_trade_pnl = {}    # 记录每个交易对上次交易的盈亏 {symbol: pnl}
        
        # ========== EMA交叉检测状态 ==========
        self.ema_cross_state = {}   # 记录每个交易对的EMA交叉状态
        self.last_ema_data = {}     # 记录上一次的EMA数据，用于交叉检测
        self.last_kline_close_time = {symbol: None for symbol in CONFIG['symbols']} # 记录每个交易对上次处理的K线收盘时间
        self.last_5min_check_time = {symbol: None for symbol in CONFIG['symbols']} # 记录每个交易对上次执行5分钟EMA打印的时间
        self.last_half_hour_check_time = {symbol: None for symbol in CONFIG['symbols']} # 记录每个交易对上次执行半小时交易检测的时间
        self.last_half_hour_log_time = None # 记录上次半点日志的时间
        
        # ========== 日志收集功能 ==========
        self.log_buffer = []        # 日志缓冲区，存储最近的日志条目
        self.max_log_entries = 100  # 最大日志条目数
        
        # ========== 检测状态持久化 ==========
        self.detection_state_file = "logs/detection_state.json"  # 检测状态持久化文件路径
        
        # ========== 系统初始化流程 ==========
        self.setup_logging()        # 1. 设置日志系统
        self.setup_binance_client() # 2. 初始化币安API连接
        self.sync_account_info()    # 3. 同步账户信息和持仓
        self.setup_trader_engine()  # 4. 初始化交易引擎
        
        # ========== 检测状态恢复 ==========
        self.load_detection_state()           # 5. 加载检测状态
        self.check_missed_detections_on_startup()  # 6. 检查启动时遗漏的检测点
    
    def add_log_entry(self, level: str, message: str):
        """
        添加日志条目到缓冲区并发送到前端
        
        参数：
        - level: 日志级别 (INFO, WARNING, ERROR, SUCCESS)
        - message: 日志消息
        """
        now = datetime.now()
        timestamp = now.isoformat()  # 使用ISO格式，便于前端解析
        timestamp_display = now.strftime('%H:%M:%S')  # 显示用的时间格式
        log_entry = {
            'timestamp': timestamp,
            'timestamp_display': timestamp_display,
            'level': level,
            'message': message
        }
        
        # 添加到缓冲区
        self.log_buffer.append(log_entry)
        
        # 保持缓冲区大小限制
        if len(self.log_buffer) > self.max_log_entries:
            self.log_buffer.pop(0)
        
        # 发送到前端
        try:
            socketio.emit('log_update', log_entry)
        except Exception as e:
            # 避免日志发送错误导致系统崩溃
            pass
        
    def setup_logging(self):
        """
        设置日志系统
        
        功能说明：
        - 创建logs目录（如果不存在）
        - 配置日志格式和输出方式
        - 同时输出到文件和控制台
        - 支持中文字符编码
        """
        # 创建日志目录
        log_dir = "/home/ubuntu/Code/quant/simple_live_trading/logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 配置日志系统
        logging.basicConfig(
            level=logging.INFO,  # 日志级别：INFO及以上
            format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
            handlers=[
                # 文件输出：保存到web_trader.log文件，支持UTF-8编码
                logging.FileHandler(f'{log_dir}/web_trader.log', encoding='utf-8'),
                # 控制台输出：实时显示日志信息
                logging.StreamHandler()
            ]
        )
        # 获取当前模块的日志记录器
        self.logger = logging.getLogger(__name__)
        
        # 添加自定义WebSocket日志处理器
        websocket_handler = WebSocketLogHandler(self)
        websocket_handler.setLevel(logging.INFO)
        websocket_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(websocket_handler)
        
        # 为werkzeug和engineio创建单独的日志文件处理器
        web_access_handler = logging.FileHandler(f'{log_dir}/web_access.log', encoding='utf-8')
        web_access_handler.setLevel(logging.INFO)
        web_access_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 获取werkzeug日志记录器并配置
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.INFO)
        werkzeug_logger.addHandler(web_access_handler)
        werkzeug_logger.propagate = False # 阻止传播到父级logger

        # 获取engineio日志记录器并配置
        engineio_logger = logging.getLogger('engineio')
        engineio_logger.setLevel(logging.INFO)
        engineio_logger.addHandler(web_access_handler)
        engineio_logger.propagate = False # 阻止传播到父级logger

    def setup_binance_client(self):
        """
        设置币安API客户端连接
        
        功能说明：
        - 从环境变量读取API密钥
        - 配置代理设置（如果需要）
        - 建立币安期货API连接
        - 测试连接有效性
        
        异常处理：
        - 连接失败时抛出异常并记录错误日志
        """
        try:
            # 创建币安客户端实例
            self.client = Client(
                CONFIG["api_key"],      # API密钥
                CONFIG["api_secret"],   # API私钥
            )
            
            # 测试API连接是否正常
            self.client.ping()
            self.logger.info("币安API连接成功")
            
            # 设置单向持仓模式（禁用双向持仓）
            try:
                self.client.futures_change_position_mode(dualSidePosition=False)
                self.logger.info("✅ 单向持仓模式设置成功")
            except Exception as e:
                # 如果已经是单向持仓模式，会返回错误，这是正常的
                self.logger.info(f"ℹ️ 单向持仓模式设置: {e}")
            
            # 设置杠杆倍数（使用当前动态杠杆）
            for symbol in CONFIG['symbols']:
                try:
                    self.client.futures_change_leverage(symbol=symbol, leverage=self.current_leverage)
                    self.logger.info(f"✅ {symbol} 杠杆设置为 {self.current_leverage}x（动态杠杆）")
                except Exception as e:
                    self.logger.warning(f"⚠️ {symbol} 杠杆设置失败: {e}")
            
        except Exception as e:
            self.logger.error(f"币安API连接失败: {e}")
            raise  # 重新抛出异常，因为API连接是系统运行的前提
    
    def setup_trader_engine(self):
        """
        设置交易引擎
        
        功能说明：
        - 创建TraderEngine实例
        - 传递配置参数和日志记录器
        - 与WebTrader共享币安客户端连接
        """
        try:
            # 准备交易引擎配置
            trader_config = {
                "demo_mode": CONFIG["demo_mode"],
                "api_key": CONFIG["api_key"],
                "api_secret": CONFIG["api_secret"],
                "leverage": CONFIG["leverage"],
                "symbol_allocation": CONFIG["symbol_allocation"],
                "position_percentage": CONFIG["position_percentage"]
            }
            
            # 创建交易引擎实例
            self.trader_engine = TraderEngine(config=trader_config, logger=self.logger)
            
            self.logger.info("✅ 交易引擎初始化成功")
            
        except Exception as e:
            self.logger.error(f"❌ 交易引擎初始化失败: {e}")
            raise
    
    def save_detection_state(self):
        """
        保存检测状态到文件
        
        功能描述：
        - 将当前的检测时间记录保存到JSON文件
        - 防止程序重启后丢失检测记录
        - 确保检测的连续性
        """
        try:
            # 确保logs目录存在
            os.makedirs(os.path.dirname(self.detection_state_file), exist_ok=True)
            
            # 准备保存的状态数据
            state_data = {
                'last_5min_check_time': {},
                'last_half_hour_check_time': {},
                'last_half_hour_log_time': self.last_half_hour_log_time.isoformat() if self.last_half_hour_log_time else None,
                'save_time': datetime.now().isoformat()
            }
            
            # 转换datetime对象为ISO格式字符串
            for symbol in CONFIG['symbols']:
                state_data['last_5min_check_time'][symbol] = (
                    self.last_5min_check_time[symbol].isoformat() 
                    if self.last_5min_check_time[symbol] else None
                )
                state_data['last_half_hour_check_time'][symbol] = (
                    self.last_half_hour_check_time[symbol].isoformat() 
                    if self.last_half_hour_check_time[symbol] else None
                )
            
            # 保存到文件
            with open(self.detection_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("检测状态已保存")
            
        except Exception as e:
            self.logger.error(f"保存检测状态失败: {str(e)}")
    
    def load_detection_state(self):
        """
        从文件加载检测状态
        
        功能描述：
        - 从JSON文件恢复检测时间记录
        - 在程序重启后保持检测的连续性
        - 如果文件不存在则使用默认值
        """
        try:
            if os.path.exists(self.detection_state_file):
                with open(self.detection_state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                # 恢复检测时间记录
                for symbol in CONFIG['symbols']:
                    # 恢复5分钟检测时间
                    if symbol in state_data.get('last_5min_check_time', {}):
                        time_str = state_data['last_5min_check_time'][symbol]
                        if time_str:
                            self.last_5min_check_time[symbol] = datetime.fromisoformat(time_str)
                    
                    # 恢复半小时检测时间
                    if symbol in state_data.get('last_half_hour_check_time', {}):
                        time_str = state_data['last_half_hour_check_time'][symbol]
                        if time_str:
                            self.last_half_hour_check_time[symbol] = datetime.fromisoformat(time_str)
                
                # 恢复半小时日志时间
                if state_data.get('last_half_hour_log_time'):
                    self.last_half_hour_log_time = datetime.fromisoformat(state_data['last_half_hour_log_time'])
                
                self.logger.info("检测状态已从文件恢复")
                
                # 打印恢复的状态信息
                for symbol in CONFIG['symbols']:
                    last_5min = self.last_5min_check_time[symbol]
                    last_half_hour = self.last_half_hour_check_time[symbol]
                    self.logger.info(f"{symbol} 恢复状态 - 上次5分钟检测: {last_5min.strftime('%H:%M:%S') if last_5min else '无'}, "
                                   f"上次半小时检测: {last_half_hour.strftime('%H:%M:%S') if last_half_hour else '无'}")
            else:
                self.logger.info("检测状态文件不存在，使用默认状态")
                
        except Exception as e:
            self.logger.error(f"加载检测状态失败: {str(e)}")
            # 如果加载失败，使用默认值
            for symbol in CONFIG['symbols']:
                self.last_5min_check_time[symbol] = None
                self.last_half_hour_check_time[symbol] = None
            self.last_half_hour_log_time = None
    
    def check_missed_detections_on_startup(self):
        """
        启动时检查是否有遗漏的检测点
        
        功能描述：
        - 在程序启动时检查是否有遗漏的半小时检测点
        - 如果发现遗漏，立即执行补偿检测
        - 确保交易策略的连续性
        """
        try:
            now = datetime.now()
            current_half_hour = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
            
            self.logger.info("=== 启动时检测遗漏检查 ===")
            self.logger.info(f"当前时间: {now.strftime('%H:%M:%S')}")
            self.logger.info(f"当前半小时点: {current_half_hour.strftime('%H:%M')}")
            
            for symbol in CONFIG['symbols']:
                last_check = self.last_half_hour_check_time[symbol]
                
                if last_check is None:
                    self.logger.info(f"{symbol} 首次启动，无需检查遗漏")
                    continue
                
                # 计算应该检测的半小时点
                next_expected_check = last_check.replace(minute=30 if last_check.minute == 0 else 0, second=0, microsecond=0)
                if next_expected_check.minute == 0:
                    next_expected_check = next_expected_check.replace(hour=next_expected_check.hour + 1)
                
                self.logger.info(f"{symbol} 上次检测: {last_check.strftime('%H:%M')}, "
                               f"下次应检测: {next_expected_check.strftime('%H:%M')}")
                
                # 如果当前时间已经超过了下次应检测的时间，说明有遗漏
                if current_half_hour >= next_expected_check:
                    missed_periods = []
                    check_time = next_expected_check
                    
                    # 找出所有遗漏的半小时点
                    while check_time <= current_half_hour:
                        missed_periods.append(check_time)
                        # 计算下一个半小时点
                        if check_time.minute == 0:
                            check_time = check_time.replace(minute=30)
                        else:
                            check_time = check_time.replace(minute=0, hour=check_time.hour + 1)
                    
                    if missed_periods:
                        self.logger.warning(f"{symbol} 发现 {len(missed_periods)} 个遗漏的半小时检测点:")
                        for missed_time in missed_periods:
                            self.logger.warning(f"  - 遗漏检测点: {missed_time.strftime('%H:%M')}")
                        
                        # 执行补偿检测（只检测最新的遗漏点）
                        self.logger.info(f"{symbol} 执行补偿检测...")
                        self.execute_compensatory_detection(symbol)
                else:
                    self.logger.info(f"{symbol} 无遗漏检测点")
            
            self.logger.info("=== 启动时检测遗漏检查完成 ===")
            
        except Exception as e:
            self.logger.error(f"启动时检测遗漏检查失败: {str(e)}")
    
    def execute_compensatory_detection(self, symbol: str):
        """
        执行补偿检测
        
        功能描述：
        - 在发现遗漏检测点时执行补偿检测
        - 基于当前EMA状态和持仓情况判断是否需要交易
        - 更新检测时间记录
        """
        try:
            self.logger.info(f"=== {symbol} 补偿检测开始 ===")
            
            # 获取K线数据并计算EMA
            df = self.get_kline_data(symbol)
            if df.empty:
                self.logger.warning(f"{symbol} K线数据为空，跳过补偿检测")
                return
            
            df = self.calculate_ema(df)
            
            # 打印当前EMA数值
            ema_short_col = f'ema_{CONFIG["ema_short"]}'
            ema_long_col = f'ema_{CONFIG["ema_long"]}'
            latest_ema_short = df[ema_short_col].iloc[-1]
            latest_ema_long = df[ema_long_col].iloc[-1]
            self.logger.info(f"{symbol} 补偿检测 - EMA{CONFIG['ema_short']}: {latest_ema_short:.2f}, EMA{CONFIG['ema_long']}: {latest_ema_long:.2f}")
            
            # 检测EMA交叉并执行交易逻辑
            cross_result = self.check_ema_cross(symbol)
            if cross_result:
                self.logger.info(f"{symbol} 补偿检测发现交叉信号: {cross_result}")
                
                # 获取当前仓位状态
                current_position = self.trader_engine.get_position(symbol)
                
                # 将交叉信号转换为交易方向
                if cross_result == 'golden_cross':
                    signal_direction = 'long'
                elif cross_result == 'death_cross':
                    signal_direction = 'short'
                else:
                    self.logger.warning(f"{symbol} 未知的交叉信号: {cross_result}")
                    return
                
                # 根据当前仓位状态和信号方向做出交易决策
                if current_position is None:
                    self.logger.info(f"{symbol} 补偿检测决策: 无持仓，开 {signal_direction} 仓")
                    self.execute_trade(symbol, signal_direction)
                elif current_position['side'] == signal_direction:
                    self.logger.info(f"{symbol} 补偿检测决策: 已有 {signal_direction} 持仓，跳过交易")
                else:
                    self.logger.info(f"{symbol} 补偿检测决策: 有 {current_position['side']} 持仓，需平仓后开 {signal_direction} 仓")
                    self.execute_trade(symbol, signal_direction)
            else:
                self.logger.info(f"{symbol} 补偿检测未发现交叉信号")
            
            # 更新检测时间记录
            now = datetime.now()
            current_half_hour = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
            self.last_half_hour_check_time[symbol] = current_half_hour
            
            # 保存检测状态
            self.save_detection_state()
            
            self.logger.info(f"=== {symbol} 补偿检测完成 ===")
            
        except Exception as e:
            self.logger.error(f"{symbol} 补偿检测失败: {str(e)}")
            
    def sync_account_info(self):
        """
        同步账户信息和持仓状态
        
        功能说明：
        - 获取账户总资金、可用余额、未实现盈亏
        - 同步所有配置交易对的持仓信息
        - 计算持仓保证金占用
        - 更新内部状态变量
        
        数据来源：
        - futures_account(): 账户资金信息
        - futures_position_information(): 持仓详情
        """
        # 步骤1: 获取期货账户信息
        try:
            account_info = self.client.futures_account()
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取账户信息失败, 错误码: {e.code}, 错误信息: {e.message}")
            return
        except Exception as e:
            self.logger.error(f"网络异常 - 获取账户信息失败: {e}")
            return
        
        # 步骤2: 解析账户资金信息
        try:
            if not account_info:
                self.logger.error("账户信息为空")
                return
            
            # 验证必要字段
            required_fields = ['totalWalletBalance', 'availableBalance', 'totalUnrealizedProfit']
            for field in required_fields:
                if field not in account_info:
                    self.logger.error(f"账户信息缺少必要字段: {field}")
                    return
            
            # 更新账户资金信息
            self.capital = float(account_info['totalWalletBalance'])  # 总钱包余额
            
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"账户资金信息解析失败: {e}, 数据: {account_info}")
            return
        except Exception as e:
            self.logger.error(f"账户资金信息处理异常: {e}")
            return
        
        # 步骤3: 获取持仓信息
        try:
            positions = self.client.futures_position_information()
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取持仓信息失败, 错误码: {e.code}, 错误信息: {e.message}")
            return
        except Exception as e:
            self.logger.error(f"网络异常 - 获取持仓信息失败: {e}")
            return
        
        # 步骤4: 解析持仓信息
        try:
            if not positions:
                self.logger.warning("持仓信息为空")
                return
            
            for pos in positions:
                try:
                    symbol = pos['symbol']
                    # 只处理配置中的交易对
                    if symbol in CONFIG['symbols']:
                        # 验证持仓数据字段
                        required_pos_fields = ['positionAmt', 'entryPrice']
                        for field in required_pos_fields:
                            if field not in pos:
                                self.logger.error(f"持仓信息缺少必要字段: {field}, 交易对: {symbol}")
                                continue
                        
                        position_amt = float(pos['positionAmt'])
                        
                        if position_amt != 0:  # 有持仓
                            # 判断持仓方向：正数为多头，负数为空头
                            side = 'long' if position_amt > 0 else 'short'
                            entry_price = float(pos['entryPrice'])
                            position_size = abs(position_amt)
                            
                            # 计算保证金占用 = 持仓价值 / 杠杆倍数
                            margin = position_size * entry_price / CONFIG['leverage']
                            
                            # 更新持仓信息
                            self.positions[symbol] = {
                                'side': side,                    # 持仓方向
                                'size': position_size,           # 持仓数量（绝对值）
                                'entry_price': entry_price,      # 开仓价格
                                'margin': margin                 # 保证金占用
                            }
                        else:
                            # 无持仓
                            self.positions[symbol] = None
                            
                except (ValueError, TypeError, KeyError) as e:
                    self.logger.error(f"持仓数据解析失败: {symbol}, 错误: {e}, 数据: {pos}")
                    continue
                except Exception as e:
                    self.logger.error(f"持仓数据处理异常: {symbol}, 错误: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"持仓信息处理异常: {e}")
            
    def adjust_leverage_based_on_pnl(self, symbol: str, pnl: float):
        """
        根据盈亏调整杠杆倍数
        
        参数说明：
        - symbol: 交易对符号
        - pnl: 本次交易的盈亏金额
        
        调整规则：
        - 如果盈利（pnl > 0），杠杆回归基础杠杆（25x）
        - 如果亏损（pnl <= 0），杠杆增加2倍
        """
        # 从API获取当前交易对的实际杠杆
        try:
            position_info = self.client.futures_position_information(symbol=symbol)
            # position_info 是一个列表，需要找到对应symbol的杠杆
            current_api_leverage = None
            for p in position_info:
                if p['symbol'] == symbol:
                    current_api_leverage = int(p['leverage'])
                    break
            
            if current_api_leverage is not None:
                old_leverage = current_api_leverage
                self.current_leverage = current_api_leverage
            else:
                self.logger.warning(f"⚠️ 未能从API获取 {symbol} 的实际杠杆，使用内部记录值 {self.current_leverage}x")
                old_leverage = self.current_leverage
        except Exception as e:
            self.logger.error(f"❌ 获取 {symbol} 实际杠杆失败: {e}，使用内部记录值 {self.current_leverage}x")
            old_leverage = self.current_leverage
        
        if pnl > 0:
            # 盈利：杠杆回归基础杠杆
            self.current_leverage = self.base_leverage
            self.logger.info(f"📈 {symbol} 本次交易盈利 {pnl:.2f} USDT，杠杆回归基础值 {self.base_leverage}x")
        else:
            # 亏损：杠杆增加
            self.current_leverage = min(self.current_leverage + self.leverage_increment, 125)
            self.logger.info(f"📉 {symbol} 本次交易亏损 {pnl:.2f} USDT，杠杆增加到 {self.current_leverage}x")
        
        # 记录杠杆变化
        if old_leverage != self.current_leverage:
            self.logger.info(f"🔄 {symbol} 杠杆调整: {old_leverage}x → {self.current_leverage}x")
            
            # 更新币安API的杠杆设置
            try:
                self.client.futures_change_leverage(symbol=symbol, leverage=self.current_leverage)
                self.logger.info(f"✅ {symbol} 币安杠杆已更新为 {self.current_leverage}x")
            except Exception as e:
                self.logger.error(f"❌ {symbol} 更新币安杠杆失败: {e}，内部杠杆已回滚到 {self.current_leverage}x")
        
        # 记录本次交易的盈亏
        self.last_trade_pnl[symbol] = pnl
    
    def write_trade_record(self, symbol: str, action: str, direction: str, price: float, quantity: float, pnl: float = None):
        """
        写入交易记录到文本文件
        
        参数说明：
        - symbol: 交易对符号
        - action: 操作类型（'开仓' 或 '平仓'）
        - direction: 交易方向（'多头' 或 '空头'）
        - price: 交易价格
        - quantity: 交易数量
        - pnl: 盈亏金额（仅平仓时有效）
        
        功能描述：
        - 格式化交易记录信息
        - 追加写入到交易记录文本文件
        - 包含时间、价格、数量、盈亏等详细信息
        """
        try:
            # 获取当前时间
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 格式化交易记录
            if action == '开仓':
                # 开仓记录格式
                record = f"[{timestamp}] {action} | {symbol} | {direction} | {price:,.2f} | {quantity:.4f} | - | EMA交叉信号\n"
            else:
                # 平仓记录格式，包含盈亏信息
                pnl_str = f"{pnl:+.2f} USDT" if pnl is not None else "0.00 USDT"
                record = f"[{timestamp}] {action} | {symbol} | {direction} | {price:,.2f} | {quantity:.4f} | {pnl_str} | EMA交叉信号\n"
            
            # 追加写入到文件
            with open(self.trade_records_file, 'a', encoding='utf-8') as f:
                f.write(record)
                
            self.logger.info(f"交易记录已写入文件: {action} {symbol} {direction}")
            
        except Exception as e:
            self.logger.error(f"写入交易记录失败: {e}")
            
    def get_kline_data(self, symbol: str, interval: str = "30m", limit: int = 100) -> pd.DataFrame:
        """
        获取指定交易对的K线数据
        
        参数说明：
        - symbol: 交易对符号（如 'BTCUSDT'）
        - interval: K线时间间隔（默认30分钟）
        - limit: 获取的K线数量（默认100根）
        
        返回值：
        - pandas.DataFrame: 包含OHLCV数据的DataFrame
        
        数据列说明：
        - timestamp: 时间戳
        - open/high/low/close: 开高低收价格
        - volume: 成交量
        """
        # 步骤1: 调用币安API获取期货K线数据
        try:
            klines = self.client.futures_klines(
                symbol=symbol,      # 交易对
                interval=interval,  # 时间间隔
                limit=limit        # 数据条数
            )
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取K线数据失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"网络异常 - 获取K线数据失败: {symbol}, 错误: {e}")
            return pd.DataFrame()
        
        # 步骤2: 验证返回的数据
        try:
            if not klines or len(klines) == 0:
                self.logger.warning(f"获取到空的K线数据: {symbol}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"K线数据验证失败: {symbol}, 错误: {e}")
            return pd.DataFrame()
        
        # 步骤3: 将API返回的数据转换为DataFrame格式
        try:
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
        except Exception as e:
            self.logger.error(f"DataFrame创建失败: {symbol}, K线数据: {klines}, 错误: {e}")
            return pd.DataFrame()
        
        # 步骤4: 数据类型转换：将字符串转换为数值类型
        try:
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"数值类型转换失败: {symbol}, 列: {col if 'col' in locals() else 'unknown'}, 错误: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"数值类型转换异常: {symbol}, 错误: {e}")
            return pd.DataFrame()
        
        # 步骤5: 时间戳转换：毫秒时间戳转换为datetime格式
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"时间戳转换失败: {symbol}, 错误: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"时间戳转换异常: {symbol}, 错误: {e}")
            return pd.DataFrame()
        
        # 步骤6: 最终验证和返回
        try:
            if df.empty:
                self.logger.warning(f"处理后的DataFrame为空: {symbol}")
                return pd.DataFrame()
            
            # self.logger.info(f"成功获取 {symbol} K线数据，数量: {len(df)}")
            return df
            
        except Exception as e:
            self.logger.error(f"最终验证失败: {symbol}, 错误: {e}")
            return pd.DataFrame()
            
    def calculate_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算指数移动平均线（EMA）指标
        
        参数说明：
        - df: 包含价格数据的DataFrame
        
        返回值：
        - pandas.DataFrame: 添加了EMA列的DataFrame
        
        计算内容：
        - EMA9: 9周期指数移动平均线（短期）
        - EMA26: 26周期指数移动平均线（长期）
        
        EMA计算公式：
        - EMA = (当前价格 × 平滑系数) + (前一日EMA × (1-平滑系数))
        - 平滑系数 = 2 / (周期数 + 1)
        """
        # 创建数据副本，避免修改原始数据
        df = df.copy()
        
        # 如果有timestamp列，设置为索引（便于时间序列分析）
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
        
        # 计算短期和长期EMA
        # ewm(span=n)：指数加权移动窗口，span参数指定周期数
        df[f'ema_{CONFIG["ema_short"]}' ] = df['close'].ewm(span=CONFIG["ema_short"]).mean()
        df[f'ema_{CONFIG["ema_long"]}' ] = df['close'].ewm(span=CONFIG["ema_long"]).mean()
        
        return df
        
    def get_ema_status(self, symbol: str):
        """
        获取EMA交叉状态和当前值
        
        参数说明：
        - symbol: 交易对符号
        
        返回值：
        - tuple: (状态描述, 短期EMA值, 长期EMA值)
        
        状态类型：
        - 🟢 金叉 (刚发生): 短期EMA刚从下方穿越长期EMA
        - 🟢 多头排列: 短期EMA在长期EMA上方
        - 🔴 死叉 (刚发生): 短期EMA刚从上方穿越长期EMA
        - 🔴 空头排列: 短期EMA在长期EMA下方
        - ❌ 获取失败: 数据获取或计算失败
        """
        try:
            # 获取K线数据
            df = self.get_kline_data(symbol)
            if df.empty:
                return "❌ 获取失败", 0, 0
                
            # 计算EMA指标
            df = self.calculate_ema(df)
            
            # 获取最新的EMA值（最后一根K线）
            latest_short_ema = df[f'ema_{CONFIG["ema_short"]}' ].iloc[-1]
            latest_long_ema = df[f'ema_{CONFIG["ema_long"]}' ].iloc[-1]
            
            # 获取前一根K线的EMA值（用于判断交叉）
            prev_short_ema = df[f'ema_{CONFIG["ema_short"]}' ].iloc[-2]
            prev_long_ema = df[f'ema_{CONFIG["ema_long"]}' ].iloc[-2]
            
            # 判断EMA交叉状态
            # 通过比较当前和前一周期的EMA位置关系来判断交叉
            if latest_short_ema > latest_long_ema:
                # 当前短期EMA在长期EMA上方
                if prev_short_ema <= prev_long_ema:
                    # 前一周期短期EMA在长期EMA下方或相等 → 发生金叉
                    status = "🟢 金叉 (刚发生)"
                else:
                    # 前一周期短期EMA也在长期EMA上方 → 持续多头排列
                    status = "🟢 多头排列"
            else:
                # 当前短期EMA在长期EMA下方
                if prev_short_ema >= prev_long_ema:
                    # 前一周期短期EMA在长期EMA上方或相等 → 发生死叉
                    status = "🔴 死叉 (刚发生)"
                else:
                    # 前一周期短期EMA也在长期EMA下方 → 持续空头排列
                    status = "🔴 空头排列"
                    
            return status, latest_short_ema, latest_long_ema
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} EMA状态失败: {e}")
            return "❌ 获取失败", 0, 0
            
    def get_current_price(self, symbol: str):
        """
        获取指定交易对的当前市场价格
        
        参数说明：
        - symbol: 交易对符号
        
        返回值：
        - float: 当前价格，获取失败时返回0
        
        数据来源：
        - futures_symbol_ticker(): 币安期货价格行情接口
        """
        # 步骤1: 获取期货交易对的实时价格信息
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取价格失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return 0
        except Exception as e:
            self.logger.error(f"网络异常 - 获取价格失败: {symbol}, 错误: {e}")
            return 0
        
        # 步骤2: 解析价格数据
        try:
            if not ticker or 'price' not in ticker:
                self.logger.error(f"价格数据格式错误: {symbol}, 返回数据: {ticker}")
                return 0
            
            price = float(ticker['price'])
            
            if price <= 0:
                self.logger.error(f"价格数据无效: {symbol}, 价格: {price}")
                return 0
            
            return price
            
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"价格数据解析失败: {symbol}, 数据: {ticker}, 错误: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"价格处理异常: {symbol}, 错误: {e}")
            return 0
            
    def calculate_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        """
        计算指定持仓的未实现盈亏
        
        参数说明：
        - symbol: 交易对符号
        - current_price: 当前市场价格
        
        返回值：
        - float: 未实现盈亏金额（USDT）
        
        计算公式：
        - 多头持仓: (当前价格 - 开仓价格) × 持仓数量
        - 空头持仓: (开仓价格 - 当前价格) × 持仓数量
        """
        # 获取持仓信息
        position = self.positions.get(symbol)
        if not position:
            return 0  # 无持仓时盈亏为0
            
        # 根据持仓方向计算盈亏
        if position['side'] == 'long':
            # 多头持仓：价格上涨盈利，价格下跌亏损
            pnl = (current_price - position['entry_price']) * position['size']
        else:
            # 空头持仓：价格下跌盈利，价格上涨亏损
            pnl = (position['entry_price'] - current_price) * position['size']
            
        return pnl
    
    def check_ema_cross(self, symbol: str):
        """
        检测EMA信号与持仓方向是否匹配（重新设计版本）
        
        参数说明：
        - symbol: 交易对符号
        
        返回值：
        - str: 交易信号类型 ('golden_cross', 'death_cross', None)
        
        功能描述：
        - 获取当前EMA信号状态（多头/空头）
        - 获取当前持仓方向
        - 判断EMA信号与持仓是否匹配
        - 如果不匹配则返回需要的交易信号
        
        交易逻辑：
        - 当前EMA多头信号 + 无持仓/空头持仓 → 返回金叉信号（做多）
        - 当前EMA空头信号 + 无持仓/多头持仓 → 返回死叉信号（做空）
        - EMA信号与持仓方向一致 → 返回None（无需交易）
        
        优势：
        - 避免因半小时检测遗漏而错过交易机会
        - 基于当前状态而非历史变化进行判断
        - 确保持仓方向始终与EMA信号一致
        """
        try:
            # 获取当前EMA状态
            df = self.get_kline_data(symbol)
            if df.empty:
                self.logger.warning(f"{symbol} K线数据为空，跳过EMA信号检测")
                return None
                
            # 计算EMA指标
            df = self.calculate_ema(df)
            
            # 获取最新的EMA值
            latest_ema_short = df[f'ema_{CONFIG["ema_short"]}'].iloc[-1]
            latest_ema_long = df[f'ema_{CONFIG["ema_long"]}'].iloc[-1]
            
            # 判断当前EMA信号状态
            current_ema_signal = "bullish" if latest_ema_short > latest_ema_long else "bearish"
            
            # 获取当前持仓状态
            current_position = self.trader_engine.get_position(symbol)
            current_position_side = None
            if current_position and current_position['size'] != 0:
                current_position_side = current_position['side']
            
            # 记录当前状态
            self.logger.info(f"=== {symbol} EMA信号与持仓匹配检测 ===")
            self.logger.info(f"当前EMA{CONFIG['ema_short']}: {latest_ema_short:.2f}, EMA{CONFIG['ema_long']}: {latest_ema_long:.2f}")
            self.logger.info(f"当前EMA信号: {'🟢 多头' if current_ema_signal == 'bullish' else '🔴 空头'}")
            self.logger.info(f"当前持仓: {current_position_side if current_position_side else '无持仓'}")
            
            # 判断是否需要交易
            if current_ema_signal == "bullish":
                # EMA多头信号
                if current_position_side != "long":
                    # 当前无多头持仓，需要做多
                    if current_position_side == "short":
                        self.logger.info(f"🔄 {symbol} EMA多头信号，当前持空仓，需要平空开多")
                    else:
                        self.logger.info(f"🟢 {symbol} EMA多头信号，当前无持仓，需要开多")
                    return 'golden_cross'
                else:
                    # 当前已是多头持仓，信号匹配
                    self.logger.info(f"✅ {symbol} EMA多头信号与当前多头持仓匹配，无需交易")
                    return None
                    
            else:  # current_ema_signal == "bearish"
                # EMA空头信号
                if current_position_side != "short":
                    # 当前无空头持仓，需要做空
                    if current_position_side == "long":
                        self.logger.info(f"🔄 {symbol} EMA空头信号，当前持多仓，需要平多开空")
                    else:
                        self.logger.info(f"🔴 {symbol} EMA空头信号，当前无持仓，需要开空")
                    return 'death_cross'
                else:
                    # 当前已是空头持仓，信号匹配
                    self.logger.info(f"✅ {symbol} EMA空头信号与当前空头持仓匹配，无需交易")
                    return None
                
        except Exception as e:
            self.logger.error(f"检测 {symbol} EMA信号与持仓匹配失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    def execute_trade(self, symbol: str, direction: str):
        """
        执行交易操作的主控制方法（单向持仓模式）
        
        参数说明：
        - symbol: 交易对符号
        - direction: 交易方向 ('long' 或 'short')
        
        功能描述：
        - 检查当前持仓状态
        - 强制单向持仓：任何新开仓前都先平掉现有仓位
        - 使用TraderEngine执行开仓操作
        
        交易逻辑（单向持仓模式）：
        1. 获取当前价格和持仓信息
        2. 如果已有相同方向持仓，跳过交易
        3. 如果有任何持仓（无论方向），先强制平仓
        4. 开新仓位
        """
        self.logger.info(f"=== {symbol} 开始执行交易 ===")
        self.logger.info(f"目标方向: {direction}")
        
        # 获取当前持仓信息（从交易引擎获取）
        try:
            current_position = self.trader_engine.get_position(symbol)
        except Exception as e:
            self.logger.error(f"获取 {symbol} 持仓信息失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return

        
        # 详细记录当前仓位状态
        if current_position:
            self.logger.info(f"{symbol} 当前持仓详情:")
            self.logger.info(f"  - 方向: {current_position['side']}")
            self.logger.info(f"  - 数量: {current_position['size']}")
            self.logger.info(f"  - 入场价: {current_position.get('entry_price', 'N/A')}")
        else:
            self.logger.info(f"{symbol} 当前无持仓")
        
        # 检查是否已有相同方向的持仓
        # 避免重复开仓
        if current_position and current_position['side'] == direction:
            self.logger.info(f"=== {symbol} 交易决策: 跳过 ===")
            self.logger.info(f"原因: 已有 {direction} 方向持仓，避免重复开仓")
            return
        
        # 单向持仓模式：如果有任何持仓，都必须先完全平仓
        if current_position:
            self.logger.info(f"=== {symbol} 交易决策: 先完全平仓后开仓 ===")
            self.logger.info(f"原因: 单向持仓模式，需先完全平掉现有 {current_position['side']} 持仓")
            self.logger.info(f"操作: 完全平 {current_position['side']} 仓 → 同步状态 → 开 {direction} 仓")
            
            # 执行平仓
            try:
                self.close_position(symbol)
                self.logger.info(f"{symbol} 平仓指令已发送，快速验证平仓状态...")
            except Exception as e:
                self.logger.error(f"执行 {symbol} 平仓失败: {e}")
                import traceback
                self.logger.error(f"错误详情: {traceback.format_exc()}")
                return
            
            # 快速验证平仓是否完全成功
            max_retries = 3
            for retry in range(max_retries):
                time.sleep(1)  # 短暂等待1秒
                
                # 重新同步持仓信息
                try:
                    self.sync_account_info()
                    self.trader_engine.sync_positions_from_api()
                except Exception as e:
                    self.logger.error(f"同步 {symbol} 持仓信息失败: {e}")
                    continue
                
                # 检查持仓状态
                try:
                    updated_position = self.trader_engine.get_position(symbol)
                    if not updated_position:
                        self.logger.info(f"{symbol} 平仓验证成功，立即开新仓")
                        break
                    else:
                        self.logger.warning(f"{symbol} 第{retry+1}次验证发现剩余持仓: {updated_position}")
                        if retry == max_retries - 1:
                            self.logger.warning(f"{symbol} 验证发现剩余持仓，继续尝试平仓...")
                            # 继续尝试平仓剩余持仓
                            try:
                                self.close_position(symbol)
                            except Exception as e:
                                self.logger.error(f"重试平仓 {symbol} 失败: {e}")
                        else:
                            # 如果不是最后一次重试，继续尝试平仓
                            self.logger.info(f"{symbol} 继续尝试平仓剩余持仓...")
                            try:
                                self.close_position(symbol)
                            except Exception as e:
                                self.logger.error(f"重试平仓 {symbol} 失败: {e}")
                except Exception as e:
                    self.logger.error(f"检查 {symbol} 持仓状态失败: {e}")
                    continue
        
        # 开仓前最终状态同步和验证
        self.logger.info(f"=== {symbol} 开仓前最终状态同步 ===")
        
        # 同步账户信息和持仓状态
        try:
            self.sync_account_info()
            self.trader_engine.sync_positions_from_api()
        except Exception as e:
            self.logger.error(f"同步 {symbol} 账户信息失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return
        
        # 获取当前资金状态
        try:
            account_info = self.client.futures_account()
            available_balance = float(account_info['availableBalance'])
            total_balance = float(account_info['totalWalletBalance'])
            self.logger.info(f"{symbol} 当前资金状态:")
            self.logger.info(f"  - 可用余额: {available_balance:.4f} USDT")
            self.logger.info(f"  - 总余额: {total_balance:.4f} USDT")
        except Exception as e:
            self.logger.error(f"{symbol} 获取资金状态失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return
        
        # 最终确认无持仓
        try:
            final_position = self.trader_engine.get_position(symbol)
            if final_position:
                self.logger.error(f"{symbol} 开仓前发现仍有持仓，取消开仓操作: {final_position}")
                return
        except Exception as e:
            self.logger.error(f"最终确认 {symbol} 持仓状态失败: {e}")
            return
        
        self.logger.info(f"{symbol} 开仓前状态验证通过，无持仓，资金充足")
        
        # 开新仓位
        self.logger.info(f"=== {symbol} 开始开 {direction} 仓 ===")
        
        # 获取当前市场价格
        try:
            current_price = self.get_current_price(symbol)
            # 价格获取失败检查
            if current_price == 0:
                self.logger.error(f"无法获取 {symbol} 当前价格，跳过交易")
                return
            self.logger.info(f"{symbol} 当前价格: {current_price}")
        except Exception as e:
            self.logger.error(f"获取 {symbol} 当前价格失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return
        
        # 首次开仓尝试
        try:
            self.open_position(symbol, direction, current_price)
        except Exception as e:
            self.logger.error(f"执行 {symbol} 开仓失败: {e}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return
        
        # 开仓后验证
        time.sleep(1)
        try:
            self.sync_account_info()
            self.trader_engine.sync_positions_from_api()
            new_position = self.trader_engine.get_position(symbol)
        except Exception as e:
            self.logger.error(f"开仓后同步 {symbol} 信息失败: {e}")
            return
        
        if new_position:
            self.logger.info(f"{symbol} 开仓成功验证:")
            self.logger.info(f"  - 方向: {new_position['side']}")
            self.logger.info(f"  - 数量: {new_position['size']}")
            self.logger.info(f"  - 入场价: {new_position.get('entry_price', 'N/A')}")
        else:
            # 开仓失败，进行重试
            self.logger.warning(f"{symbol} 首次开仓后未检测到新持仓，开始重试...")
            max_retries = 2  # 额外重试2次
            
            for retry in range(max_retries):
                self.logger.info(f"{symbol} 第{retry+2}次开仓尝试...")
                time.sleep(1)  # 短暂等待后重试
                
                try:
                    self.open_position(symbol, direction, current_price)
                except Exception as e:
                    self.logger.error(f"第{retry+2}次开仓 {symbol} 失败: {e}")
                    continue
                
                # 重试后验证
                time.sleep(1)
                try:
                    self.sync_account_info()
                    self.trader_engine.sync_positions_from_api()
                    new_position = self.trader_engine.get_position(symbol)
                except Exception as e:
                    self.logger.error(f"重试后同步 {symbol} 信息失败: {e}")
                    continue
                
                if new_position:
                    self.logger.info(f"{symbol} 重试开仓成功验证:")
                    self.logger.info(f"  - 方向: {new_position['side']}")
                    self.logger.info(f"  - 数量: {new_position['size']}")
                    self.logger.info(f"  - 入场价: {new_position.get('entry_price', 'N/A')}")
                    break
                else:
                    self.logger.warning(f"{symbol} 第{retry+2}次开仓仍未成功")
                    if retry == max_retries - 1:
                        self.logger.error(f"{symbol} 经过3次尝试仍未成功开仓，请检查账户状态和网络连接")
        
        self.logger.info(f"=== {symbol} 交易执行完成 ===")
    
    def calculate_trade_quantity(self, symbol: str, price: float) -> float:
        """
        计算交易数量（基于固定交易金额）
        
        参数说明：
        - symbol: 交易对符号
        - price: 当前价格
        
        返回：
        - float: 计算出的交易数量
        """
        # 步骤1: 获取实时账户余额
        try:
            account_info = self.client.futures_account()
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取账户信息失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return 0.0
        except Exception as e:
            self.logger.error(f"网络异常 - 获取账户信息失败: {symbol}, 错误: {e}")
            return 0.0
        
        # 步骤2: 解析可用余额
        try:
            available_balance = float(account_info['availableBalance'])
        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"解析可用余额失败: {symbol}, 账户信息: {account_info}, 错误: {e}")
            return 0.0
        
        # 步骤3: 更新资金数据
        try:
            self.capital = available_balance
        except Exception as e:
            self.logger.error(f"更新资金数据失败: {symbol}, 错误: {e}")
            return 0.0
        
        # 步骤4: 获取固定交易金额
        try:
            fixed_amount = CONFIG['fixed_trade_amount']
        except (KeyError, TypeError) as e:
            self.logger.error(f"获取固定交易金额失败: {symbol}, 配置: {CONFIG}, 错误: {e}")
            return 0.0
        
        # 步骤5: 计算所需保证金
        try:
            required_margin = fixed_amount / self.current_leverage
        except (ZeroDivisionError, TypeError, ValueError) as e:
            self.logger.error(f"计算保证金失败: {symbol}, 杠杆: {self.current_leverage}, 错误: {e}")
            return 0.0
        
        # 步骤6: 检查余额是否足够
        try:
            if available_balance < required_margin:
                self.logger.warning(f"余额不足: {symbol}, 可用余额: {available_balance:.2f} USDT, 需要保证金: {required_margin:.2f} USDT")
                return 0.0
        except (TypeError, ValueError) as e:
            self.logger.error(f"余额检查失败: {symbol}, 错误: {e}")
            return 0.0
        
        # 步骤7: 计算数量（基于固定金额和杠杆）
        try:
            if price <= 0:
                self.logger.error(f"价格无效: {symbol}, 价格: {price}")
                return 0.0
            quantity = fixed_amount * self.current_leverage / price
        except (ZeroDivisionError, TypeError, ValueError) as e:
            self.logger.error(f"计算数量失败: {symbol}, 价格: {price}, 错误: {e}")
            return 0.0
        
        # 步骤8: 获取交易对精度信息
        try:
            exchange_info = self.client.futures_exchange_info()
        except BinanceAPIException as e:
            self.logger.error(f"币安API异常 - 获取交易所信息失败: {symbol}, 错误码: {e.code}, 错误信息: {e.message}")
            return 0.0
        except Exception as e:
            self.logger.error(f"网络异常 - 获取交易所信息失败: {symbol}, 错误: {e}")
            return 0.0
        
        # 步骤9: 解析精度信息并调整数量
        try:
            precision = 3  # 默认精度
            symbol_found = False
            
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    symbol_found = True
                    for filter_info in symbol_info['filters']:
                        if filter_info['filterType'] == 'LOT_SIZE':
                            step_size = float(filter_info['stepSize'])
                            # 根据stepSize调整精度
                            if step_size == 1.0:
                                precision = 0
                            elif step_size == 0.1:
                                precision = 1
                            elif step_size == 0.01:
                                precision = 2
                            elif step_size == 0.001:
                                precision = 3
                            else:
                                precision = 3  # 默认精度
                            break
                    break
            
            if not symbol_found:
                self.logger.warning(f"未找到交易对精度信息: {symbol}, 使用默认精度: {precision}")
            
            quantity = round(quantity, precision)
            
        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"解析精度信息失败: {symbol}, 交易所信息: {exchange_info}, 错误: {e}")
            # 使用默认精度继续
            try:
                quantity = round(quantity, 3)
                self.logger.warning(f"使用默认精度: {symbol}, 数量: {quantity}")
            except Exception as round_error:
                self.logger.error(f"数量精度调整失败: {symbol}, 错误: {round_error}")
                return 0.0
        
        # 步骤10: 记录计算结果
        try:
            self.logger.info(f"固定金额交易计算: {symbol}, 固定金额: {CONFIG['fixed_trade_amount']} USDT, "
                           f"杠杆: {self.current_leverage}x, 价格: {price:.4f}, 计算数量: {quantity:.6f}, "
                           f"所需保证金: {required_margin:.2f} USDT")
        except Exception as e:
            self.logger.warning(f"记录计算结果失败: {symbol}, 错误: {e}")
        
        # 步骤11: 最终验证和返回
        try:
            if quantity <= 0:
                self.logger.warning(f"计算出的数量无效: {symbol}, 数量: {quantity}")
                return 0.0
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"最终验证失败: {symbol}, 数量: {quantity}, 错误: {e}")
            return 0.0

    def open_position(self, symbol: str, side: str, price: float):
        """
        开仓操作方法（使用TraderEngine）
        
        参数说明：
        - symbol: 交易对符号
        - side: 持仓方向 ('long' 或 'short')
        - price: 开仓价格（用于计算数量，实际价格由TraderEngine自动获取）
        
        功能描述：
        - 计算交易数量
        - 使用TraderEngine执行开仓操作
        - 同步持仓信息到WebTrader
        - 记录交易历史和文件
        """
        try:
            # 计算交易数量
            quantity = self.calculate_trade_quantity(symbol, price)
            if quantity <= 0:
                self.logger.error(f"❌ {symbol} 计算交易数量失败")
                return
            
            # 使用交易引擎执行开仓（新的简化接口）
            result = self.trader_engine.open_position(symbol, side, quantity, self.current_leverage)
            
            if result["success"]:
                # 同步持仓信息到WebTrader
                self.positions[symbol] = result["position"]
                
                # 记录交易历史
                trade_record = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': symbol,
                    'action': f'开{side}仓',
                    'quantity': result["quantity"],
                    'price': result["price"],
                    'type': '模拟' if CONFIG['demo_mode'] else '真实'
                }
                self.trades.append(trade_record)
                self.trade_count += 1
                
                # 写入交易记录到文本文件
                direction = '多头' if side == 'long' else '空头'
                self.write_trade_record(symbol, '开仓', direction, result["price"], result["quantity"])
                
                # 处理止损订单信息
                stop_loss_info = ""
                if "stop_loss" in result and result["stop_loss"]["success"]:
                    stop_price = result["stop_loss"]["stop_price"]
                    stop_order_id = result["stop_loss"]["order_id"]
                    stop_type = result["stop_loss"]["type"]
                    stop_loss_info = f", 止损价: {stop_price} ({stop_type}, 订单ID: {stop_order_id})"
                    self.logger.info(f"🛡️ {symbol} 止损订单已设置: 止损价 {stop_price}")
                elif "stop_loss" in result and not result["stop_loss"]["success"]:
                    self.logger.warning(f"⚠️ {symbol} 止损订单创建失败: {result['stop_loss']['error']}")
                    stop_loss_info = f", 止损设置失败: {result['stop_loss']['error']}"
                
                self.logger.info(f"✅ {symbol} 开{side}仓成功，数量: {result['quantity']}, 保证金: {result['margin']:.2f} USDT{stop_loss_info}")
            else:
                self.logger.error(f"❌ {symbol} 开{side}仓失败: {result['error']}")
            
        except Exception as e:
            self.logger.error(f"开 {symbol} {side} 仓失败: {e}")

    def close_position(self, symbol: str, quantity: float = None):
        """
        平仓操作方法（使用TraderEngine）
        
        参数说明：
        - symbol: 交易对符号
        - quantity: 平仓数量（可选，默认全部平仓）
        
        功能描述：
        - 使用TraderEngine执行平仓操作
        - 同步持仓信息到WebTrader
        - 记录交易历史和文件
        """
        try:
            # 检查是否有持仓
            if symbol not in self.positions:
                self.logger.warning(f"⚠️ {symbol} 没有持仓，无法平仓")
                return
            
            position = self.positions[symbol]
            
            # 使用交易引擎执行平仓（新的简化接口）
            result = self.trader_engine.close_position(symbol, quantity)
            
            if result["success"]:
                # 记录交易历史
                trade_record = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': symbol,
                    'action': f'平{position["side"]}仓',
                    'quantity': result["quantity"],
                    'price': result["price"],
                    'pnl': result["pnl"],
                    'type': '模拟' if CONFIG['demo_mode'] else '真实'
                }
                self.trades.append(trade_record)
                self.trade_count += 1
                
                # 写入交易记录到文本文件
                direction = '多头' if position['side'] == 'long' else '空头'
                self.write_trade_record(symbol, '平仓', direction, result["price"], result["quantity"], result["pnl"])
                
                # 根据盈亏调整杠杆
                self.adjust_leverage_based_on_pnl(symbol, result["pnl"])
                
                # 更新或清理持仓记录
                if result.get("remaining_quantity", 0) > 0:
                    # 部分平仓，更新持仓数量
                    self.positions[symbol]["quantity"] = result["remaining_quantity"]
                    self.logger.info(f"✅ {symbol} 部分平仓成功，剩余数量: {result['remaining_quantity']}, 盈亏: {result['pnl']:.2f} USDT")
                else:
                    # 全部平仓，清理持仓记录
                    del self.positions[symbol]
                    self.logger.info(f"✅ {symbol} 全部平仓成功，盈亏: {result['pnl']:.2f} USDT")
            else:
                self.logger.error(f"❌ {symbol} 平仓失败: {result['error']}")
            
        except Exception as e:
            self.logger.error(f"平 {symbol} 仓失败: {e}")

    def get_trading_data(self):
        """
        获取完整的交易数据用于Web界面显示
        
        返回值：
        - dict: 包含以下结构的交易数据
          - timestamp: 数据获取时间戳
          - capital: 当前可用资金
          - symbols: 各交易对的价格和EMA状态
          - positions: 当前持仓信息
          - summary: 账户汇总信息
        
        功能描述：
        - 收集所有交易对的实时价格和技术指标
        - 计算持仓的未实现盈亏
        - 生成账户资金汇总统计
        - 为Web界面提供完整的数据结构
        """
        try:
            # 初始化数据结构
            data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'capital': self.capital,
                'symbols': {},
                'positions': {},
                'summary': {}
            }
            
            # 初始化汇总统计变量
            total_margin = 0        # 总保证金占用
            total_unrealized_pnl = 0  # 总未实现盈亏
            
            # 遍历所有配置的交易对，获取详细信息
            for symbol in CONFIG['symbols']:
                try:
                    # 获取当前价格
                    current_price = self.get_current_price(symbol)
                    # 获取EMA状态和数值
                    ema_status, ema_short, ema_long = self.get_ema_status(symbol)
                    
                    # 存储交易对基础信息
                    data['symbols'][symbol] = {
                        'price': current_price,
                        'ema_status': ema_status,
                        'ema_short': float(ema_short) if ema_short else 0.0,
                        'ema_long': float(ema_long) if ema_long else 0.0
                    }
                    
                    # 处理持仓信息
                    position = self.positions.get(symbol)
                    if position:
                        # 计算未实现盈亏
                        unrealized_pnl = self.calculate_unrealized_pnl(symbol, current_price)
                        total_unrealized_pnl += unrealized_pnl
                        total_margin += position['margin']
                        
                        # 存储详细持仓信息
                        data['positions'][symbol] = {
                            'side': position['side'],           # 持仓方向
                            'size': position['size'],           # 持仓数量
                            'entry_price': position['entry_price'],  # 开仓价格
                            'current_price': current_price,     # 当前价格
                            'unrealized_pnl': unrealized_pnl,   # 未实现盈亏
                            'margin': position['margin']        # 保证金占用
                        }
                    else:
                        # 无持仓时设为None
                        data['positions'][symbol] = None
                        
                except Exception as e:
                    # 单个交易对数据获取失败时的容错处理
                    self.logger.error(f"获取{symbol}数据失败: {e}")
                    data['symbols'][symbol] = {
                        'price': 0.0,
                        'ema_status': "❌ 获取失败",
                        'ema_short': 0.0,
                        'ema_long': 0.0
                    }
                    data['positions'][symbol] = None
                    
            # 计算账户汇总信息
            total_value = self.capital + total_unrealized_pnl  # 总资产价值
            total_pnl_from_initial = total_value - CONFIG["initial_capital"]  # 相对初始资金的盈亏
            # 计算盈亏百分比
            pnl_percentage = (total_pnl_from_initial / CONFIG["initial_capital"]) * 100 if CONFIG["initial_capital"] > 0 else 0
            
            # 存储汇总统计信息
            data['summary'] = {
                'total_margin': total_margin,           # 总保证金占用
                'available_balance': self.capital,      # 可用余额
                'unrealized_pnl': total_unrealized_pnl, # 总未实现盈亏
                'total_value': total_value,             # 总资产价值
                'total_pnl': total_pnl_from_initial,    # 总盈亏
                'pnl_percentage': pnl_percentage,       # 盈亏百分比
                'trade_count': self.trade_count         # 交易次数
            }
            
            # 添加日志数据
            data['logs'] = self.log_buffer.copy()  # 复制日志缓冲区
            
            return data
            
        except Exception as e:
            self.logger.error(f"获取交易数据失败: {e}")
            # 返回默认数据结构，确保Web界面不会崩溃
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'capital': 0.0,
                'symbols': {symbol: {'price': 0.0, 'ema_short': 0.0, 'ema_long': 0.0, 'ema_status': "❌ 获取失败"} for symbol in CONFIG['symbols']},
                'positions': {symbol: None for symbol in CONFIG['symbols']},
                'summary': {'total_margin': 0.0, 'available_balance': 0.0, 'unrealized_pnl': 0.0, 'total_value': 0.0, 'total_pnl': 0.0, 'pnl_percentage': 0.0, 'trade_count': 0}
            }

# ============================================================================
# Web应用程序和WebSocket服务
# ============================================================================

# 创建全局交易器实例
trader = WebTrader()

# ============================================================================
# Flask路由定义
# ============================================================================

@app.route('/')
def index():
    """
    主页路由
    
    功能描述：
    - 渲染主页HTML模板
    - 提供Web交易界面的入口
    
    返回值：
    - HTML页面：交易监控界面
    """
    return render_template('index.html')



# ============================================================================
# WebSocket事件处理
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """
    WebSocket连接事件处理
    
    功能描述：
    - 处理客户端WebSocket连接请求
    - 发送连接确认消息
    - 建立实时数据推送通道
    """
    print('客户端已连接')
    emit('status', {'msg': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """
    WebSocket断开连接事件处理
    
    功能描述：
    - 处理客户端断开连接事件
    - 清理相关资源
    - 记录连接状态变化
    """
    print('客户端已断开连接')

# ============================================================================
# 后台任务和自动交易逻辑
# ============================================================================

def background_task():
    """
    后台任务主循环
    
    功能描述：
    - 每3秒获取K线数据用于前端显示
    - 严格按照半小时间隔（0分和30分）检测EMA交叉信号并执行自动交易
    - 实时推送交易数据到Web界面
    
    执行逻辑：
    1. 每3秒获取K线数据并推送到前端（仅用于显示）
    2. 只在半小时点（0分和30分）执行K线更新检测和交易逻辑
    3. 通过WebSocket推送到前端
    """
    while True:
        if trader.running:
            now = datetime.now()
            
            # 计算当前应该处理的5分钟点（EMA值打印）
            current_5min = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
            
            # 计算当前应该处理的半小时点（交易检测）
            current_half_hour = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
            
            # 检查是否应该执行5分钟检测（EMA值打印）
            time_since_5min = (now - current_5min).total_seconds()
            is_5min_point = 0 <= time_since_5min <= 30  # 30秒窗口
            
            # 检查是否应该执行半小时检测（交易检测）
            time_since_half_hour = (now - current_half_hour).total_seconds()
            is_half_hour_point = 0 <= time_since_half_hour <= 30  # 30秒窗口
            
            # 每分钟记录一次检测状态（用于调试）
            if now.second < 3:  # 避免重复日志
                trader.logger.info(f"检测状态 - 当前时间: {now.strftime('%H:%M:%S')}, "
                                  f"5分钟点: {current_5min.strftime('%H:%M')}, "
                                  f"半小时点: {current_half_hour.strftime('%H:%M')}, "
                                  f"距离5分钟点: {time_since_5min:.0f}秒, "
                                  f"距离半小时点: {time_since_half_hour:.0f}秒, "
                                  f"5分钟检测窗口: {is_5min_point}, "
                                  f"半小时检测窗口: {is_half_hour_point}")
            
            # 遍历所有交易对
            for symbol in CONFIG['symbols']:
                try:
                    # 每3秒都获取K线数据用于前端显示
                    df = trader.get_kline_data(symbol)
                    if df.empty:
                        if is_5min_point or is_half_hour_point:  # 只在检测点时记录警告
                            trader.logger.warning(f"{symbol} K线数据为空，跳过处理")
                        continue

                    # 5分钟EMA值打印检测
                    if is_5min_point:
                        # 检查是否已经在这个5分钟点执行过EMA打印
                        should_print_ema = False
                        
                        if trader.last_5min_check_time[symbol] is None:
                            # 第一次5分钟检测
                            should_print_ema = True
                            trader.logger.info(f"{symbol} 首次5分钟EMA检测")
                        elif trader.last_5min_check_time[symbol] < current_5min:
                            # 发现有未处理的5分钟点
                            should_print_ema = True
                            missed_time = current_5min - trader.last_5min_check_time[symbol]
                            trader.logger.info(f"{symbol} 检测到遗漏的5分钟点，距离上次检测: {missed_time}")
                        
                        if should_print_ema:
                            trader.logger.info(f"=== 5分钟EMA检测 {symbol} ===")
                            trader.logger.info(f"当前时间: {now.strftime('%H:%M:%S')}")
                            
                            latest_kline_close_time = df['timestamp'].iloc[-1]
                            trader.logger.info(f"最新K线收盘时间: {latest_kline_close_time}")
                            
                            # 计算EMA值
                            df = trader.calculate_ema(df)
                            
                            # 打印当前EMA数值
                            ema_short_col = f'ema_{CONFIG["ema_short"]}'
                            ema_long_col = f'ema_{CONFIG["ema_long"]}'
                            latest_ema_short = df[ema_short_col].iloc[-1]
                            latest_ema_long = df[ema_long_col].iloc[-1]
                            trader.logger.info(f"{symbol} 当前EMA{CONFIG['ema_short']}: {latest_ema_short:.2f}, EMA{CONFIG['ema_long']}: {latest_ema_long:.2f}")
                            
                            # 标记这个5分钟点已经检测过
                            trader.last_5min_check_time[symbol] = current_5min
                            
                            # 保存检测状态到文件
                            trader.save_detection_state()
                            
                            trader.logger.info(f"=== {symbol} 5分钟EMA检测完成 ===")

                    # 半小时交易检测
                    if is_half_hour_point:
                        # 检查是否已经在这个半小时点执行过交易检测
                        should_trade_check = False
                        
                        if trader.last_half_hour_check_time[symbol] is None:
                            # 第一次半小时检测
                            should_trade_check = True
                            trader.logger.info(f"{symbol} 首次半小时交易检测")
                        elif trader.last_half_hour_check_time[symbol] < current_half_hour:
                            # 发现有未处理的半小时点
                            should_trade_check = True
                            missed_time = current_half_hour - trader.last_half_hour_check_time[symbol]
                            trader.logger.info(f"{symbol} 检测到遗漏的半小时点，距离上次检测: {missed_time}")
                        
                        if should_trade_check:
                            trader.logger.info(f"=== 半小时交易检测 {symbol} ===")
                            trader.logger.info(f"当前时间: {now.strftime('%H:%M:%S')}")
                            
                            # 计算EMA值
                            df = trader.calculate_ema(df)
                            
                            # 打印当前EMA数值
                            ema_short_col = f'ema_{CONFIG["ema_short"]}'
                            ema_long_col = f'ema_{CONFIG["ema_long"]}'
                            latest_ema_short = df[ema_short_col].iloc[-1]
                            latest_ema_long = df[ema_long_col].iloc[-1]
                            trader.logger.info(f"{symbol} 半小时检测 - EMA{CONFIG['ema_short']}: {latest_ema_short:.2f}, EMA{CONFIG['ema_long']}: {latest_ema_long:.2f}")
                            
                            # 检测EMA交叉并执行交易逻辑
                            cross_result = trader.check_ema_cross(symbol)
                            if cross_result:
                                trader.logger.info(f"{symbol} 检测到EMA交叉: {cross_result}")
                                
                                # 先获取当前仓位状态
                                current_position = trader.trader_engine.get_position(symbol)
                                trader.logger.info(f"=== {symbol} 仓位状态检查 ===")
                                
                                if current_position:
                                    trader.logger.info(f"{symbol} 当前持仓: {current_position['side']} 方向, 数量: {current_position['size']}")
                                else:
                                    trader.logger.info(f"{symbol} 当前无持仓")
                                
                                # 将交叉信号转换为交易方向
                                if cross_result == 'golden_cross':
                                    signal_direction = 'long'  # 金叉做多
                                elif cross_result == 'death_cross':
                                    signal_direction = 'short'  # 死叉做空
                                else:
                                    trader.logger.warning(f"{symbol} 未知的交叉信号: {cross_result}")
                                    continue
                                
                                # 根据当前仓位状态和信号方向做出交易决策
                                trader.logger.info(f"=== {symbol} 交易决策分析 ===")
                                trader.logger.info(f"信号方向: {signal_direction}")
                                
                                if current_position is None:
                                    # 无持仓：直接开新仓
                                    trader.logger.info(f"{symbol} 决策: 无持仓，开 {signal_direction} 仓")
                                    trader.execute_trade(symbol, signal_direction)
                                elif current_position['side'] == signal_direction:
                                    # 已有相同方向持仓：不操作
                                    trader.logger.info(f"{symbol} 决策: 已有 {signal_direction} 持仓，跳过交易")
                                else:
                                    # 有反向持仓：先平仓再开新仓
                                    trader.logger.info(f"{symbol} 决策: 有 {current_position['side']} 持仓，需平仓后开 {signal_direction} 仓")
                                    trader.execute_trade(symbol, signal_direction)
                                
                                trader.logger.info(f"=== {symbol} 交易决策完成 ===")
                            else:
                                trader.logger.info(f"{symbol} 未检测到EMA交叉")
                            
                            # 标记这个半小时点已经检测过
                            trader.last_half_hour_check_time[symbol] = current_half_hour
                            
                            # 保存检测状态到文件
                            trader.save_detection_state()
                            
                            trader.logger.info(f"=== {symbol} 半小时交易检测完成 ===")
                
                except Exception as e:
                    trader.logger.error(f"处理交易对 {symbol} 时发生错误: {str(e)}")
                    import traceback
                    trader.logger.error(f"错误详情: {traceback.format_exc()}")

            # 独立的半小时EMA值日志记录（测试期间暂时注释）
            # if is_half_hour_point and (trader.last_half_hour_log_time is None or trader.last_half_hour_log_time != current_half_hour):
            #     trader.logger.info(f"--- 整点/半点报告 ({current_half_hour.strftime('%H:%M')}) ---")
            #     for symbol in CONFIG['symbols']:
            #         df = trader.get_kline_data(symbol)
            #         if not df.empty:
            #             ema_short_col = f'ema_{CONFIG["ema_short"]}'
            #             ema_long_col = f'ema_{CONFIG["ema_long"]}'
            #             latest_ema_short = df[ema_short_col].iloc[-1]
            #             latest_ema_long = df[ema_long_col].iloc[-1]
            #             trader.logger.info(f"{symbol} 当前EMA{CONFIG['ema_short']}: {latest_ema_short:.2f}, EMA{CONFIG['ema_long']}: {latest_ema_long:.2f}")
            #     trader.last_half_hour_log_time = current_half_hour

            # 每3秒获取并推送最新的交易数据到前端（用于实时显示）
            trading_data = trader.get_trading_data()
            socketio.emit('update_data', trading_data)

        time.sleep(CONFIG['check_interval'])

# ============================================================================
# 系统启动和初始化
# ============================================================================

# 启动后台任务线程
trader.running = True  # 设置交易器运行状态为True
background_thread = threading.Thread(target=background_task)  # 创建后台任务线程
background_thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
background_thread.start()  # 启动后台任务线程

# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == '__main__':
    """
    主程序入口
    
    功能描述：
    - 显示系统启动信息和配置参数
    - 启动Flask Web服务器和WebSocket服务
    - 提供Web界面访问入口
    
    启动流程：
    1. 打印系统信息和配置参数
    2. 显示访问地址
    3. 启动SocketIO服务器（包含Flask应用）
    """
    print("=" * 60)
    print("🌐 Web实时交易监控系统（动态杠杆版本）")
    print("=" * 60)
    print(f"交易对: {CONFIG['symbols']}")
    print(f"策略: EMA{CONFIG['ema_short']}/EMA{CONFIG['ema_long']} 交叉")
    print(f"固定交易金额: {CONFIG['fixed_trade_amount']} USDT")
    print(f"基础杠杆倍数: {CONFIG['base_leverage']}x")
    print(f"杠杆调整规则: 亏损后杠杆+{CONFIG['leverage_increment']}, 盈利后杠杆回归{CONFIG['base_leverage']}")
    print(f"更新间隔: {CONFIG['check_interval']} 秒")
    print("=" * 60)
    print("🚀 启动Web服务器...")
    print("📱 访问地址: http://43.156.49.149:5001")
    print("=" * 60)

    # 启动SocketIO服务器
    # host='0.0.0.0': 允许外部访问
    # port=5001: 监听端口5001
    # debug=False: 生产模式，不显示调试信息
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)