# 更新日志

## v1.1.0 (2024-11-24) - 🚨 严重Bug修复

### 🔴 严重问题修复

#### 异常回撤问题
**问题**：回测显示最大回撤$834M，远超初始资金$100K，收益率23905%，夏普比率0.003。

**根本原因**：
1. **稳定币配对**：FDUSDUSDT、USDCUSDT等稳定币与其他币种配对
   - 价格接近1.0但持仓量巨大
   - 微小价格变动导致巨额损益
   - P-value很小（确实协整）但无套利价值

2. **资金管理缺失**：
   - 每个交易对独立使用max_position_size
   - 多个交易对累计超过初始资金
   - 没有全局资金限制

3. **风险计算错误**：
   - 允许持仓市值远超资金
   - 回撤计算不准确

**修复**：
- ✅ 创建改进版回测引擎 v2 (`backtest_engine_v2.py`)
- ✅ 自动过滤稳定币配对
- ✅ 全局资金管理和风险控制
- ✅ 异常持仓检测和警告
- ✅ 更准确的回撤计算（基于组合价值）

**影响的文件**：
- `crypto_utils/backtest_engine_v2.py`（新增）
- `crypto_main.py`（自动使用v2引擎）
- `config.yaml`（默认排除稳定币）

**使用建议**：
```yaml
# config.yaml - 避免稳定币
data:
  source: 'manual'
  manual:
    symbols: ['BTCUSDT', 'ETHUSDT', ...]  # 不包含USDC/FDUSD
```

### 📊 预期改进

| 指标 | v1.0.2 | v1.1.0 | 说明 |
|------|--------|--------|------|
| 收益率 | 23905% | 5-20% | 合理范围 |
| 最大回撤 | -834842% | -2~-15% | 不超过资金 |
| 夏普比率 | 0.003 | 0.5-2.5 | 健康水平 |
| 回撤绝对值 | $834M | $2K-$15K | 合理范围 |

### 📚 新增文档

- **CRITICAL_BUG_FIX.md**：详细问题分析和解决方案
- **FIX_AND_RERUN.md**：一键修复指南

---

## v1.0.2 (2024-11-24)

### 🐛 Bug修复

#### 3. Pandas索引访问错误
**问题**: 使用`.loc[pair, 'column']`访问DataFrame时出现`AssertionError`。

**修复**:
- ✅ 将所有`.loc`标量访问改为`.at`
- ✅ 添加异常处理机制
- ✅ 兼容不同版本的pandas

**影响的文件**:
- `crypto_utils/crypto_arb_strategy.py`
- `crypto_main.py`
- `quick_start.py`

**技术说明**:
```python
# 之前（可能出错）
value = df.loc[pair, 'Column']

# 现在（稳定）
value = df.at[pair, 'Column']
```

---

## v1.0.1 (2024-11-24)

### 🐛 Bug修复

#### 1. NaN值处理问题
**问题**: 某些新上市的交易对（如ASTERUSDT）包含大量NaN值，导致协整检验失败。

**修复**:
- ✅ 数据下载时自动检测并剔除NaN比例超过10%的交易对
- ✅ 协整检验前自动清理剩余的NaN值
- ✅ 使用前向/后向填充处理少量缺失数据
- ✅ 添加数据质量报告，初始化时显示各交易对的NaN比例

**影响的文件**:
- `crypto_utils/binance_data.py`
- `crypto_utils/crypto_arb_strategy.py`

**使用建议**:
```yaml
# 可以调整NaN容忍度（默认10%）
# 在prepare_pairs_data方法中
drop_nan_threshold: 0.1  # 10%
```

#### 2. statsmodels兼容性警告
**问题**: `has_const=True` 参数在新版statsmodels中已废弃，产生警告。

**修复**:
- ✅ 移除 `has_const` 参数
- ✅ 代码与statsmodels 0.12.2+ 兼容

**影响的文件**:
- `crypto_utils/crypto_arb_strategy.py`

### 📚 文档更新

#### 新增文档
- ✅ **TROUBLESHOOTING.md**: 详细的故障排除指南
  - 10个常见问题及解决方案
  - 调试技巧
  - 性能优化建议
  - 数据质量检查清单

### 🔧 改进

#### 数据质量监控
- 添加初始化时的数据质量报告
- 协整检验时跳过NaN比例过高的交易对
- 详细的警告日志帮助诊断问题

#### 错误处理
- 更友好的错误信息
- 自动跳过问题交易对而非崩溃
- 详细的日志记录

---

## v1.0.0 (2024-11-24)

### 🎉 初始版本

#### 核心功能
- ✅ Binance历史数据下载
- ✅ 协整检验（Engle-Granger）
- ✅ 统计套利策略
- ✅ 阈值优化
- ✅ 完整回测引擎
- ✅ 性能指标计算
- ✅ 可视化图表

#### 模块结构
```
crypto_utils/
├── binance_data.py          # Binance数据下载
├── crypto_arb_strategy.py   # 统计套利策略
└── backtest_engine.py       # 回测引擎
```

#### 配置系统
- YAML配置文件
- 灵活的参数设置
- 支持多种运行模式

#### 文档
- README_CRYPTO.md
- USAGE_GUIDE_CN.md
- PROJECT_STRUCTURE.md

---

## 升级指南

### 从v1.0.0升级到v1.0.1

无需特殊操作，直接使用新版本即可。新版本完全向后兼容。

**建议操作**:
1. 备份当前版本（可选）
2. 更新文件
3. 重新运行回测

```bash
# 备份（可选）
cp crypto_utils/crypto_arb_strategy.py crypto_arb_strategy.py.bak
cp crypto_utils/binance_data.py binance_data.py.bak

# 使用新版本
# （文件已更新）

# 测试
python crypto_main.py --skip-download  # 使用已有数据测试
```

### 新功能使用

#### 1. 数据质量报告
运行程序时会自动显示：
```
WARNING:crypto_utils.crypto_arb_strategy:ASTERUSDT 包含 15000 个NaN值 (90.12%)
INFO:crypto_utils.binance_data:保留 14/15 个交易对
```

#### 2. 自动数据清洗
无需手动操作，系统会自动：
- 剔除低质量交易对
- 清理NaN值
- 填充缺失数据

#### 3. 更好的错误处理
程序会跳过问题交易对而继续运行：
```
WARNING:crypto_utils.crypto_arb_strategy:跳过 ASTERUSDT-BTCUSDT: NaN比例过高 (90.1%, 0.0%)
```

---

## 已知问题

### 1. Pandas 2.0+ 兼容性
**问题**: pandas 2.0+中 `fillna(method='ffill')` 已废弃。

**状态**: 已知，将在下一版本修复。

**临时解决方案**:
```bash
pip install pandas==1.4.2
```

### 2. 图表中文显示
**问题**: 某些系统上中文可能显示为方框。

**状态**: 已知，取决于系统字体。

**解决方案**: 见TROUBLESHOOTING.md第8节。

---

## 路线图

### v1.1.0 (计划中)
- [ ] 支持更多交易所（OKX, Huobi）
- [ ] 实时交易功能
- [ ] Web界面
- [ ] 更多风险指标

### v1.2.0 (计划中)
- [ ] 机器学习优化
- [ ] 策略组合管理
- [ ] 自动报告生成
- [ ] 通知功能（邮件/钉钉）

### v2.0.0 (远期)
- [ ] 高频交易支持
- [ ] 分布式回测
- [ ] 多市场套利
- [ ] 完整的交易系统

---

## 贡献者

感谢所有贡献者！

---

## 反馈

如有问题或建议，请：
- 提交Issue
- 或通过其他方式联系

---

最后更新: 2024-11-24

