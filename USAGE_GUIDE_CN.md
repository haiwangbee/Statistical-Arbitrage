# 加密货币统计套利系统 - 使用指南

## 📋 目录
1. [系统简介](#系统简介)
2. [快速开始](#快速开始)
3. [详细使用步骤](#详细使用步骤)
4. [配置说明](#配置说明)
5. [策略原理](#策略原理)
6. [常见问题](#常见问题)

## 系统简介

这是一个基于统计套利的加密货币交易策略回测系统，核心特性：

- **自动数据获取**: 从Binance下载历史K线数据
- **协整检验**: 使用Engle-Granger方法寻找统计套利机会
- **智能优化**: 自动优化交易阈值
- **完整回测**: 包含持仓管理、PnL计算、风险指标等
- **可视化报告**: 自动生成图表和性能报告

## 快速开始

### 第一步：安装依赖

```bash
cd /Users/houbo/Documents/code/crypto/Statistical-Arbitrage
pip install -r requirements_crypto.txt
```

### 第二步：运行快速示例

```bash
# 方式1: 使用主程序（推荐）
python crypto_main.py

# 方式2: 使用快速开始脚本
python quick_start.py
```

### 第三步：查看结果

结果保存在 `results/crypto/` 目录下：
- `metrics.csv` - 性能指标
- `pnl.csv` - 损益记录
- `cumulative_pnl.png` - PnL曲线图
- 更多...

## 详细使用步骤

### 1. 准备配置文件

编辑 `config.yaml`，设置你的策略参数：

```yaml
# 示例配置
data:
  source: 'auto'          # 自动选择高流动性币对
  auto:
    quote_asset: 'USDT'
    top_n: 15             # 选择前15个
  timeframe:
    interval: '1h'        # 1小时K线
    start_time: '2024-01-01'
    end_time: null        # 到当前时间

strategy:
  cointegration:
    pvalue_threshold: 0.01  # 严格的协整检验
  threshold:
    mode: 'optimize'        # 自动优化阈值
  pair_selection:
    max_pairs: 5           # 最多5个交易对
    no_overlap: true       # 避免资产重叠

backtest:
  initial_capital: 100000.0
  max_position_size: 10000.0
```

### 2. 运行回测

```bash
# 完整运行（下载数据+回测）
python crypto_main.py

# 使用已有数据（跳过下载）
python crypto_main.py --skip-download

# 使用自定义配置
python crypto_main.py --config my_config.yaml
```

### 3. 分析结果

程序会输出详细的回测报告：

```
回测结果摘要
============================================================
初始资金:        $100,000.00
最终资金:        $115,234.56
总收益:          $15,234.56
收益率:          15.23%
最大回撤:        $-3,456.78 (-3.46%)
夏普比率:        1.234
胜率:            65.42%
...
```

### 4. 查看图表

系统自动生成以下图表：

1. **累计PnL曲线** (`cumulative_pnl.png`)
   - 总体收益曲线
   - 各交易对收益曲线

2. **持仓变化图** (`position_*.png`)
   - 每个交易对的持仓变化

3. **回撤曲线** (`drawdown.png`)
   - 资金回撤情况

## 配置说明

### 数据源选择

#### 自动模式（推荐）
```yaml
data:
  source: 'auto'
  auto:
    quote_asset: 'USDT'  # 或 'BTC', 'ETH'
    top_n: 15            # 交易量前N个
```

系统会自动获取交易量最大的N个交易对，确保流动性。

#### 手动模式
```yaml
data:
  source: 'manual'
  manual:
    symbols:
      - 'BTCUSDT'
      - 'ETHUSDT'
      - 'BNBUSDT'
      # ... 添加更多
```

适合想要测试特定交易对的情况。

### 时间范围选择

```yaml
timeframe:
  interval: '1h'           # 支持: 1m, 5m, 15m, 1h, 4h, 1d
  start_time: '2024-01-01' # YYYY-MM-DD 格式
  end_time: '2024-06-30'   # null表示当前时间
```

**建议**:
- 短期测试: 1-3个月，1h间隔
- 长期回测: 6-12个月，4h间隔
- 数据越多，协整检验越可靠

### 策略参数

#### 协整检验参数
```yaml
cointegration:
  pvalue_threshold: 0.01  # 0.01=严格, 0.05=宽松
  min_half_life: 1        # 最小半衰期（小时）
  max_half_life: 168      # 最大半衰期（1周）
```

**说明**:
- p值越小，协整关系越强，但可能找到的交易对越少
- 半衰期表示价差回归均值的速度
- 半衰期太短: 噪音交易多
- 半衰期太长: 持仓时间长，资金利用率低

#### 阈值设置

**优化模式**（推荐）:
```yaml
threshold:
  mode: 'optimize'
  optimize:
    min_sigma: 0.5   # 最小0.5倍标准差
    max_sigma: 3.0   # 最大3倍标准差
    num_steps: 10    # 测试10个点
```

系统会测试不同阈值，选择PnL最高的。

**固定模式**:
```yaml
threshold:
  mode: 'fixed'
  fixed:
    sigma_multiplier: 1.96  # 固定使用1.96倍标准差
```

适合有经验的用户。

#### 交易对选择

```yaml
pair_selection:
  method: 'top_pnl'       # 或 'diversified'
  max_pairs: 5            # 最多交易对数量
  no_overlap: true        # 是否避免同一币种出现在多个对中
```

**no_overlap=true** (推荐):
- 避免过度集中在某个币种
- 提高组合多样性

**no_overlap=false**:
- 可能获得更高收益
- 风险更集中

### 回测参数

```yaml
backtest:
  initial_capital: 100000.0      # 初始资金
  max_position_size: 10000.0     # 单个交易对最大持仓
  commission_rate: 0.001         # 手续费 0.1%
  slippage_rate: 0.0005          # 滑点 0.05%
```

**建议**:
- `max_position_size` = 5-10% 的总资金
- Binance现货手续费: Maker 0.1%, Taker 0.1%
- 使用BNB抵扣可降至0.075%

## 策略原理

### 配对交易 (Pairs Trading)

配对交易是一种市场中性策略，通过交易两个相关资产的价差来获利。

### 协整关系

两个资产价格存在长期均衡关系：

```
log(Price_A) = c + γ * log(Price_B) + z_t
```

其中:
- `γ` 是对冲比率
- `z_t` 是误差修正项（价差）

当价差偏离均值时，预期会回归，这就是交易机会。

### 交易信号

```
如果 z_t > +threshold:
    做空A，做多B（认为价差会缩小）

如果 z_t < -threshold:
    做多A，做空B（认为价差会扩大）

如果 z_t 接近 0:
    平仓获利
```

### 风险控制

1. **协整检验**: 确保长期均衡关系存在
2. **半衰期筛选**: 确保价差回归速度合理
3. **阈值优化**: 平衡交易频率和盈利
4. **分散投资**: 多个交易对降低风险
5. **持仓限制**: 控制单一交易对风险

## 进阶使用

### 使用Python API

可以直接导入模块进行定制化开发：

```python
from crypto_utils import BinanceDataDownloader, CryptoStatArbStrategy, BacktestEngine

# 下载数据
downloader = BinanceDataDownloader()
data = downloader.prepare_pairs_data(
    symbols=['BTCUSDT', 'ETHUSDT'],
    interval='1h',
    start_time='2024-01-01'
)

# 初始化策略
strategy = CryptoStatArbStrategy(data)

# 寻找协整对
pairs = strategy.find_cointegrated_pairs(pvalue_threshold=0.01)

# 可视化
strategy.visualize_pair(pairs.index[0])

# 回测
engine = BacktestEngine(data)
results = engine.run_backtest(pairs_config, strategy)
```

### 参数调优技巧

#### 提高收益
- 增加交易对数量（`top_n`, `max_pairs`）
- 放宽协整检验（`pvalue_threshold=0.05`）
- 降低交易阈值（更频繁交易）

#### 降低风险
- 严格协整检验（`pvalue_threshold=0.01`）
- 提高交易阈值（减少噪音交易）
- 启用资产不重叠（`no_overlap=true`）
- 增加半衰期限制

#### 提高夏普比率
- 优化阈值而非使用固定值
- 筛选半衰期合理的交易对
- 选择流动性好的币种

### 不同市场环境

#### 震荡市（推荐）
统计套利最适合震荡市：
```yaml
strategy:
  cointegration:
    pvalue_threshold: 0.01
  threshold:
    mode: 'optimize'
```

#### 趋势市
趋势市中协整关系可能短暂失效：
```yaml
strategy:
  cointegration:
    pvalue_threshold: 0.005  # 更严格
    max_half_life: 72        # 更短的半衰期
```

## 常见问题

### Q1: 为什么找不到协整交易对？

**可能原因**:
1. 数据不够长（建议至少1个月）
2. p值阈值太严格
3. 所选币种相关性不强

**解决方案**:
```yaml
# 尝试放宽参数
cointegration:
  pvalue_threshold: 0.05  # 从0.01改为0.05

# 或增加交易对数量
auto:
  top_n: 20  # 从15改为20
```

### Q2: 回测收益为负怎么办？

**分析步骤**:
1. 检查交易次数（过多可能是阈值太小）
2. 检查持仓时间（过长可能是半衰期太大）
3. 查看最大回撤（过大说明风险控制不足）

**优化方向**:
```yaml
# 减少交易次数
threshold:
  optimize:
    min_sigma: 1.0  # 从0.5提高到1.0

# 限制半衰期
cointegration:
  max_half_life: 48  # 限制在2天内
```

### Q3: 数据下载很慢或失败？

**解决方案**:
1. 检查网络连接
2. 减少交易对数量
3. 缩短时间范围
4. 使用已下载的数据：
   ```bash
   python crypto_main.py --skip-download
   ```

### Q4: 实盘和回测差异大？

**常见原因**:
1. 滑点: 回测使用固定滑点，实盘可能更大
2. 手续费: 确认实际费率
3. 成交量: 回测假设完全成交
4. 延迟: 实盘有网络和处理延迟

**建议**:
```yaml
# 保守估计
backtest:
  commission_rate: 0.002  # 提高到0.2%
  slippage_rate: 0.001    # 提高到0.1%
```

### Q5: 如何选择K线间隔？

| 间隔 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 1m-5m | 高频交易 | 机会多 | 噪音大，手续费高 |
| 15m-1h | 日内交易 | 平衡 | 需要实时监控 |
| 4h-1d | 中长线 | 稳定 | 机会少，资金占用长 |

**推荐**: 从1h开始测试。

### Q6: 多少初始资金合适？

**最小建议**: $10,000
- 5个交易对 × $2,000每对

**理想建议**: $50,000-$100,000
- 更好的分散
- 更灵活的仓位管理

### Q7: 如何评估策略好坏？

关键指标:
1. **夏普比率** > 1.0（好）, > 2.0（优秀）
2. **最大回撤** < -20%（可接受）
3. **胜率** > 50%
4. **盈亏比** > 1.5

### Q8: 可以用于实盘交易吗？

当前版本主要是回测框架。实盘交易需要：
1. 实时数据流
2. 订单执行模块
3. 风险监控
4. 异常处理

**建议**: 先用历史数据充分测试，确认策略稳定后再考虑实盘。

## 性能优化

### 加速数据下载
```python
# 在binance_data.py中调整
time.sleep(0.5)  # 改为0.2（但注意API限制）
```

### 并行处理
系统已使用joblib并行处理阈值优化，如需更多并行：
```yaml
# 在strategy中调整
n_jobs: -1  # 使用所有CPU核心
```

### 内存优化
处理大量数据时：
```python
# 只保留必要列
data = data[['BidPrice', 'AskPrice', 'MidPrice', 'Volume']]
```

## 总结

这个系统提供了一个完整的加密货币统计套利回测框架。通过调整配置参数，可以适应不同的市场环境和交易风格。

**关键要点**:
1. ✅ 数据质量决定策略质量
2. ✅ 协整检验是策略基础
3. ✅ 阈值优化提高收益
4. ✅ 风险控制至关重要
5. ✅ 回测不等于实盘

**下一步**:
1. 运行快速示例熟悉系统
2. 尝试不同配置参数
3. 分析回测结果
4. 优化策略细节
5. 考虑实盘前的准备

祝交易顺利! 🚀

