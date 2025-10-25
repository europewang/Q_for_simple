# EMA交叉策略回测

基于EMA9和EMA26交叉信号的ETHUSDT交易策略回测系统。

## 策略说明

### 核心逻辑
- **做多信号**: 当EMA9上穿EMA26时（金叉），在收盘价做多
- **做空信号**: 当EMA9下穿EMA26时（死叉），在收盘价做空
- **平仓信号**: 在下一个EMA交叉信号时平仓并开新仓

### 交易参数
- **交易对**: ETHUSDT
- **K线周期**: 30分钟
- **每次交易金额**: 10 USDT
- **杠杆倍数**: 5倍
- **回测时间**: 2024年1月1日 - 2025年1月1日（一年）

### EMA参数
- **快线**: EMA9（9周期指数移动平均线）
- **慢线**: EMA26（26周期指数移动平均线）

## 文件说明

- `ema_crossover_strategy.py`: 主策略文件，包含完整的回测逻辑
- `requirements.txt`: 项目依赖包
- `ema_strategy_results/`: 回测结果目录
  - `backtest_report.txt`: 详细回测报告
  - `trades_record.csv`: 交易记录明细
  - `kline_data_with_ema.csv`: 带EMA指标的K线数据

## 运行方法

1. 激活conda环境：
```bash
conda activate quant
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行回测：
```bash
python /home/ubuntu/Code/quant/backtest_for_ema_Martin_strategy/ema_crossover_strategy.py
```

## 输出结果

回测完成后会生成：

1. **控制台输出**: 实时交易信息和最终报告
2. **backtest_report.txt**: 包含详细的绩效指标
3. **trades_record.csv**: 每笔交易的详细记录
4. **kline_data_with_ema.csv**: 历史K线数据和EMA指标

## 关键指标

- **总交易次数**: 一年内的交易频次
- **胜率**: 盈利交易占比
- **盈亏比**: 平均盈利/平均亏损
- **总收益率**: 最终收益百分比
- **最终收益**: 一年后的绝对收益金额

## 注意事项

- 策略使用Binance API获取实时数据
- 交易手续费未计入回测（实际交易需考虑）
- 滑点影响未计入回测
- 杠杆交易存在爆仓风险，实际使用需谨慎