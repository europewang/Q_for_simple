"""
风险管理模块
负责控制交易风险，包括仓位大小、止损止盈、最大回撤等
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from shared.models.trade_models import Signal, Position, Order, OrderSide, PositionSide, AccountInfo
from shared.utils.logger import get_logger


@dataclass
class RiskMetrics:
    """风险指标"""
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_position_size: float
    current_exposure: float


class RiskManager:
    """风险管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化风险管理器
        
        Args:
            config: 风险管理配置
        """
        self.config = config
        self.logger = get_logger("RiskManager")
        
        # 风险参数
        self.max_position_percentage = config.get('max_position_percentage', 0.95)  # 最大仓位比例
        self.max_daily_loss_percentage = config.get('max_daily_loss_percentage', 0.05)  # 最大日损失比例
        self.max_drawdown_percentage = config.get('max_drawdown_percentage', 0.10)  # 最大回撤比例
        self.stop_loss_percentage = config.get('stop_loss_percentage', 0.02)  # 止损比例
        self.take_profit_percentage = config.get('take_profit_percentage', 0.06)  # 止盈比例
        self.min_position_size = config.get('min_position_size', 10.0)  # 最小仓位大小
        self.max_leverage = config.get('max_leverage', 20.0)  # 最大杠杆
        
        # 风险状态
        self.daily_start_balance = 0.0
        self.peak_balance = 0.0
        self.current_balance = 0.0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        
        # 交易统计
        self.trades_today = 0
        self.max_trades_per_day = config.get('max_trades_per_day', 50)
        self.trade_history: List[Dict[str, Any]] = []
        
        # 风险控制状态
        self.trading_enabled = True
        self.risk_alerts: List[str] = []
        
        self.logger.info("风险管理器初始化完成")
    
    def update_account_info(self, account_info: AccountInfo):
        """
        更新账户信息
        
        Args:
            account_info: 账户信息
        """
        self.current_balance = account_info.total_wallet_balance
        
        # 更新峰值余额
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # 计算回撤
        if self.peak_balance > 0:
            self.current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        
        # 检查风险限制
        self._check_risk_limits()
    
    def validate_signal(self, signal: Signal, account_info: AccountInfo, current_position: Optional[Position]) -> bool:
        """
        验证交易信号是否符合风险管理要求
        
        Args:
            signal: 交易信号
            account_info: 账户信息
            current_position: 当前持仓
            
        Returns:
            是否允许执行信号
        """
        if not self.trading_enabled:
            self.logger.warning("交易已被风险管理器禁用")
            return False
        
        # 检查日交易次数限制
        if self.trades_today >= self.max_trades_per_day:
            self.logger.warning(f"今日交易次数已达上限: {self.max_trades_per_day}")
            return False
        
        # 检查最大回撤限制
        if self.current_drawdown > self.max_drawdown_percentage:
            self.logger.warning(f"当前回撤 {self.current_drawdown:.2%} 超过限制 {self.max_drawdown_percentage:.2%}")
            return False
        
        # 检查日损失限制
        daily_loss_percentage = abs(self.daily_pnl) / self.daily_start_balance if self.daily_start_balance > 0 else 0
        if self.daily_pnl < 0 and daily_loss_percentage > self.max_daily_loss_percentage:
            self.logger.warning(f"今日损失 {daily_loss_percentage:.2%} 超过限制 {self.max_daily_loss_percentage:.2%}")
            return False
        
        return True
    
    def calculate_position_size(self, signal: Signal, account_info: AccountInfo) -> float:
        """
        计算仓位大小
        
        Args:
            signal: 交易信号
            account_info: 账户信息
            
        Returns:
            仓位大小（USDT金额）
        """
        # 可用余额
        available_balance = account_info.available_balance
        
        # 基础仓位大小
        base_position_size = available_balance * self.max_position_percentage
        
        # 根据信号强度调整
        adjusted_size = base_position_size * signal.strength
        
        # 应用最小和最大限制
        adjusted_size = max(adjusted_size, self.min_position_size)
        adjusted_size = min(adjusted_size, available_balance * 0.95)
        
        # 考虑杠杆限制
        max_position_with_leverage = available_balance * self.max_leverage
        adjusted_size = min(adjusted_size, max_position_with_leverage)
        
        self.logger.info(f"计算仓位大小: {adjusted_size:.2f} USDT")
        return adjusted_size
    
    def calculate_stop_loss_price(self, entry_price: float, position_side: PositionSide) -> float:
        """
        计算止损价格
        
        Args:
            entry_price: 入场价格
            position_side: 持仓方向
            
        Returns:
            止损价格
        """
        if position_side == PositionSide.LONG:
            return entry_price * (1 - self.stop_loss_percentage)
        else:
            return entry_price * (1 + self.stop_loss_percentage)
    
    def calculate_take_profit_price(self, entry_price: float, position_side: PositionSide) -> float:
        """
        计算止盈价格
        
        Args:
            entry_price: 入场价格
            position_side: 持仓方向
            
        Returns:
            止盈价格
        """
        if position_side == PositionSide.LONG:
            return entry_price * (1 + self.take_profit_percentage)
        else:
            return entry_price * (1 - self.take_profit_percentage)
    
    def should_force_close_position(self, position: Position, current_price: float) -> bool:
        """
        判断是否应该强制平仓
        
        Args:
            position: 当前持仓
            current_price: 当前价格
            
        Returns:
            是否应该强制平仓
        """
        # 计算当前盈亏比例
        if position.side == PositionSide.LONG:
            pnl_percentage = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_percentage = (position.entry_price - current_price) / position.entry_price
        
        # 检查止损
        if pnl_percentage <= -self.stop_loss_percentage:
            self.logger.warning(f"触发止损: 当前亏损 {pnl_percentage:.2%}")
            return True
        
        # 检查止盈
        if pnl_percentage >= self.take_profit_percentage:
            self.logger.info(f"触发止盈: 当前盈利 {pnl_percentage:.2%}")
            return True
        
        return False
    
    def record_trade(self, trade_info: Dict[str, Any]):
        """
        记录交易
        
        Args:
            trade_info: 交易信息
        """
        trade_info['timestamp'] = datetime.now()
        self.trade_history.append(trade_info)
        self.trades_today += 1
        
        # 更新PnL
        if 'pnl' in trade_info:
            self.daily_pnl += trade_info['pnl']
            self.total_pnl += trade_info['pnl']
        
        self.logger.info(f"记录交易: {trade_info}")
    
    def _check_risk_limits(self):
        """检查风险限制"""
        self.risk_alerts.clear()
        
        # 检查回撤
        if self.current_drawdown > self.max_drawdown_percentage * 0.8:
            alert = f"回撤警告: 当前回撤 {self.current_drawdown:.2%} 接近限制 {self.max_drawdown_percentage:.2%}"
            self.risk_alerts.append(alert)
            self.logger.warning(alert)
        
        # 检查日损失
        if self.daily_start_balance > 0:
            daily_loss_percentage = abs(self.daily_pnl) / self.daily_start_balance
            if self.daily_pnl < 0 and daily_loss_percentage > self.max_daily_loss_percentage * 0.8:
                alert = f"日损失警告: 当前损失 {daily_loss_percentage:.2%} 接近限制 {self.max_daily_loss_percentage:.2%}"
                self.risk_alerts.append(alert)
                self.logger.warning(alert)
        
        # 检查交易次数
        if self.trades_today > self.max_trades_per_day * 0.8:
            alert = f"交易次数警告: 今日交易 {self.trades_today} 次，接近限制 {self.max_trades_per_day} 次"
            self.risk_alerts.append(alert)
            self.logger.warning(alert)
    
    def reset_daily_stats(self):
        """重置日统计"""
        self.daily_start_balance = self.current_balance
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.risk_alerts.clear()
        self.logger.info("日统计已重置")
    
    def enable_trading(self):
        """启用交易"""
        self.trading_enabled = True
        self.logger.info("交易已启用")
    
    def disable_trading(self):
        """禁用交易"""
        self.trading_enabled = False
        self.logger.warning("交易已禁用")
    
    def get_risk_metrics(self) -> RiskMetrics:
        """获取风险指标"""
        winning_trades = sum(1 for trade in self.trade_history if trade.get('pnl', 0) > 0)
        losing_trades = len(self.trade_history) - winning_trades
        win_rate = winning_trades / len(self.trade_history) if self.trade_history else 0
        
        return RiskMetrics(
            max_drawdown=self.max_drawdown,
            current_drawdown=self.current_drawdown,
            win_rate=win_rate,
            profit_factor=0.0,  # 需要更复杂的计算
            sharpe_ratio=0.0,   # 需要更复杂的计算
            total_trades=len(self.trade_history),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=self.total_pnl,
            max_position_size=self.current_balance * self.max_position_percentage,
            current_exposure=0.0  # 需要从持仓信息计算
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取风险管理状态"""
        return {
            'trading_enabled': self.trading_enabled,
            'current_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'trades_today': self.trades_today,
            'max_trades_per_day': self.max_trades_per_day,
            'risk_alerts': self.risk_alerts,
            'risk_limits': {
                'max_position_percentage': self.max_position_percentage,
                'max_daily_loss_percentage': self.max_daily_loss_percentage,
                'max_drawdown_percentage': self.max_drawdown_percentage,
                'stop_loss_percentage': self.stop_loss_percentage,
                'take_profit_percentage': self.take_profit_percentage
            }
        }