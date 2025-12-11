# 加密货币统计套利系统

基于配对交易(Pairs Trading)的加密货币统计套利策略回测框架，支持Binance交易所历史数据下载和回测。

## 特性

- ✅ **Binance数据集成**: 自动下载历史K线数据
- ✅ **协整检验**: Engle-Granger协整检验寻找统计套利机会
- ✅ **阈值优化**: 自动优化交易阈值以最大化收益
- ✅ **完整回测**: 包含持仓、PnL、回撤等完整指标
- ✅ **可视化**: 自动生成各类图表
- ✅ **配置化**: YAML配置文件，灵活调整策略参数

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_crypto.txt
```

### 2. 配置策略

编辑 `config.yaml` 文件，设置：
- 交易对选择方式（自动/手动）
- 时间范围和K线间隔
- 策略参数（协整阈值、交易阈值等）
- 回测参数（初始资金、最大持仓等）

### 3. 运行回测

```bash
# 完整运行（下载数据+回测）
python crypto_main.py

# 使用自定义配置文件
python crypto_main.py --config my_config.yaml

# 跳过数据下载，使用已有数据
python crypto_main.py --skip-download

# 使用指定数据文件
python crypto_main.py --data-file ./data/crypto/market_data_1h.csv
```

## 配置说明

### 数据配置

```yaml
data:
  source: 'auto'  # 'auto' 自动获取高交易量币对, 'manual' 手动指定
  
  auto:
    quote_asset: 'USDT'  # 计价货币
    top_n: 15            # 获取交易量前N个
  
  manual:
    symbols:
      - 'BTCUSDT'
      - 'ETHUSDT'
      # ... 更多交易对
  
  timeframe:
    interval: '1h'           # K线间隔: 1m, 5m, 15m, 1h, 4h, 1d
    start_time: '2024-01-01' # 开始时间
    end_time: null           # 结束时间（null=现在）
```

### 策略配置

```yaml
strategy:
  # 协整检验
  cointegration:
    pvalue_threshold: 0.01  # p值阈值（越小越严格）
    min_half_life: 1        # 最小半衰期（小时）
    max_half_life: 168      # 最大半衰期（1周）
  
  # 阈值优化
  threshold:
    mode: 'optimize'        # 'optimize' 优化, 'fixed' 固定
    optimize:
      min_sigma: 0.5        # 最小阈值倍数
      max_sigma: 3.0        # 最大阈值倍数
      num_steps: 10         # 优化步数
  
  # 交易对选择
  pair_selection:
    method: 'top_pnl'       # 'top_pnl' 按收益, 'diversified' 分散
    max_pairs: 5            # 最大交易对数量
    no_overlap: true        # 避免资产重叠
```

### 回测配置

```yaml
backtest:
  initial_capital: 100000.0      # 初始资金
  max_position_size: 10000.0     # 单对最大持仓
  commission_rate: 0.001         # 手续费率
  slippage_rate: 0.0005          # 滑点率
```

## 策略原理

### 1. 协整检验

使用Engle-Granger两步法检验交易对的协整关系：

1. **长期关系**: `y_t = c + γ * x_t + z_t`
2. **误差修正**: 对残差 `z_t` 进行ADF检验

### 2. 交易信号

基于误差修正项（z-value）的均值回归特性：

- **开多仓**: 当 `z < -threshold` 时，做多资产1，做空资产2
- **开空仓**: 当 `z > threshold` 时，做空资产1，做多资产2  
- **平仓**: 当 `z` 回归到0附近时平仓

### 3. 对冲比率

使用协整回归系数 `γ` 作为对冲比率，确保组合的统计套利特性。

## 目录结构

```
.
├── config.yaml                # 配置文件
├── crypto_main.py            # 主程序入口
├── requirements_crypto.txt   # 依赖包
├── crypto_utils/            # 工具模块
│   ├── __init__.py
│   ├── binance_data.py      # Binance数据下载
│   ├── crypto_arb_strategy.py  # 统计套利策略
│   └── backtest_engine.py   # 回测引擎
├── data/crypto/             # 数据存储
├── results/crypto/          # 回测结果
└── logs/                    # 日志文件
```

## 输出结果

运行完成后，在 `results/crypto/` 目录下生成：

### 数据文件
- `positions.csv`: 持仓记录
- `pnl.csv`: 损益记录
- `metrics.csv`: 性能指标
- `pair_results.csv`: 各交易对表现

### 图表
- `cumulative_pnl.png`: 累计PnL曲线
- `position_*.png`: 各交易对持仓图
- `drawdown.png`: 回撤曲线

### 性能指标
- 总收益 / 收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比
- 等等...

## 使用示例

### 示例1: 快速回测主流币对

```yaml
# config.yaml
data:
  source: 'manual'
  manual:
    symbols: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
  timeframe:
    interval: '1h'
    start_time: '2024-01-01'
    end_time: '2024-06-30'

strategy:
  cointegration:
    pvalue_threshold: 0.05
  threshold:
    mode: 'fixed'
    fixed:
      sigma_multiplier: 2.0
  pair_selection:
    max_pairs: 2
```

```bash
python crypto_main.py
```

### 示例2: 自动选择高流动性币对

```yaml
# config.yaml
data:
  source: 'auto'
  auto:
    quote_asset: 'USDT'
    top_n: 20
  timeframe:
    interval: '4h'
    start_time: '2024-01-01'

strategy:
  cointegration:
    pvalue_threshold: 0.01
  threshold:
    mode: 'optimize'
  pair_selection:
    method: 'top_pnl'
    max_pairs: 5
    no_overlap: true
```

```bash
python crypto_main.py
```

## 模块说明

### BinanceDataDownloader

下载Binance历史数据：

```python
from crypto_utils import BinanceDataDownloader

downloader = BinanceDataDownloader()

# 获取热门交易对
symbols = downloader.get_top_volume_pairs('USDT', top_n=10)

# 下载数据
data = downloader.prepare_pairs_data(
    symbols=symbols,
    interval='1h',
    start_time='2024-01-01'
)
```

### CryptoStatArbStrategy

统计套利策略：

```python
from crypto_utils import CryptoStatArbStrategy

strategy = CryptoStatArbStrategy(market_data)

# 寻找协整交易对
pairs = strategy.find_cointegrated_pairs(pvalue_threshold=0.01)

# 优化阈值
threshold_results = strategy.optimize_threshold(
    pair=('BTCUSDT', 'ETHUSDT'),
    gamma=0.5,
    std=0.001
)

# 可视化
strategy.visualize_pair(('BTCUSDT', 'ETHUSDT'))
```

### BacktestEngine

回测引擎：

```python
from crypto_utils import BacktestEngine

engine = BacktestEngine(
    market_data=market_data,
    initial_capital=100000.0
)

# 运行回测
results = engine.run_backtest(pairs_config, strategy)

# 绘制结果
engine.plot_results(save_dir='./results')

# 导出数据
engine.export_results('./results')
```

## 注意事项

1. **数据质量**: 确保网络连接稳定，Binance API可访问
2. **计算资源**: 大量交易对的协整检验和阈值优化需要较多时间
3. **参数调优**: 不同市场环境下最优参数可能不同，需要反复测试
4. **滑点与手续费**: 回测结果已考虑但实盘可能有差异
5. **风险控制**: 统计套利仍有风险，建议设置止损

## 进阶功能

### 实盘交易（开发中）

配置Binance API密钥后可用于实盘交易：

```yaml
binance:
  api_key: 'your_api_key'
  api_secret: 'your_api_secret'
  testnet: true  # 先用测试网
```

### 实时监控（开发中）

实时监控协整关系和交易信号。

## 常见问题

**Q: 为什么找不到协整交易对？**

A: 尝试：
- 增加交易对数量
- 放宽p值阈值（如改为0.05）
- 使用更长的历史数据
- 调整K线间隔

**Q: 回测收益为负怎么办？**

A: 可能原因：
- 市场环境不适合统计套利
- 阈值设置不当
- 手续费和滑点过高
- 交易对选择不合适

尝试优化参数或更换时间段。

**Q: 数据下载失败？**

A: 检查：
- 网络连接
- Binance API是否可访问
- 时间范围是否合理
- 是否需要使用代理

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题，请提交Issue。

