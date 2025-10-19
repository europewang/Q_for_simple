"""
状态监控模块
提供系统状态跟踪、性能监控和报警功能
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, asdict
from collections import deque

from shared.utils.logger import get_logger


@dataclass
class PerformanceMetrics:
    """性能指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    network_latency: float = 0.0
    order_execution_time: float = 0.0
    data_feed_delay: float = 0.0
    last_update: datetime = None


@dataclass
class AlertRule:
    """报警规则"""
    name: str
    condition: str  # 条件表达式
    threshold: float
    message: str
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    cooldown_minutes: int = 5  # 冷却时间（分钟）


class StatusMonitor:
    """状态监控器"""
    
    def __init__(self, update_interval: int = 5, history_size: int = 1000):
        """
        初始化状态监控器
        
        Args:
            update_interval: 更新间隔（秒）
            history_size: 历史数据保存数量
        """
        self.update_interval = update_interval
        self.history_size = history_size
        self.logger = get_logger("StatusMonitor")
        
        # 系统状态
        self.system_status = {
            'running': False,
            'start_time': None,
            'uptime': 0,
            'last_heartbeat': None,
            'error_count': 0,
            'warning_count': 0
        }
        
        # 性能指标
        self.performance_metrics = PerformanceMetrics()
        self.performance_history = deque(maxlen=history_size)
        
        # 交易统计
        self.trading_stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_volume': 0.0,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'avg_trade_duration': 0.0,
            'last_trade_time': None
        }
        
        # 报警规则
        self.alert_rules = self._create_default_alert_rules()
        self.alert_callbacks: List[Callable] = []
        
        # 历史数据
        self.status_history = deque(maxlen=history_size)
        self.alert_history = deque(maxlen=100)
        
        # 运行状态
        self.running = False
        self.monitor_thread = None
        
        # 性能监控
        self.execution_times = deque(maxlen=100)
        self.latency_measurements = deque(maxlen=100)
    
    def _create_default_alert_rules(self) -> List[AlertRule]:
        """创建默认报警规则"""
        return [
            AlertRule(
                name="高CPU使用率",
                condition="cpu_usage > threshold",
                threshold=80.0,
                message="CPU使用率超过{threshold}%: {value}%"
            ),
            AlertRule(
                name="高内存使用率",
                condition="memory_usage > threshold",
                threshold=85.0,
                message="内存使用率超过{threshold}%: {value}%"
            ),
            AlertRule(
                name="网络延迟过高",
                condition="network_latency > threshold",
                threshold=1000.0,
                message="网络延迟过高: {value}ms"
            ),
            AlertRule(
                name="订单执行时间过长",
                condition="order_execution_time > threshold",
                threshold=5000.0,
                message="订单执行时间过长: {value}ms"
            ),
            AlertRule(
                name="数据延迟过高",
                condition="data_feed_delay > threshold",
                threshold=2000.0,
                message="数据源延迟过高: {value}ms"
            ),
            AlertRule(
                name="最大回撤过大",
                condition="max_drawdown > threshold",
                threshold=10.0,
                message="最大回撤超过{threshold}%: {value}%"
            ),
            AlertRule(
                name="日盈亏过低",
                condition="daily_pnl < threshold",
                threshold=-1000.0,
                message="日盈亏低于{threshold}: {value}"
            ),
            AlertRule(
                name="错误数量过多",
                condition="error_count > threshold",
                threshold=10,
                message="错误数量过多: {value}次"
            )
        ]
    
    def start(self):
        """启动状态监控"""
        if self.running:
            self.logger.warning("状态监控已在运行")
            return
        
        self.running = True
        self.system_status['running'] = True
        self.system_status['start_time'] = datetime.now()
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("状态监控已启动")
    
    def stop(self):
        """停止状态监控"""
        self.running = False
        self.system_status['running'] = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("状态监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 更新系统状态
                self._update_system_status()
                
                # 更新性能指标
                self._update_performance_metrics()
                
                # 检查报警规则
                self._check_alert_rules()
                
                # 保存历史数据
                self._save_status_snapshot()
                
                # 等待下次更新
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环出错: {str(e)}")
                self.system_status['error_count'] += 1
                time.sleep(1)
    
    def _update_system_status(self):
        """更新系统状态"""
        now = datetime.now()
        
        if self.system_status['start_time']:
            self.system_status['uptime'] = (now - self.system_status['start_time']).total_seconds()
        
        self.system_status['last_heartbeat'] = now
    
    def _update_performance_metrics(self):
        """更新性能指标"""
        try:
            # 尝试获取系统性能指标
            import psutil
            
            # CPU使用率
            self.performance_metrics.cpu_usage = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self.performance_metrics.memory_usage = memory.percent
            
            # 网络延迟（简单的ping测试）
            self.performance_metrics.network_latency = self._measure_network_latency()
            
            # 订单执行时间（从历史数据计算平均值）
            if self.execution_times:
                self.performance_metrics.order_execution_time = sum(self.execution_times) / len(self.execution_times)
            
            self.performance_metrics.last_update = datetime.now()
            
            # 保存到历史记录
            self.performance_history.append(asdict(self.performance_metrics))
            
        except ImportError:
            # 如果psutil不可用，使用模拟数据
            self.performance_metrics.cpu_usage = 0.0
            self.performance_metrics.memory_usage = 0.0
            self.performance_metrics.last_update = datetime.now()
        except Exception as e:
            self.logger.error(f"更新性能指标失败: {str(e)}")
    
    def _measure_network_latency(self) -> float:
        """测量网络延迟"""
        try:
            import subprocess
            import platform
            
            # 根据操作系统选择ping命令
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "1", "8.8.8.8"]
            else:
                cmd = ["ping", "-c", "1", "8.8.8.8"]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            end_time = time.time()
            
            if result.returncode == 0:
                return (end_time - start_time) * 1000  # 转换为毫秒
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _check_alert_rules(self):
        """检查报警规则"""
        current_time = datetime.now()
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if (rule.last_triggered and 
                current_time - rule.last_triggered < timedelta(minutes=rule.cooldown_minutes)):
                continue
            
            # 评估条件
            if self._evaluate_alert_condition(rule):
                self._trigger_alert(rule, current_time)
    
    def _evaluate_alert_condition(self, rule: AlertRule) -> bool:
        """评估报警条件"""
        try:
            # 构建评估上下文
            context = {
                'cpu_usage': self.performance_metrics.cpu_usage,
                'memory_usage': self.performance_metrics.memory_usage,
                'network_latency': self.performance_metrics.network_latency,
                'order_execution_time': self.performance_metrics.order_execution_time,
                'data_feed_delay': self.performance_metrics.data_feed_delay,
                'max_drawdown': abs(self.trading_stats['max_drawdown']),
                'daily_pnl': self.trading_stats['daily_pnl'],
                'error_count': self.system_status['error_count'],
                'threshold': rule.threshold
            }
            
            # 评估条件表达式
            return eval(rule.condition, {"__builtins__": {}}, context)
            
        except Exception as e:
            self.logger.error(f"评估报警条件失败 [{rule.name}]: {str(e)}")
            return False
    
    def _trigger_alert(self, rule: AlertRule, trigger_time: datetime):
        """触发报警"""
        # 获取当前值
        value = self._get_rule_value(rule)
        
        # 格式化消息
        message = rule.message.format(
            threshold=rule.threshold,
            value=value
        )
        
        # 创建报警记录
        alert = {
            'rule_name': rule.name,
            'message': message,
            'value': value,
            'threshold': rule.threshold,
            'timestamp': trigger_time,
            'severity': self._get_alert_severity(rule)
        }
        
        # 保存到历史记录
        self.alert_history.append(alert)
        
        # 更新规则触发时间
        rule.last_triggered = trigger_time
        
        # 调用报警回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"报警回调执行失败: {str(e)}")
        
        # 记录日志
        self.logger.warning(f"报警触发: {message}")
    
    def _get_rule_value(self, rule: AlertRule) -> float:
        """获取规则对应的当前值"""
        if "cpu_usage" in rule.condition:
            return self.performance_metrics.cpu_usage
        elif "memory_usage" in rule.condition:
            return self.performance_metrics.memory_usage
        elif "network_latency" in rule.condition:
            return self.performance_metrics.network_latency
        elif "order_execution_time" in rule.condition:
            return self.performance_metrics.order_execution_time
        elif "data_feed_delay" in rule.condition:
            return self.performance_metrics.data_feed_delay
        elif "max_drawdown" in rule.condition:
            return abs(self.trading_stats['max_drawdown'])
        elif "daily_pnl" in rule.condition:
            return self.trading_stats['daily_pnl']
        elif "error_count" in rule.condition:
            return self.system_status['error_count']
        else:
            return 0.0
    
    def _get_alert_severity(self, rule: AlertRule) -> str:
        """获取报警严重程度"""
        if "error" in rule.name.lower() or "失败" in rule.name:
            return "error"
        elif "高" in rule.name or "过" in rule.name:
            return "warning"
        else:
            return "info"
    
    def _save_status_snapshot(self):
        """保存状态快照"""
        snapshot = {
            'timestamp': datetime.now(),
            'system_status': self.system_status.copy(),
            'performance_metrics': asdict(self.performance_metrics),
            'trading_stats': self.trading_stats.copy()
        }
        
        self.status_history.append(snapshot)
    
    def update_trading_stats(self, stats: Dict[str, Any]):
        """更新交易统计"""
        self.trading_stats.update(stats)
        
        # 计算胜率
        if self.trading_stats['total_trades'] > 0:
            self.trading_stats['win_rate'] = (
                self.trading_stats['successful_trades'] / 
                self.trading_stats['total_trades'] * 100
            )
    
    def record_order_execution_time(self, execution_time_ms: float):
        """记录订单执行时间"""
        self.execution_times.append(execution_time_ms)
    
    def record_network_latency(self, latency_ms: float):
        """记录网络延迟"""
        self.latency_measurements.append(latency_ms)
        self.performance_metrics.network_latency = latency_ms
    
    def record_data_feed_delay(self, delay_ms: float):
        """记录数据源延迟"""
        self.performance_metrics.data_feed_delay = delay_ms
    
    def add_alert_callback(self, callback: Callable):
        """添加报警回调函数"""
        self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable):
        """移除报警回调函数"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        return {
            'system_status': self.system_status,
            'performance_metrics': asdict(self.performance_metrics),
            'trading_stats': self.trading_stats,
            'recent_alerts': list(self.alert_history)[-10:],  # 最近10个报警
            'uptime_hours': self.system_status['uptime'] / 3600 if self.system_status['uptime'] else 0
        }
    
    def get_performance_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取性能历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            record for record in self.performance_history
            if record.get('last_update') and 
            datetime.fromisoformat(record['last_update']) > cutoff_time
        ]
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取报警历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if alert['timestamp'] > cutoff_time
        ]
    
    def enable_alert_rule(self, rule_name: str):
        """启用报警规则"""
        for rule in self.alert_rules:
            if rule.name == rule_name:
                rule.enabled = True
                self.logger.info(f"已启用报警规则: {rule_name}")
                return
        
        self.logger.warning(f"未找到报警规则: {rule_name}")
    
    def disable_alert_rule(self, rule_name: str):
        """禁用报警规则"""
        for rule in self.alert_rules:
            if rule.name == rule_name:
                rule.enabled = False
                self.logger.info(f"已禁用报警规则: {rule_name}")
                return
        
        self.logger.warning(f"未找到报警规则: {rule_name}")
    
    def add_custom_alert_rule(self, rule: AlertRule):
        """添加自定义报警规则"""
        self.alert_rules.append(rule)
        self.logger.info(f"已添加自定义报警规则: {rule.name}")
    
    def increment_error_count(self):
        """增加错误计数"""
        self.system_status['error_count'] += 1
    
    def increment_warning_count(self):
        """增加警告计数"""
        self.system_status['warning_count'] += 1
    
    def reset_daily_stats(self):
        """重置日统计"""
        self.trading_stats['daily_pnl'] = 0.0
        self.system_status['error_count'] = 0
        self.system_status['warning_count'] = 0
        self.logger.info("已重置日统计数据")