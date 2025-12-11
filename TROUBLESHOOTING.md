# 故障排除指南

## 常见问题和解决方案

### 1. NaN值问题

#### 症状
```
WARNING:crypto_utils.crypto_arb_strategy:处理交易对 ASTERUSDT-BNBUSDT 时出错: y包含NaN值
```

#### 原因
某些新上市的交易对在早期时间段没有数据，导致价格序列中包含NaN值。

#### 解决方案

**方案1: 自动过滤（已实现）**

最新版本已经自动处理NaN问题：
- 数据下载时自动剔除NaN超过10%的交易对
- 协整检验时自动清理NaN值
- 剩余少量NaN使用前向/后向填充

无需手动操作。

**方案2: 调整时间范围**

如果某个币种是新上市的：
```yaml
# config.yaml
data:
  timeframe:
    start_time: '2024-06-01'  # 改为更晚的日期
```

**方案3: 手动排除问题币种**

```yaml
# config.yaml  
data:
  source: 'manual'
  manual:
    symbols:
      - 'BTCUSDT'
      - 'ETHUSDT'
      # 不包含ASTERUSDT
```

**方案4: 检查数据质量**

运行程序时会自动报告数据质量：
```
WARNING:crypto_utils.crypto_arb_strategy:ASTERUSDT 包含 15000 个NaN值 (90.12%)
INFO:crypto_utils.binance_data:保留 14/15 个交易对
```

---

### 2. statsmodels警告

#### 症状
```
ValueWarning: unknown kwargs ['has_const']
```

#### 原因
较新版本的statsmodels不再接受`has_const`参数。

#### 解决方案

**已修复** - 最新版本已移除该参数。

如果仍然看到此警告，请更新代码：

```python
# 旧代码
long_run_ols = OLS(y, add_constant(x), has_const=True)

# 新代码
long_run_ols = OLS(y, add_constant(x))
```

或者降级statsmodels版本：
```bash
pip install statsmodels==0.12.2
```

---

### 3. 找不到协整交易对

#### 症状
```
INFO:__main__:找到 0 个协整交易对
ERROR:__main__:未找到协整交易对，请调整参数或更换交易对
```

#### 原因
1. p值阈值设置过于严格
2. 数据时间范围不够长
3. 所选交易对相关性不强
4. 市场处于强趋势期，协整关系减弱

#### 解决方案

**方案1: 放宽p值阈值**
```yaml
# config.yaml
strategy:
  cointegration:
    pvalue_threshold: 0.05  # 从0.01改为0.05
```

**方案2: 延长数据时间**
```yaml
data:
  timeframe:
    start_time: '2023-01-01'  # 使用更长的历史数据
```

**方案3: 增加交易对数量**
```yaml
data:
  auto:
    top_n: 30  # 从15增加到30
```

**方案4: 选择相关性强的币种**
```yaml
data:
  source: 'manual'
  manual:
    symbols:
      # Layer1公链（相关性强）
      - 'ETHUSDT'
      - 'BNBUSDT'
      - 'SOLUSDT'
      - 'AVAXUSDT'
      - 'DOTUSDT'
      # 或DeFi代币
      - 'UNIUSDT'
      - 'AAVEUSDT'
      - 'LINKUSDT'
```

---

### 4. 数据下载失败

#### 症状
```
ERROR:crypto_utils.binance_data:下载数据失败: Connection timeout
```

#### 原因
1. 网络连接问题
2. Binance API访问受限
3. API请求过快被限流

#### 解决方案

**方案1: 检查网络**
```bash
# 测试连接
ping api.binance.com
curl https://api.binance.com/api/v3/ping
```

**方案2: 使用代理**
```python
# 在binance_data.py中
import os
os.environ['HTTP_PROXY'] = 'http://your-proxy:port'
os.environ['HTTPS_PROXY'] = 'http://your-proxy:port'
```

**方案3: 降低请求速度**
```python
# 在binance_data.py的download_multiple_symbols方法中
time.sleep(1.0)  # 从0.5改为1.0
```

**方案4: 使用已下载的数据**
```bash
# 如果之前下载成功过
python crypto_main.py --skip-download
```

---

### 5. 回测收益为负

#### 症状
回测结果显示亏损。

#### 原因
1. 策略参数不适合当前市场
2. 手续费和滑点设置过高
3. 阈值设置不当
4. 选择的时间段不适合统计套利

#### 解决方案

**方案1: 优化阈值**
```yaml
strategy:
  threshold:
    mode: 'optimize'  # 使用优化模式
    optimize:
      min_sigma: 0.8
      max_sigma: 2.5
```

**方案2: 调整成本**
```yaml
backtest:
  commission_rate: 0.0005  # 如果使用BNB抵扣
  slippage_rate: 0.0003    # 降低滑点
```

**方案3: 更严格的协整检验**
```yaml
strategy:
  cointegration:
    pvalue_threshold: 0.005  # 更严格
    min_half_life: 2
    max_half_life: 72        # 更短的半衰期
```

**方案4: 选择不同时间段**
```yaml
# 统计套利更适合震荡市
data:
  timeframe:
    start_time: '2024-03-01'  # 尝试不同时段
    end_time: '2024-06-30'
```

---

### 6. 内存不足

#### 症状
```
MemoryError: Unable to allocate array
```

#### 原因
处理大量交易对和长时间数据时内存占用过大。

#### 解决方案

**方案1: 减少交易对数量**
```yaml
data:
  auto:
    top_n: 10  # 减少到10个
```

**方案2: 缩短时间范围**
```yaml
data:
  timeframe:
    start_time: '2024-06-01'  # 只用半年数据
```

**方案3: 使用更大的K线间隔**
```yaml
data:
  timeframe:
    interval: '4h'  # 从1h改为4h
```

**方案4: 分批处理**
```python
# 修改crypto_main.py，分批处理交易对
symbols = downloader.get_top_volume_pairs(top_n=30)
for batch in [symbols[i:i+10] for i in range(0, len(symbols), 10)]:
    # 处理每批10个
    pass
```

---

### 7. 程序运行很慢

#### 原因
1. 下载大量数据
2. 协整检验计算密集
3. 阈值优化遍历多个参数

#### 解决方案

**方案1: 使用缓存数据**
```bash
python crypto_main.py --skip-download
```

**方案2: 减少优化步数**
```yaml
strategy:
  threshold:
    optimize:
      num_steps: 5  # 从10减少到5
```

**方案3: 限制交易对数量**
```yaml
strategy:
  pair_selection:
    max_pairs: 3  # 减少最终交易对数量
```

**方案4: 并行处理（已实现）**
系统已使用joblib并行处理，无需额外设置。

---

### 8. 图表不显示中文

#### 症状
图表中的中文显示为方框。

#### 解决方案

**方案1: 安装中文字体**
```bash
# macOS
brew install font-noto-sans-cjk

# Linux
sudo apt-get install fonts-noto-cjk
```

**方案2: 修改matplotlib配置**
```python
# 在代码开头添加
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS
# 或
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows
plt.rcParams['axes.unicode_minus'] = False
```

**方案3: 使用英文**
修改代码中的中文标签为英文。

---

### 9. Pandas警告

#### 症状
```
FutureWarning: DataFrame.fillna with 'method' is deprecated
```

#### 解决方案

**已修复** - 最新版本会处理此问题。

如果使用的是pandas 2.0+：
```python
# 旧代码
df.fillna(method='ffill')

# 新代码
df.ffill()
```

---

### 10. Pandas索引访问错误

#### 症状
```
AssertionError
  File "crypto_arb_strategy.py", line 232, in calculate_trading_metrics
    alpha = self.tradable_pairs.loc[pair, 'Alpha']
```

#### 原因
使用`.loc`访问多层索引DataFrame时，在某些pandas版本中可能出现维度断言错误。

#### 解决方案

**已修复** - 最新版本已使用`.at`代替`.loc`进行标量访问。

如果仍然遇到此问题：

```python
# 旧代码（可能出错）
value = df.loc[pair, 'Column']

# 新代码（推荐）
value = df.at[pair, 'Column']

# 或使用try-except
try:
    value = df.at[pair, 'Column']
except:
    pair_idx = df.index.get_loc(pair)
    if isinstance(pair_idx, slice):
        pair_idx = pair_idx.start
    value = df.iloc[pair_idx]['Column']
```

**说明**:
- `.at`: 用于访问单个标量值（推荐）
- `.loc`: 用于切片或多值访问
- `.iloc`: 用于基于位置的访问

---

### 11. 找不到模块

#### 症状
```
ModuleNotFoundError: No module named 'crypto_utils'
```

#### 原因
Python路径问题。

#### 解决方案

**方案1: 在项目根目录运行**
```bash
cd /Users/houbo/Documents/code/crypto/Statistical-Arbitrage
python crypto_main.py
```

**方案2: 设置PYTHONPATH**
```bash
export PYTHONPATH=/Users/houbo/Documents/code/crypto/Statistical-Arbitrage:$PYTHONPATH
python crypto_main.py
```

**方案3: 安装为包**
```bash
pip install -e .
```

---

## 调试技巧

### 1. 启用详细日志
```yaml
# config.yaml
logging:
  level: 'DEBUG'  # 改为DEBUG级别
```

### 2. 查看日志文件
```bash
tail -f logs/crypto_arb.log
```

### 3. Python调试
```python
# 在出错位置添加
import pdb; pdb.set_trace()
```

### 4. 检查数据质量
```python
# 在Python中
import pandas as pd
data = pd.read_csv('data/crypto/market_data_1h.csv', header=[0,1], index_col=0)
print(data.isnull().sum())  # 查看NaN统计
```

### 5. 单独测试模块
```python
from crypto_utils import BinanceDataDownloader

downloader = BinanceDataDownloader()
# 测试单个功能
```

---

## 性能优化建议

### 1. 数据层面
- 使用4h或1d间隔而非1h
- 限制历史数据长度（6-12个月）
- 减少交易对数量（10-15个）

### 2. 计算层面
- 阈值优化减少步数
- 限制最终交易对数量
- 使用已下载的数据

### 3. 系统层面
- 确保足够的内存（建议8GB+）
- 使用SSD存储
- 关闭不必要的后台程序

---

## 数据质量检查清单

在运行回测前，检查：

- [ ] 所有交易对的NaN比例 < 10%
- [ ] 时间范围覆盖足够长（建议 > 3个月）
- [ ] K线数据连续，无大段缺失
- [ ] 交易量充足（避免低流动性币种）
- [ ] 价格数据合理（无异常波动）

---

## 获取帮助

如果以上方案都无法解决问题：

1. **查看日志**: `logs/crypto_arb.log`
2. **检查数据**: 查看下载的CSV文件
3. **简化配置**: 使用最小配置测试
4. **隔离问题**: 逐个模块测试

```bash
# 最小测试配置
python quick_start.py
```

---

## 常用命令速查

```bash
# 完整运行
python crypto_main.py

# 使用已有数据
python crypto_main.py --skip-download

# 自定义配置
python crypto_main.py --config my_config.yaml

# 查看帮助
python crypto_main.py --help

# 查看日志
tail -f logs/crypto_arb.log

# 检查数据
ls -lh data/crypto/

# 查看结果
ls -lh results/crypto/
```

---

最后更新: 2024-11-24

