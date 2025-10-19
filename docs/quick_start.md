# 快速开始指南

本指南将帮助您快速设置和运行MyQuant量化交易系统。

## 📋 前置要求

### 系统要求
- **操作系统**: Windows 10/11, macOS 10.14+, 或 Linux
- **Python版本**: 3.8 或更高版本
- **内存**: 至少 4GB RAM（推荐 8GB+）
- **存储**: 至少 2GB 可用空间

### 账户要求
- **Binance账户** (用于实时交易)
- **API密钥** (如需实盘交易)

## 🚀 安装步骤

### 1. 下载项目

```bash
# 克隆项目（如果使用Git）
git clone <repository-url>
cd myquant1008

# 或者直接下载ZIP文件并解压
```

### 2. 创建Python虚拟环境

**Windows PowerShell:**
```powershell
# 创建虚拟环境
python -m venv myquant

# 激活虚拟环境
myquant\Scripts\Activate.ps1

# 如果遇到执行策略错误，运行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Linux/macOS:**
```bash
# 创建虚拟环境
python3 -m venv myquant

# 激活虚拟环境
source myquant/bin/activate
```

### 3. 安装依赖包

```bash
# 升级pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

**常见安装问题解决:**

如果遇到某些包安装失败，可以尝试：

```bash
# 分别安装核心包
pip install pandas numpy matplotlib
pip install python-binance ccxt
pip install flask flask-socketio

# 可选包（如果需要Web监控）
pip install psutil plotly
```

## ⚙️ 配置设置

### 1. 基础配置

编辑 `live_trading/config/live_trading_config.json` 文件：

```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "simulation_mode": true,
    "initial_balance": 10000.0,
    "leverage": 1
  },
  "strategy": {
    "name": "SimpleEMAStrategy",
    "fast_ema_period": 12,
    "slow_ema_period": 26,
    "signal_threshold": 0.001
  },
  "risk_management": {
    "max_position_percentage": 0.1,
    "stop_loss_percentage": 0.02,
    "take_profit_percentage": 0.04,
    "max_daily_loss_percentage": 0.05
  },
  "exchange": {
    "name": "binance",
    "api_key": "",
    "api_secret": "",
    "testnet": true
  },
  "data_feed": {
    "source": "mock",
    "update_interval": 1
  }
}
```

### 2. API密钥配置（实盘交易）

**重要**: 仅在需要实盘交易时配置API密钥

1. 登录 [Binance](https://www.binance.com)
2. 进入 API管理 页面
3. 创建新的API密钥
4. 设置权限：现货交易、期货交易（根据需要）
5. 将API密钥填入配置文件

**安全提示:**
- 不要在代码中硬编码API密钥
- 使用IP白名单限制API访问
- 定期更换API密钥
- 测试时使用测试网

## 🏃‍♂️ 运行系统

### 1. 运行回测

```bash
# 进入回测目录
cd backtest

# 运行简单回测
python run_backtest.py

# 查看回测结果
# 结果将保存在 backtest/results/ 目录中
```

### 2. 启动实时交易系统

```bash
# 进入实时交易目录
cd live_trading

# 演示模式（推荐首次使用）
python start_trading.py --mode demo

# 测试网模式（使用Binance测试网）
python start_trading.py --mode test

# 检查配置文件
python start_trading.py --check-config

# 实盘模式（谨慎使用！）
python start_trading.py --mode live
```

### 3. 访问监控界面

启动交易系统后，打开浏览器访问：

```
http://localhost:5000
```

监控界面提供：
- 实时系统状态
- 账户余额和持仓
- 交易历史和统计
- 风险指标监控
- 价格图表

## 📊 第一次运行

### 演示模式运行

1. **启动演示模式**
```bash
cd live_trading
python start_trading.py --mode demo
```

2. **观察输出**
```
╔══════════════════════════════════════════════════════════════╗
║                    实时量化交易系统                          ║
║                   Live Trading System                        ║
║                                                              ║
║  版本: 1.0.0                                                 ║
║  作者: MyQuant Team                                          ║
║  时间: 2024-01-15 10:30:00                                   ║
╚══════════════════════════════════════════════════════════════╝

启动演示模式（模拟交易）

配置摘要:
==================================================
交易对: BTCUSDT
模拟模式: 是
初始余额: 10000.00 USDT
策略: SimpleEMAStrategy
快速EMA: 12
慢速EMA: 26
最大仓位比例: 10.0%
止损比例: 2.0%
止盈比例: 4.0%
数据源: mock
交易所: mock
==================================================

正在启动交易系统...
按 Ctrl+C 停止交易系统
--------------------------------------------------
```

3. **打开监控界面**
   - 浏览器访问 http://localhost:5000
   - 观察实时数据更新
   - 查看模拟交易信号

### 回测运行

1. **运行回测**
```bash
cd backtest
python run_backtest.py
```

2. **查看结果**
   - 回测报告将显示在终端
   - 图表将保存在 `backtest/results/` 目录
   - 详细数据保存为CSV文件

## 🔧 常见问题

### 安装问题

**Q: pip install 失败**
```bash
# 尝试使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 或者分别安装核心包
pip install pandas numpy matplotlib python-binance
```

**Q: PowerShell执行策略错误**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 运行问题

**Q: 模块导入错误**
```bash
# 确保在项目根目录运行
cd myquant1008

# 确保虚拟环境已激活
# Windows: myquant\Scripts\Activate.ps1
# Linux/macOS: source myquant/bin/activate
```

**Q: 配置文件错误**
```bash
# 检查配置文件语法
python start_trading.py --check-config

# 使用默认配置
# 删除配置文件，系统会自动创建默认配置
```

**Q: 网络连接问题**
```json
// 在配置文件中设置代理（如需要）
{
  "data_feed": {
    "source": "mock",  // 使用模拟数据避免网络问题
    "proxy": "http://proxy:port"
  }
}
```

### 交易问题

**Q: API密钥错误**
- 检查API密钥是否正确
- 确认API权限设置
- 使用测试网进行测试

**Q: 余额不足**
- 检查账户余额
- 调整仓位大小设置
- 使用模拟模式进行测试

## 📈 下一步

完成快速开始后，您可以：

1. **学习策略开发**: 阅读 [策略开发指南](strategy_development.md)
2. **深入配置**: 查看 [配置说明](configuration.md)
3. **API参考**: 浏览 [API文档](api_reference.md)
4. **自定义策略**: 开发您自己的交易策略
5. **风险管理**: 了解风险控制机制

## 🆘 获取帮助

如果遇到问题：

1. **查看日志**: 检查 `logs/` 目录中的日志文件
2. **常见问题**: 阅读 [FAQ](faq.md)
3. **社区支持**: 在GitHub Issues中提问
4. **联系我们**: 发送邮件到 support@myquant.com

---

**祝您交易愉快！** 🚀

> **风险提示**: 量化交易存在风险，请在充分了解和测试后再进行实盘交易。