# 项目结构说明

## 📁 目录树

```
Statistical-Arbitrage/
│
├── 📄 crypto_main.py              # 主程序入口
├── 📄 config.yaml                 # 配置文件
├── 📄 quick_start.py             # 快速开始示例
├── 📄 requirements_crypto.txt    # Python依赖包
│
├── 📄 README_CRYPTO.md           # 项目说明文档
├── 📄 USAGE_GUIDE_CN.md          # 详细使用指南
├── 📄 PROJECT_STRUCTURE.md       # 本文件
│
├── 📁 crypto_utils/              # 核心功能模块
│   ├── __init__.py
│   ├── binance_data.py           # Binance数据下载
│   ├── crypto_arb_strategy.py   # 统计套利策略
│   └── backtest_engine.py        # 回测引擎
│
├── 📁 data/                      # 数据目录
│   ├── crypto/                   # 加密货币数据
│   │   └── market_data_*.csv    # 下载的市场数据
│   └── [原有股票数据...]
│
├── 📁 results/                   # 结果输出
│   └── crypto/                   # 加密货币回测结果
│       ├── positions.csv         # 持仓记录
│       ├── pnl.csv              # 损益记录
│       ├── metrics.csv          # 性能指标
│       ├── pair_results.csv     # 各交易对表现
│       ├── cumulative_pnl.png   # PnL曲线图
│       ├── position_*.png       # 持仓图
│       └── drawdown.png         # 回撤图
│
├── 📁 logs/                      # 日志文件
│   └── crypto_arb.log           # 运行日志
│
├── 📁 [原项目文件...]            # 原股票套利项目
│   ├── statistical_arbitrage.ipynb
│   ├── utils/
│   ├── models/
│   ├── imgs/
│   ├── res/
│   └── report/
│
└── 📄 [其他文件...]
```

## 📦 新增文件说明

### 核心程序文件

| 文件 | 说明 | 用途 |
|------|------|------|
| `crypto_main.py` | 主程序入口 | 完整的回测流程控制 |
| `quick_start.py` | 快速开始脚本 | 演示基本用法 |
| `config.yaml` | 配置文件 | 所有策略参数设置 |

### 功能模块 (`crypto_utils/`)

| 模块 | 主要类/函数 | 功能 |
|------|-------------|------|
| `binance_data.py` | `BinanceDataDownloader` | 从Binance下载历史数据 |
| `crypto_arb_strategy.py` | `CryptoStatArbStrategy` | 协整检验、信号生成 |
| `backtest_engine.py` | `BacktestEngine` | 回测执行、性能分析 |

### 文档文件

| 文档 | 内容 |
|------|------|
| `README_CRYPTO.md` | 项目概览、特性介绍 |
| `USAGE_GUIDE_CN.md` | 详细使用教程、常见问题 |
| `PROJECT_STRUCTURE.md` | 本文档，项目结构说明 |

## 🔄 数据流程

```
1. 数据获取
   crypto_main.py
        ↓
   BinanceDataDownloader.prepare_pairs_data()
        ↓
   data/crypto/market_data_*.csv

2. 协整检验
   market_data
        ↓
   CryptoStatArbStrategy.find_cointegrated_pairs()
        ↓
   tradable_pairs

3. 阈值优化
   tradable_pairs
        ↓
   CryptoStatArbStrategy.optimize_threshold()
        ↓
   best_thresholds

4. 回测执行
   pairs_config
        ↓
   BacktestEngine.run_backtest()
        ↓
   results/crypto/*

5. 结果分析
   results
        ↓
   图表 + CSV文件
```

## 🎯 使用场景

### 场景1: 快速测试
```bash
# 使用默认配置快速运行
python crypto_main.py
```

### 场景2: 自定义策略
```bash
# 1. 编辑 config.yaml
# 2. 运行自定义配置
python crypto_main.py --config config.yaml
```

### 场景3: 重复测试
```bash
# 使用已下载数据（节省时间）
python crypto_main.py --skip-download
```

### 场景4: 学习示例
```bash
# 运行交互式示例
python quick_start.py
```

### 场景5: 二次开发
```python
# 在Python脚本中使用
from crypto_utils import BinanceDataDownloader, CryptoStatArbStrategy
# ... 自定义代码
```

## 📊 输出文件说明

### CSV文件

1. **positions.csv**: 持仓记录
   - 列: 时间戳 + 各交易对持仓量
   - 用途: 分析持仓变化

2. **pnl.csv**: 损益记录
   - 列: 时间戳 + 各交易对PnL + 总PnL
   - 用途: 分析收益来源

3. **metrics.csv**: 性能指标
   - 包含: 总收益、夏普比率、最大回撤等
   - 用途: 评估策略表现

4. **pair_results.csv**: 交易对表现
   - 包含: 每个交易对的收益、交易次数等
   - 用途: 对比不同交易对

### 图表文件

1. **cumulative_pnl.png**: 累计PnL曲线
   - 上图: 总体收益曲线
   - 下图: 各交易对收益曲线

2. **position_*.png**: 持仓变化图
   - 显示两个资产的持仓变化
   - 观察对冲关系

3. **drawdown.png**: 回撤曲线
   - 显示资金回撤情况
   - 评估风险

## 🔧 配置文件层次

```yaml
config.yaml
├── data:                    # 数据配置
│   ├── source              # 数据来源
│   ├── auto/manual         # 自动/手动选择
│   └── timeframe           # 时间设置
│
├── strategy:               # 策略配置
│   ├── cointegration       # 协整检验参数
│   ├── threshold           # 阈值设置
│   └── pair_selection      # 交易对选择
│
├── backtest:               # 回测配置
│   ├── initial_capital     # 初始资金
│   ├── max_position_size   # 最大持仓
│   └── commission/slippage # 成本设置
│
├── output:                 # 输出配置
│   ├── results_dir         # 结果目录
│   └── save_plots/data     # 保存选项
│
├── logging:                # 日志配置
│   └── level/file          # 日志级别和文件
│
└── binance:                # API配置（可选）
    └── api_key/secret      # API密钥
```

## 🆚 与原项目的关系

### 原项目（股票）
```
statistical_arbitrage.ipynb    # Jupyter notebook
utils/ArbUtils.py              # 辅助函数
models/                        # 定价模型
data/price_stock.csv          # 股票数据
```

### 新项目（加密货币）
```
crypto_main.py                # Python脚本
crypto_utils/                 # 完整模块包
config.yaml                   # 配置驱动
data/crypto/                  # 加密货币数据
```

### 核心差异

| 方面 | 原项目 | 新项目 |
|------|--------|--------|
| 数据源 | CSV文件 | Binance API |
| 运行方式 | Jupyter | 命令行/脚本 |
| 配置方式 | 代码内嵌 | YAML配置文件 |
| 模块化 | 中等 | 高 |
| 可扩展性 | 中等 | 高 |
| 自动化 | 手动 | 自动化 |

### 策略相似性

✅ 两个项目使用相同的核心策略：
- 协整检验（Engle-Granger）
- 误差修正项计算
- 阈值交易信号
- 对冲比率管理

## 💡 扩展建议

### 短期扩展
1. 增加更多交易所支持（OKX, Huobi等）
2. 添加实时交易功能
3. 增加更多风险指标
4. 优化参数搜索算法

### 中期扩展
1. Web界面展示
2. 策略组合管理
3. 自动报告生成
4. 邮件/钉钉通知

### 长期扩展
1. 机器学习优化
2. 多市场套利
3. 高频交易支持
4. 分布式回测

## 📝 开发规范

### 代码风格
- PEP 8标准
- 类型提示
- 详细文档字符串
- 日志记录

### 模块设计
- 单一职责原则
- 低耦合高内聚
- 配置与代码分离
- 可测试性

### 版本控制
```bash
# 推荐的Git工作流
git checkout -b feature/new-feature
# ... 开发
git commit -m "Add: new feature"
git push origin feature/new-feature
```

## 🐛 调试技巧

### 查看日志
```bash
tail -f logs/crypto_arb.log
```

### 调整日志级别
```yaml
# config.yaml
logging:
  level: 'DEBUG'  # INFO -> DEBUG
```

### Python调试
```python
# 在crypto_main.py中添加
import pdb; pdb.set_trace()
```

## 📚 学习路径

1. **初学者**:
   - 阅读 README_CRYPTO.md
   - 运行 quick_start.py
   - 修改 config.yaml 尝试不同参数

2. **进阶用户**:
   - 阅读 USAGE_GUIDE_CN.md
   - 理解各模块源码
   - 尝试参数优化

3. **高级用户**:
   - 修改策略逻辑
   - 添加新功能模块
   - 集成其他数据源

## 🤝 贡献指南

欢迎贡献代码！建议流程：
1. Fork项目
2. 创建功能分支
3. 提交代码
4. 发起Pull Request

## 📮 反馈

如有问题或建议，请：
- 提交GitHub Issue
- 或通过其他方式联系

---

最后更新: 2024-11-24

