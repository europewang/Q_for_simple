"""
Web监控界面
提供实时交易系统状态的Web界面展示
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import threading
import time

try:
    from flask import Flask, render_template, jsonify, request
    from flask_socketio import SocketIO, emit
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from shared.utils.logger import get_logger


class WebMonitor:
    """Web监控界面"""
    
    def __init__(self, port: int = 5000, update_interval: int = 1):
        """
        初始化Web监控
        
        Args:
            port: Web服务端口
            update_interval: 更新间隔（秒）
        """
        self.port = port
        self.update_interval = update_interval
        self.logger = get_logger("WebMonitor")
        
        # 系统状态数据
        self.system_data = {
            'status': 'stopped',
            'last_update': None,
            'account_info': {},
            'positions': [],
            'orders': [],
            'risk_metrics': {},
            'strategy_status': {},
            'execution_stats': {},
            'market_data': {}
        }
        
        # 历史数据
        self.price_history = []
        self.pnl_history = []
        self.signal_history = []
        
        # 运行状态
        self.running = False
        self.app = None
        self.socketio = None
        self.update_thread = None
        
        if not FLASK_AVAILABLE:
            self.logger.warning("Flask未安装，Web监控功能不可用")
            return
        
        self._setup_flask_app()
    
    def _setup_flask_app(self):
        """设置Flask应用"""
        if not FLASK_AVAILABLE:
            return
        
        self.app = Flask(__name__, template_folder=self._get_template_folder())
        self.app.config['SECRET_KEY'] = 'trading_system_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 注册路由
        self._register_routes()
        self._register_socketio_events()
    
    def _get_template_folder(self) -> str:
        """获取模板文件夹路径"""
        current_dir = os.path.dirname(__file__)
        template_dir = os.path.join(current_dir, 'templates')
        os.makedirs(template_dir, exist_ok=True)
        return template_dir
    
    def _register_routes(self):
        """注册Flask路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return self._render_dashboard()
        
        @self.app.route('/api/status')
        def get_status():
            """获取系统状态API"""
            return jsonify(self.system_data)
        
        @self.app.route('/api/history/<data_type>')
        def get_history(data_type):
            """获取历史数据API"""
            if data_type == 'price':
                return jsonify(self.price_history[-100:])  # 最近100个数据点
            elif data_type == 'pnl':
                return jsonify(self.pnl_history[-100:])
            elif data_type == 'signals':
                return jsonify(self.signal_history[-50:])  # 最近50个信号
            else:
                return jsonify([])
        
        @self.app.route('/api/control/<action>', methods=['POST'])
        def control_system(action):
            """系统控制API"""
            # 这里可以添加启动/停止等控制功能
            return jsonify({'status': 'success', 'action': action})
    
    def _register_socketio_events(self):
        """注册SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接"""
            self.logger.info("Web客户端已连接")
            emit('status_update', self.system_data)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开连接"""
            self.logger.info("Web客户端已断开连接")
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """客户端请求更新"""
            emit('status_update', self.system_data)
    
    def _render_dashboard(self) -> str:
        """渲染仪表板"""
        # 简单的HTML模板
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>实时交易系统监控</title>
            <meta charset="utf-8">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
                .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
                .status-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .status-card h3 { margin-top: 0; color: #2c3e50; }
                .status-value { font-size: 24px; font-weight: bold; margin: 10px 0; }
                .status-positive { color: #27ae60; }
                .status-negative { color: #e74c3c; }
                .status-neutral { color: #34495e; }
                .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .log-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-height: 300px; overflow-y: auto; }
                .log-entry { padding: 5px 0; border-bottom: 1px solid #eee; font-family: monospace; font-size: 12px; }
                .running { color: #27ae60; }
                .stopped { color: #e74c3c; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>实时交易系统监控</h1>
                    <p>系统状态: <span id="system-status" class="stopped">已停止</span> | 最后更新: <span id="last-update">--</span></p>
                </div>
                
                <div class="status-grid">
                    <div class="status-card">
                        <h3>账户信息</h3>
                        <div>总余额: <span id="total-balance" class="status-value status-neutral">--</span> USDT</div>
                        <div>可用余额: <span id="available-balance" class="status-value status-neutral">--</span> USDT</div>
                        <div>未实现盈亏: <span id="unrealized-pnl" class="status-value status-neutral">--</span> USDT</div>
                    </div>
                    
                    <div class="status-card">
                        <h3>持仓信息</h3>
                        <div>持仓数量: <span id="position-count" class="status-value status-neutral">--</span></div>
                        <div>总持仓价值: <span id="position-value" class="status-value status-neutral">--</span> USDT</div>
                        <div>今日盈亏: <span id="daily-pnl" class="status-value status-neutral">--</span> USDT</div>
                    </div>
                    
                    <div class="status-card">
                        <h3>交易统计</h3>
                        <div>今日交易次数: <span id="daily-trades" class="status-value status-neutral">--</span></div>
                        <div>成功率: <span id="success-rate" class="status-value status-neutral">--%</span></div>
                        <div>平均盈亏: <span id="avg-pnl" class="status-value status-neutral">--</span> USDT</div>
                    </div>
                    
                    <div class="status-card">
                        <h3>风险指标</h3>
                        <div>最大回撤: <span id="max-drawdown" class="status-value status-neutral">--%</span></div>
                        <div>风险度: <span id="risk-level" class="status-value status-neutral">--</span></div>
                        <div>杠杆倍数: <span id="leverage" class="status-value status-neutral">--</span>x</div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3>价格走势</h3>
                    <canvas id="priceChart" width="400" height="200"></canvas>
                </div>
                
                <div class="chart-container">
                    <h3>盈亏曲线</h3>
                    <canvas id="pnlChart" width="400" height="200"></canvas>
                </div>
                
                <div class="log-container">
                    <h3>最新信号</h3>
                    <div id="signal-log"></div>
                </div>
            </div>
            
            <script>
                // 初始化Socket.IO连接
                const socket = io();
                
                // 初始化图表
                const priceCtx = document.getElementById('priceChart').getContext('2d');
                const pnlCtx = document.getElementById('pnlChart').getContext('2d');
                
                const priceChart = new Chart(priceCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: '价格',
                            data: [],
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52, 152, 219, 0.1)',
                            tension: 0.1
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: false }
                        }
                    }
                });
                
                const pnlChart = new Chart(pnlCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: '累计盈亏',
                            data: [],
                            borderColor: '#27ae60',
                            backgroundColor: 'rgba(39, 174, 96, 0.1)',
                            tension: 0.1
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
                
                // 处理状态更新
                socket.on('status_update', function(data) {
                    updateStatus(data);
                });
                
                function updateStatus(data) {
                    // 更新系统状态
                    const statusElement = document.getElementById('system-status');
                    statusElement.textContent = data.status === 'running' ? '运行中' : '已停止';
                    statusElement.className = data.status === 'running' ? 'running' : 'stopped';
                    
                    document.getElementById('last-update').textContent = 
                        data.last_update ? new Date(data.last_update).toLocaleString() : '--';
                    
                    // 更新账户信息
                    if (data.account_info) {
                        document.getElementById('total-balance').textContent = 
                            (data.account_info.total_wallet_balance || 0).toFixed(2);
                        document.getElementById('available-balance').textContent = 
                            (data.account_info.available_balance || 0).toFixed(2);
                        document.getElementById('unrealized-pnl').textContent = 
                            (data.account_info.total_unrealized_pnl || 0).toFixed(2);
                    }
                    
                    // 更新持仓信息
                    if (data.positions) {
                        document.getElementById('position-count').textContent = data.positions.length;
                    }
                    
                    // 更新风险指标
                    if (data.risk_metrics) {
                        document.getElementById('max-drawdown').textContent = 
                            ((data.risk_metrics.max_drawdown || 0) * 100).toFixed(2);
                    }
                }
                
                // 定期请求更新
                setInterval(() => {
                    socket.emit('request_update');
                }, 5000);
                
                // 页面加载时请求初始数据
                socket.emit('request_update');
            </script>
        </body>
        </html>
        """
        return html_template
    
    def start(self):
        """启动Web监控"""
        if not FLASK_AVAILABLE:
            self.logger.error("Flask未安装，无法启动Web监控")
            return
        
        if self.running:
            self.logger.warning("Web监控已在运行")
            return
        
        self.running = True
        self.logger.info(f"启动Web监控，端口: {self.port}")
        
        # 启动更新线程
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # 启动Flask应用
        try:
            self.socketio.run(
                self.app,
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            self.logger.error(f"启动Web监控失败: {str(e)}")
            self.running = False
    
    def stop(self):
        """停止Web监控"""
        self.running = False
        self.logger.info("Web监控已停止")
    
    def update_system_data(self, data: Dict[str, Any]):
        """更新系统数据"""
        self.system_data.update(data)
        self.system_data['last_update'] = datetime.now().isoformat()
        
        # 更新历史数据
        if 'market_data' in data and data['market_data']:
            market_data = data['market_data']
            self.price_history.append({
                'timestamp': datetime.now().isoformat(),
                'price': market_data.get('close', 0)
            })
            
            # 保持历史数据长度
            if len(self.price_history) > 1000:
                self.price_history = self.price_history[-1000:]
        
        if 'risk_metrics' in data and data['risk_metrics']:
            risk_metrics = data['risk_metrics']
            self.pnl_history.append({
                'timestamp': datetime.now().isoformat(),
                'total_pnl': risk_metrics.get('total_pnl', 0),
                'daily_pnl': risk_metrics.get('daily_pnl', 0)
            })
            
            if len(self.pnl_history) > 1000:
                self.pnl_history = self.pnl_history[-1000:]
        
        # 通过WebSocket发送更新
        if self.socketio and self.running:
            try:
                self.socketio.emit('status_update', self.system_data)
            except Exception as e:
                self.logger.error(f"发送WebSocket更新失败: {str(e)}")
    
    def add_signal(self, signal_data: Dict[str, Any]):
        """添加交易信号"""
        signal_entry = {
            'timestamp': datetime.now().isoformat(),
            'symbol': signal_data.get('symbol', ''),
            'action': signal_data.get('action', ''),
            'strength': signal_data.get('strength', 0),
            'price': signal_data.get('price', 0),
            'reason': signal_data.get('reason', '')
        }
        
        self.signal_history.append(signal_entry)
        
        # 保持历史数据长度
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]
        
        # 通过WebSocket发送信号更新
        if self.socketio and self.running:
            try:
                self.socketio.emit('new_signal', signal_entry)
            except Exception as e:
                self.logger.error(f"发送信号更新失败: {str(e)}")
    
    def _update_loop(self):
        """更新循环"""
        while self.running:
            try:
                # 这里可以添加定期更新逻辑
                time.sleep(self.update_interval)
            except Exception as e:
                self.logger.error(f"更新循环出错: {str(e)}")
                time.sleep(1)
    
    def get_web_url(self) -> str:
        """获取Web界面URL"""
        return f"http://localhost:{self.port}"