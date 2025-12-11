# ⚡ v1.1版本快速修复

## 刚刚修复的问题

**错误信息**：
```
TypeError: __init__() got an unexpected keyword argument 'max_position_size'
```

**原因**：v2引擎改变了初始化参数接口

### 参数变化

| 版本 | 参数 | 说明 |
|------|------|------|
| v1 | `max_position_size=10000.0` | 绝对值（美元） |
| v2 | `max_position_pct=0.1` | 百分比（10%） |

### 已修复 ✅

`crypto_main.py` 现在自动检测引擎版本并使用正确的参数：

```python
if USE_V2_ENGINE:
    # 使用百分比参数
    max_position_pct = max_position_size / initial_capital
    backtest = BacktestEngine(
        market_data=strategy.market_data,
        initial_capital=initial_capital,
        max_position_pct=max_position_pct,
        max_leverage=1.0
    )
else:
    # 使用绝对值参数
    backtest = BacktestEngine(
        market_data=strategy.market_data,
        initial_capital=initial_capital,
        max_position_size=max_position_size
    )
```

## 🚀 现在可以运行了

```bash
cd /Users/houbo/Documents/code/crypto/Statistical-Arbitrage
python crypto_main.py --skip-download
```

## 预期输出

```
INFO:__main__:回测引擎: 改进版 v2  ✅
INFO:__main__:步骤 5: 回测执行
INFO:crypto_utils.backtest_engine_v2:开始回测，共 X 个交易对
INFO:crypto_utils.backtest_engine_v2:回测交易对: BTC-ETH
...
============================================================
回测结果摘要 (改进版)
============================================================
初始资金:        $100,000.00
最终资金:        $XXX,XXX.XX  ✅
总收益:          $XX,XXX.XX
收益率:          XX.XX%  ✅ 合理
最大回撤:        $-X,XXX.XX (-X.XX%)  ✅ 合理！
夏普比率:        X.XXX  ✅
...
```

## 关键改进

1. ✅ 自动检测引擎版本
2. ✅ 兼容v1和v2参数
3. ✅ 自动过滤稳定币
4. ✅ 合理的风险指标
5. ✅ 完整的可视化功能

## 如果还有问题

### 问题：还是参数错误
**检查**：确认文件 `crypto_utils/backtest_engine_v2.py` 存在

### 问题：找不到协整对
**解决**：
```yaml
# config.yaml
strategy:
  cointegration:
    pvalue_threshold: 0.05  # 放宽到0.05
```

### 问题：结果还是异常
**检查**：
1. 是否看到 "改进版 v2" 提示？
2. 是否看到 "跳过稳定币配对" 警告？
3. config.yaml 是否使用 manual 模式？

## 完整流程

### 首次运行（下载新数据）
```bash
python crypto_main.py
```

### 使用已有数据（更快）
```bash
python crypto_main.py --skip-download
```

### 查看结果
```bash
ls -lh results/crypto/
# 应该看到：
# - cumulative_pnl.png
# - drawdown.png
# - position_*.png
# - metrics.csv
# - pnl.csv
```

---

## 技术细节

### v2引擎的优势

1. **百分比管理**：更灵活的资金分配
   ```python
   max_position_pct = 0.1  # 10%的资金
   # 如果有10万，就是1万
   # 如果有100万，就是10万
   ```

2. **稳定币过滤**：自动识别并跳过
   ```python
   def _is_stablecoin_pair(self, symbol1, symbol2):
       stablecoins = ['USDT', 'USDC', 'BUSD', 'TUSD', 'FDUSD', 'DAI']
       # ... 检查逻辑
   ```

3. **异常检测**：警告过大的损益
   ```python
   if max_daily_pnl > self.initial_capital * 0.5:
       logger.warning(f"单日最大损益超过50%")
   ```

4. **准确回撤**：基于组合价值而非PnL
   ```python
   portfolio_value = initial_capital + cumulative_pnl
   drawdown = portfolio_value - running_max
   ```

---

## 所有文件更新状态

| 文件 | 状态 | 说明 |
|------|------|------|
| `crypto_main.py` | ✅ 已更新 | 兼容v1/v2引擎 |
| `config.yaml` | ✅ 已更新 | 排除稳定币 |
| `crypto_utils/backtest_engine_v2.py` | ✅ 新增 | 改进版引擎 |
| `crypto_utils/backtest_engine.py` | ⚪ 保留 | v1引擎（备用） |

## 立即运行 🎯

```bash
python crypto_main.py --skip-download
```

应该在几分钟内看到合理的回测结果！

---

更新时间: 2024-11-24
版本: v1.1.0 (稳定版)

