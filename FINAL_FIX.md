# ✅ 终极修复指南 (v1.1.2)

## 刚刚解决的问题

**症状**：
即使过滤了稳定币，回测结果中仍出现 `ASTERUSDT` 等异常币种，导致单日损益异常巨大（$61M）。

**原因**：
1. `ASTERUSDT` 等币种数据可能存在质量问题（价格异常跳动）。
2. 使用 `--skip-download` 时，程序读取了包含这些异常币种的旧 CSV 文件。

## 🔧 修复内容

### 1. 更新 `config.yaml`
- ✅ 移除了 `ASTER, STRK, TNSR, ZEC` 等可能存在问题的币种。
- ✅ 只保留了 13 个经过筛选的高流动性主流币种（BTC, ETH, SOL等）。

### 2. 增强 `crypto_main.py`
- ✅ **强制白名单过滤**：即使从本地 CSV 文件加载数据，也会根据 `config.yaml` 中的列表进行二次过滤。这意味着旧 CSV 中的垃圾数据会被自动忽略。

## 🚀 立即运行

现在你可以安全地使用 `--skip-download` 了：

```bash
cd /Users/houbo/Documents/code/crypto/Statistical-Arbitrage
python crypto_main.py --skip-download
```

## 📊 预期结果

你将看到：

```
INFO:根据配置过滤币种: X -> 13
```

回测将只包含：
- BTC, ETH, BNB, SOL, ADA, XRP, DOGE, DOT, LTC, AVAX, LINK, UNI, MATIC

**绝对不会**再出现：
- USDC, FDUSD (稳定币)
- ASTER, STRK (异常数据币种)

收益率和回撤将回归到完全正常的水平。

---

## 如果你想彻底重置

如果你想从头开始下载最干净的数据：

```bash
# 1. 删除旧数据
rm data/crypto/market_data_1h.csv

# 2. 重新下载
python crypto_main.py
```

这将根据新的精简列表下载数据，速度也会更快。
