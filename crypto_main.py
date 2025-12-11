#!/usr/bin/env python3
"""
加密货币统计套利主程序
基于配对交易的统计套利策略回测框架
"""

import os
import sys
import yaml
import logging
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from crypto_utils.binance_data import BinanceDataDownloader
from crypto_utils.crypto_arb_strategy import CryptoStatArbStrategy

# 使用改进版回测引擎（修复了稳定币配对和资金管理问题）
try:
    from crypto_utils.backtest_engine_v2 import BacktestEngineV2 as BacktestEngine
    USE_V2_ENGINE = True
except ImportError:
    from crypto_utils.backtest_engine import BacktestEngine
    USE_V2_ENGINE = False


def setup_logging(config):
    """配置日志"""
    log_level = getattr(logging, config['logging']['level'])
    log_file = config['logging']['file']
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def load_config(config_path='config.yaml'):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def download_data(config, logger):
    """下载市场数据"""
    logger.info("="*60)
    logger.info("步骤 1: 下载市场数据")
    logger.info("="*60)
    
    downloader = BinanceDataDownloader()
    
    # 确定交易对列表
    if config['data']['source'] == 'auto':
        quote = config['data']['auto']['quote_asset']
        top_n = config['data']['auto']['top_n']
        logger.info(f"自动获取 {quote} 交易量前 {top_n} 的交易对")
        symbols = downloader.get_top_volume_pairs(quote_asset=quote, top_n=top_n)
    else:
        symbols = config['data']['manual']['symbols']
        logger.info(f"使用手动指定的 {len(symbols)} 个交易对")
    
    logger.info(f"交易对列表: {symbols}")
    
    # 下载数据
    interval = config['data']['timeframe']['interval']
    start_time = config['data']['timeframe']['start_time']
    end_time = config['data']['timeframe']['end_time']
    
    logger.info(f"时间范围: {start_time} 到 {end_time if end_time else '现在'}")
    logger.info(f"K线间隔: {interval}")
    
    market_data = downloader.prepare_pairs_data(
        symbols=symbols,
        interval=interval,
        start_time=start_time,
        end_time=end_time
    )
    
    # 保存原始数据
    if config['output']['save_data']:
        save_path = config['data']['save_path']
        os.makedirs(save_path, exist_ok=True)
        market_data.to_csv(f'{save_path}/market_data_{interval}.csv')
        logger.info(f"市场数据已保存到: {save_path}/market_data_{interval}.csv")
    
    # 强制过滤稳定币
    stablecoins = ['USDC', 'FDUSD', 'BUSD', 'TUSD', 'DAI', 'USDP', 'USDD']
    filtered_columns = []
    removed_coins = set()
    
    # 获取所有币种
    all_symbols = list(market_data.columns.get_level_values(0).unique())
    
    for symbol in all_symbols:
        # 检查是否包含稳定币名称
        is_stable = False
        for stable in stablecoins:
            if symbol.startswith(stable):
                is_stable = True
                removed_coins.add(symbol)
                break
        
        if not is_stable:
            filtered_columns.append(symbol)
            
    if removed_coins:
        logger.warning(f"已自动剔除 {len(removed_coins)} 个稳定币: {removed_coins}")
        market_data = market_data[filtered_columns]
    
    logger.info(f"数据下载完成，形状: {market_data.shape}")
    logger.info(f"时间范围: {market_data.index[0]} 到 {market_data.index[-1]}")
    
    return market_data


def find_cointegrated_pairs(market_data, config, logger):
    """寻找协整交易对"""
    logger.info("\n" + "="*60)
    logger.info("步骤 2: 协整检验")
    logger.info("="*60)
    
    # 初始化策略
    strategy = CryptoStatArbStrategy(market_data)
    
    # 协整检验
    pvalue_threshold = config['strategy']['cointegration']['pvalue_threshold']
    tradable_pairs = strategy.find_cointegrated_pairs(pvalue_threshold=pvalue_threshold)
    
    if len(tradable_pairs) == 0:
        logger.error("未找到协整交易对，请调整参数或更换交易对")
        return None, None
    
    logger.info(f"\n协整交易对 (前10个):\n{tradable_pairs.head(10)}")
    
    # 计算交易指标
    metrics = strategy.calculate_trading_metrics()
    logger.info(f"\n交易指标:\n{metrics.head(10)}")
    
    # 筛选合适的半衰期
    min_hl = config['strategy']['cointegration']['min_half_life']
    max_hl = config['strategy']['cointegration']['max_half_life']
    
    valid_pairs = metrics[
        (metrics['HalfLife'] >= min_hl) & 
        (metrics['HalfLife'] <= max_hl)
    ]
    
    logger.info(f"\n半衰期在 [{min_hl}, {max_hl}] 范围内的交易对: {len(valid_pairs)} 个")
    
    if len(valid_pairs) == 0:
        logger.warning("没有满足半衰期要求的交易对，使用所有协整交易对")
        valid_pairs = metrics
    
    # 合并结果
    final_pairs = pd.merge(
        tradable_pairs, 
        valid_pairs, 
        left_index=True, 
        right_index=True
    ).sort_values('P-Value')
    
    return strategy, final_pairs


def optimize_thresholds(strategy, final_pairs, config, logger):
    """优化交易阈值"""
    logger.info("\n" + "="*60)
    logger.info("步骤 3: 阈值优化")
    logger.info("="*60)
    
    threshold_mode = config['strategy']['threshold']['mode']
    
    if threshold_mode == 'fixed':
        # 使用固定阈值
        sigma_mult = config['strategy']['threshold']['fixed']['sigma_multiplier']
        logger.info(f"使用固定阈值: {sigma_mult}σ")
        
        best_thresholds = {}
        for pair in final_pairs.index:
            std = final_pairs.loc[pair, 'Std']
            best_thresholds[pair] = {
                'threshold': sigma_mult * std,
                'sigma_multiplier': sigma_mult,
                'pnl': 0  # 固定阈值模式不优化PnL
            }
    else:
        # 优化阈值
        logger.info("优化阈值中...")
        
        min_sigma = config['strategy']['threshold']['optimize']['min_sigma']
        max_sigma = config['strategy']['threshold']['optimize']['max_sigma']
        num_steps = config['strategy']['threshold']['optimize']['num_steps']
        
        threshold_range = np.linspace(min_sigma, max_sigma, num_steps)
        best_thresholds = {}
        
        for i, pair in enumerate(final_pairs.index[:20]):  # 限制优化数量
            logger.info(f"优化 {pair} ({i+1}/{min(20, len(final_pairs))})")
            
            # 使用.at代替.loc避免索引问题
            gamma = final_pairs.at[pair, 'Gamma']
            std = final_pairs.at[pair, 'Std']
            
            results = strategy.optimize_threshold(
                pair, gamma, std, 
                threshold_range=threshold_range,
                limit=config['backtest']['max_position_size']
            )
            
            # 选择PnL最高的阈值
            best_idx = results['TotalPnL'].idxmax()
            best_result = results.loc[best_idx]
            
            best_thresholds[pair] = {
                'threshold': best_result['Threshold'],
                'sigma_multiplier': best_result['ThresholdMultiplier'],
                'pnl': best_result['TotalPnL']
            }
            
            logger.info(f"  最佳阈值: {best_result['ThresholdMultiplier']:.2f}σ, "
                       f"预期PnL: ${best_result['TotalPnL']:.2f}")
    
    # 转换为DataFrame
    threshold_df = pd.DataFrame(best_thresholds).T
    threshold_df.index.name = 'Pair'
    
    return threshold_df


def select_trading_pairs(final_pairs, threshold_df, config, logger):
    """选择最终交易对"""
    logger.info("\n" + "="*60)
    logger.info("步骤 4: 选择交易对")
    logger.info("="*60)
    
    max_pairs = config['strategy']['pair_selection']['max_pairs']
    method = config['strategy']['pair_selection']['method']
    no_overlap = config['strategy']['pair_selection']['no_overlap']
    
    if method == 'top_pnl':
        # 按PnL排序
        sorted_pairs = threshold_df.sort_values('pnl', ascending=False)
    else:
        # 按P-Value排序（更可靠的协整关系）
        sorted_pairs = threshold_df.loc[
            final_pairs.sort_values('P-Value').index.intersection(threshold_df.index)
        ]
    
    selected_pairs = []
    used_symbols = set()
    
    for pair in sorted_pairs.index:
        if len(selected_pairs) >= max_pairs:
            break
        
        symbol1, symbol2 = pair
        
        # 检查资产重叠
        if no_overlap:
            if symbol1 in used_symbols or symbol2 in used_symbols:
                continue
            used_symbols.add(symbol1)
            used_symbols.add(symbol2)
        
        selected_pairs.append(pair)
    
    logger.info(f"选择了 {len(selected_pairs)} 个交易对:")
    for pair in selected_pairs:
        logger.info(f"  {pair[0]}-{pair[1]}: "
                   f"Gamma={final_pairs.at[pair, 'Gamma']:.4f}, "
                   f"Threshold={threshold_df.at[pair, 'threshold']:.6f}, "
                   f"PnL=${threshold_df.at[pair, 'pnl']:.2f}")
    
    return selected_pairs


def run_backtest(strategy, selected_pairs, final_pairs, threshold_df, config, logger):
    """运行回测"""
    logger.info("\n" + "="*60)
    logger.info("步骤 5: 回测执行")
    logger.info("="*60)
    
    # 准备配置
    pairs_config = {}
    for pair in selected_pairs:
        pairs_config[pair] = {
            'gamma': final_pairs.at[pair, 'Gamma'],
            'threshold': threshold_df.at[pair, 'threshold']
        }
    
    # 创建回测引擎
    initial_capital = config['backtest']['initial_capital']
    max_position_size = config['backtest']['max_position_size']
    
    # v2引擎使用百分比参数，v1使用绝对值参数
    if USE_V2_ENGINE:
        # 计算持仓占比
        max_position_pct = max_position_size / initial_capital
        backtest = BacktestEngine(
            market_data=strategy.market_data,
            initial_capital=initial_capital,
            max_position_pct=max_position_pct,
            max_leverage=1.0
        )
    else:
        backtest = BacktestEngine(
            market_data=strategy.market_data,
            initial_capital=initial_capital,
            max_position_size=max_position_size
        )
    
    # 运行回测
    results = backtest.run_backtest(pairs_config, strategy)
    
    # 输出结果
    output_dir = config['output']['results_dir']
    os.makedirs(output_dir, exist_ok=True)
    
    if config['output']['save_data']:
        backtest.export_results(output_dir)
    
    if config['output']['save_plots']:
        backtest.plot_results(save_dir=output_dir)
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='加密货币统计套利回测')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='配置文件路径')
    parser.add_argument('--skip-download', action='store_true',
                       help='跳过数据下载，使用已有数据')
    parser.add_argument('--data-file', type=str, default=None,
                       help='使用指定的数据文件')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    logger = setup_logging(config)
    
    logger.info("="*60)
    logger.info("加密货币统计套利回测系统")
    logger.info("="*60)
    logger.info(f"配置文件: {args.config}")
    logger.info(f"回测引擎: {'改进版 v2' if USE_V2_ENGINE else '原版 (建议升级到v2)'}")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 获取数据
        if args.data_file:
            logger.info(f"从文件加载数据: {args.data_file}")
            market_data = pd.read_csv(args.data_file, index_col=0, header=[0, 1])
            market_data.index = pd.to_datetime(market_data.index)
        elif args.skip_download:
            data_file = f"{config['data']['save_path']}/market_data_{config['data']['timeframe']['interval']}.csv"
            logger.info(f"从文件加载数据: {data_file}")
            market_data = pd.read_csv(data_file, index_col=0, header=[0, 1])
            market_data.index = pd.to_datetime(market_data.index)
            
            # 如果是manual模式，强制过滤只保留配置中的币种
            if config['data']['source'] == 'manual':
                target_symbols = config['data']['manual']['symbols']
                # 从MultiIndex列中提取第一层（symbol）
                current_symbols = market_data.columns.get_level_values(0).unique()
                
                # 找出需要保留的列
                keep_symbols = [s for s in current_symbols if s in target_symbols]
                
                if len(keep_symbols) < len(current_symbols):
                    logger.info(f"根据配置过滤币种: {len(current_symbols)} -> {len(keep_symbols)}")
                    # 重建DataFrame只包含目标币种
                    # 注意：这里需要处理MultiIndex切片
                    market_data = market_data.loc[:, (keep_symbols, slice(None))]
        else:
            market_data = download_data(config, logger)
            
        # 再次过滤稳定币（以防从CSV加载了包含稳定币的数据）
        stablecoins = ['USDC', 'FDUSD', 'BUSD', 'TUSD', 'DAI', 'USDP', 'USDD']
        filtered_columns = []
        removed_coins = set()
        all_symbols = list(market_data.columns.get_level_values(0).unique())
        
        for symbol in all_symbols:
            is_stable = False
            for stable in stablecoins:
                if symbol.startswith(stable):
                    is_stable = True
                    removed_coins.add(symbol)
                    break
            if not is_stable:
                filtered_columns.append(symbol)
                
        if removed_coins:
            logger.warning(f"从数据中剔除 {len(removed_coins)} 个稳定币: {removed_coins}")
            market_data = market_data[filtered_columns]
        
        # 2. 寻找协整交易对
        strategy, final_pairs = find_cointegrated_pairs(market_data, config, logger)
        
        if strategy is None:
            return
        
        # 3. 优化阈值
        threshold_df = optimize_thresholds(strategy, final_pairs, config, logger)
        
        # 4. 选择交易对
        selected_pairs = select_trading_pairs(final_pairs, threshold_df, config, logger)
        
        if len(selected_pairs) == 0:
            logger.error("没有可交易的交易对")
            return
        
        # 5. 运行回测
        results = run_backtest(strategy, selected_pairs, final_pairs, threshold_df, config, logger)
        
        logger.info("\n" + "="*60)
        logger.info("回测完成!")
        logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"运行出错: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

