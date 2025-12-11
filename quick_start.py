#!/usr/bin/env python3
"""
快速开始示例
演示如何使用加密货币统计套利系统
"""

import warnings
warnings.filterwarnings('ignore')

from crypto_utils import BinanceDataDownloader, CryptoStatArbStrategy, BacktestEngine


def example_1_download_data():
    """
    示例1: 下载Binance历史数据
    """
    print("="*60)
    print("示例1: 下载Binance历史数据")
    print("="*60)
    
    # 初始化下载器
    downloader = BinanceDataDownloader()
    
    # 获取交易量前10的USDT交易对
    print("\n获取热门交易对...")
    top_pairs = downloader.get_top_volume_pairs(quote_asset='USDT', top_n=10)
    print(f"交易量前10: {top_pairs}")
    
    # 下载单个交易对数据
    print("\n下载BTCUSDT 1小时K线数据...")
    btc_data = downloader.get_historical_klines(
        symbol='BTCUSDT',
        interval='1h',
        start_time='2024-01-01',
        end_time='2024-01-07'
    )
    print(f"数据形状: {btc_data.shape}")
    print(btc_data.head())
    
    # 下载多个交易对并准备配对交易格式
    print("\n下载多个交易对并准备配对交易数据...")
    pairs_data = downloader.prepare_pairs_data(
        symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        interval='1h',
        start_time='2024-01-01',
        end_time='2024-01-31'
    )
    print(f"数据形状: {pairs_data.shape}")
    print(pairs_data.head())
    
    return pairs_data


def example_2_find_pairs(market_data):
    """
    示例2: 寻找协整交易对
    """
    print("\n" + "="*60)
    print("示例2: 寻找协整交易对")
    print("="*60)
    
    # 初始化策略
    strategy = CryptoStatArbStrategy(market_data)
    
    # 协整检验
    print("\n执行协整检验...")
    tradable_pairs = strategy.find_cointegrated_pairs(pvalue_threshold=0.05)
    
    if len(tradable_pairs) > 0:
        print(f"\n找到 {len(tradable_pairs)} 个协整交易对:")
        print(tradable_pairs)
        
        # 计算交易指标
        print("\n计算交易指标...")
        metrics = strategy.calculate_trading_metrics()
        print(metrics)
        
        return strategy, tradable_pairs
    else:
        print("未找到协整交易对，可能需要更多数据或调整参数")
        return strategy, None


def example_3_optimize_threshold(strategy, pair):
    """
    示例3: 优化交易阈值
    """
    print("\n" + "="*60)
    print("示例3: 优化交易阈值")
    print("="*60)
    
    # 获取交易对参数
    gamma = strategy.tradable_pairs.at[pair, 'Gamma']
    
    # 计算标准差
    import pandas as pd
    metrics = strategy.calculate_trading_metrics()
    std = metrics.at[pair, 'Std']
    
    # 优化阈值
    print(f"\n优化交易对 {pair} 的阈值...")
    import numpy as np
    results = strategy.optimize_threshold(
        pair=pair,
        gamma=gamma,
        std=std,
        threshold_range=np.linspace(0.5, 2.5, 5),
        limit=10000.0
    )
    
    print("\n阈值优化结果:")
    print(results)
    
    # 可视化误差修正项
    print(f"\n可视化 {pair} 的误差修正项...")
    strategy.visualize_pair(pair)
    
    return results


def example_4_backtest(strategy, pairs_config):
    """
    示例4: 运行回测
    """
    print("\n" + "="*60)
    print("示例4: 运行回测")
    print("="*60)
    
    # 创建回测引擎
    try:
        from crypto_utils.backtest_engine_v2 import BacktestEngineV2 as BacktestEngine
        use_v2 = True
    except ImportError:
        from crypto_utils.backtest_engine import BacktestEngine
        use_v2 = False
        
    if use_v2:
        engine = BacktestEngine(
            market_data=strategy.market_data,
            initial_capital=100000.0,
            max_position_pct=0.1
        )
    else:
        engine = BacktestEngine(
            market_data=strategy.market_data,
            initial_capital=100000.0,
            max_position_size=10000.0
        )
    
    # 运行回测
    print("\n运行回测...")
    results = engine.run_backtest(pairs_config, strategy)
    
    # 绘制结果
    print("\n生成回测图表...")
    engine.plot_results()
    
    # 导出结果
    print("\n导出回测结果...")
    engine.export_results('./results/quick_start')
    
    return results


def main():
    """
    主函数：运行完整示例流程
    """
    print("="*60)
    print("加密货币统计套利系统 - 快速开始示例")
    print("="*60)
    
    try:
        # 示例1: 下载数据
        # 注意: 这需要网络连接到Binance
        print("\n提示: 示例1需要下载数据，可能需要几分钟...")
        print("如果网络连接有问题，可以注释掉example_1并使用预先下载的数据")
        
        # 取消注释下面这行来运行数据下载
        # market_data = example_1_download_data()
        
        # 或者使用测试数据（需要先准备）
        print("\n使用已有数据进行演示...")
        import pandas as pd
        import os
        
        # 检查是否有已下载的数据
        data_file = './data/crypto/market_data_1h.csv'
        if os.path.exists(data_file):
            print(f"加载数据文件: {data_file}")
            market_data = pd.read_csv(data_file, index_col=0, header=[0, 1])
            market_data.index = pd.to_datetime(market_data.index)
        else:
            print(f"\n数据文件不存在: {data_file}")
            print("请先运行以下命令下载数据:")
            print("  python crypto_main.py")
            print("\n或者取消注释上面的 example_1_download_data() 来下载数据")
            return
        
        # 示例2: 寻找协整交易对
        strategy, tradable_pairs = example_2_find_pairs(market_data)
        
        if tradable_pairs is None or len(tradable_pairs) == 0:
            print("\n未找到协整交易对，示例结束")
            return
        
        # 选择第一个交易对进行演示
        first_pair = tradable_pairs.index[0]
        
        # 示例3: 优化阈值
        threshold_results = example_3_optimize_threshold(strategy, first_pair)
        
        # 准备回测配置
        best_threshold = threshold_results.loc[
            threshold_results['TotalPnL'].idxmax(), 'Threshold'
        ]
        
        pairs_config = {
            first_pair: {
                'gamma': strategy.tradable_pairs.at[first_pair, 'Gamma'],
                'threshold': best_threshold
            }
        }
        
        # 示例4: 运行回测
        results = example_4_backtest(strategy, pairs_config)
        
        print("\n" + "="*60)
        print("示例运行完成!")
        print("="*60)
        print("\n提示:")
        print("1. 回测结果已保存到 ./results/quick_start/")
        print("2. 查看生成的图表和CSV文件")
        print("3. 修改 config.yaml 来定制策略参数")
        print("4. 运行 'python crypto_main.py' 执行完整回测流程")
        
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

