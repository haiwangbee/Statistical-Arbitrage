#!/usr/bin/env python3
"""
加密货币统计套利 Dry Run 模式
长期运行的模拟交易程序，用于在真实市场中测试策略表现
"""

import os
import sys
import yaml
import logging
import argparse
import signal
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from crypto_utils.live_data import LiveDataFeed
from crypto_utils.dryrun_engine import DryRunEngine
from crypto_utils.crypto_arb_strategy import CryptoStatArbStrategy


class DryRunManager:
    """
    Dry Run 管理器
    协调数据源、策略和交易引擎
    """
    
    def __init__(self, config: dict):
        """
        初始化 Dry Run 管理器
        
        Parameters:
        -----------
        config : dict
            配置字典
        """
        self.config = config
        self.logger = self._setup_logging()
        
        # 组件
        self.data_feed: LiveDataFeed = None
        self.engine: DryRunEngine = None
        self.strategy: CryptoStatArbStrategy = None
        
        # 运行状态
        self._running = False
        self._initialized = False
        
        # 协整参数
        self.pairs_config = {}
        self.cointegration_params = {}
        
        self.logger.info("DryRunManager 初始化完成")
    
    def _setup_logging(self) -> logging.Logger:
        """配置日志"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', './logs/dryrun.log')
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 创建 logger
        logger = logging.getLogger('DryRun')
        logger.setLevel(log_level)
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def initialize(self):
        """初始化所有组件"""
        self.logger.info("=" * 60)
        self.logger.info("开始初始化 Dry Run 系统")
        self.logger.info("=" * 60)
        
        # 1. 获取交易对列表
        if self.config['data']['source'] == 'manual':
            symbols = self.config['data']['manual']['symbols']
        else:
            from crypto_utils.binance_data import BinanceDataDownloader
            downloader = BinanceDataDownloader()
            symbols = downloader.get_top_volume_pairs(
                quote_asset=self.config['data']['auto']['quote_asset'],
                top_n=self.config['data']['auto']['top_n']
            )
        
        # 过滤稳定币
        stablecoins = ['USDC', 'FDUSD', 'BUSD', 'TUSD', 'DAI', 'USDP', 'USDD']
        filtered_symbols = []
        for symbol in symbols:
            is_stable = any(symbol.startswith(s) for s in stablecoins)
            if not is_stable:
                filtered_symbols.append(symbol)
        
        self.logger.info(f"交易对数量: {len(filtered_symbols)}")
        
        # 2. 初始化实时数据源
        dryrun_config = self.config.get('dryrun', {})
        interval = self.config['data']['timeframe']['interval']
        lookback_hours = dryrun_config.get('lookback_hours', 168)
        
        self.data_feed = LiveDataFeed(
            symbols=filtered_symbols,
            interval=interval,
            lookback_hours=lookback_hours
        )
        
        # 获取历史数据
        self.logger.info("正在获取历史数据...")
        market_data = self.data_feed.fetch_historical_data()
        self.logger.info(f"历史数据形状: {market_data.shape}")
        
        # 3. 运行协整分析
        self.logger.info("正在进行协整分析...")
        self.strategy = CryptoStatArbStrategy(market_data)
        
        pvalue_threshold = self.config['strategy']['cointegration']['pvalue_threshold']
        tradable_pairs = self.strategy.find_cointegrated_pairs(pvalue_threshold=pvalue_threshold)
        
        if len(tradable_pairs) == 0:
            self.logger.error("未找到协整交易对")
            return False
        
        # 计算交易指标
        metrics = self.strategy.calculate_trading_metrics()
        
        # 筛选半衰期
        min_hl = self.config['strategy']['cointegration']['min_half_life']
        max_hl = self.config['strategy']['cointegration']['max_half_life']
        
        valid_pairs = metrics[
            (metrics['HalfLife'] >= min_hl) & 
            (metrics['HalfLife'] <= max_hl)
        ]
        
        if len(valid_pairs) == 0:
            self.logger.warning("没有满足半衰期要求的交易对，使用所有协整交易对")
            valid_pairs = metrics
        
        # 合并结果
        final_pairs = pd.merge(
            tradable_pairs, 
            valid_pairs, 
            left_index=True, 
            right_index=True
        ).sort_values('P-Value')
        
        self.logger.info(f"找到 {len(final_pairs)} 个有效交易对")
        
        # 4. 选择交易对并设置阈值
        max_pairs = self.config['strategy']['pair_selection']['max_pairs']
        threshold_mode = self.config['strategy']['threshold']['mode']
        
        selected_pairs = []
        used_symbols = set()
        no_overlap = self.config['strategy']['pair_selection'].get('no_overlap', True)
        
        for pair in final_pairs.index:
            if len(selected_pairs) >= max_pairs:
                break
            
            symbol1, symbol2 = pair
            
            if no_overlap:
                if symbol1 in used_symbols or symbol2 in used_symbols:
                    continue
                used_symbols.add(symbol1)
                used_symbols.add(symbol2)
            
            selected_pairs.append(pair)
        
        # 设置阈值和参数
        for pair in selected_pairs:
            gamma = final_pairs.at[pair, 'Gamma']
            std = valid_pairs.at[pair, 'Std']
            constant = final_pairs.at[pair, 'Constant']
            
            if threshold_mode == 'fixed':
                sigma_mult = self.config['strategy']['threshold']['fixed']['sigma_multiplier']
                threshold = sigma_mult * std
            else:
                # 使用优化后的阈值（默认 1.5 倍标准差）
                threshold = 1.5 * std
            
            self.pairs_config[pair] = {
                'gamma': gamma,
                'threshold': threshold
            }
            
            self.cointegration_params[pair] = {
                'constant': constant,
                'gamma': gamma,
                'std': std
            }
            
            self.logger.info(f"  {pair[0]}-{pair[1]}: gamma={gamma:.4f}, threshold={threshold:.6f}")
        
        # 5. 初始化交易引擎
        backtest_config = self.config.get('backtest', {})
        initial_capital = backtest_config.get('initial_capital', 100000.0)
        max_position_size = backtest_config.get('max_position_size', 10000.0)
        max_position_pct = max_position_size / initial_capital
        
        state_file = dryrun_config.get('state_file', './data/dryrun_state.json')
        
        self.engine = DryRunEngine(
            initial_capital=initial_capital,
            max_position_pct=max_position_pct,
            commission_rate=backtest_config.get('commission_rate', 0.001),
            slippage_rate=backtest_config.get('slippage_rate', 0.0005),
            state_file=state_file
        )
        
        # 初始化交易对
        self.engine.initialize_pairs(self.pairs_config, self.cointegration_params)
        
        # 6. 设置数据更新回调
        self.data_feed.add_update_callback(self._on_data_update)
        
        self._initialized = True
        self.logger.info("=" * 60)
        self.logger.info("Dry Run 系统初始化完成")
        self.logger.info("=" * 60)
        
        return True
    
    def _on_data_update(self, market_data: pd.DataFrame, timestamp):
        """数据更新回调"""
        if not self._running:
            return
        
        self.logger.debug(f"数据更新: {timestamp}")
        
        # 处理新数据
        trades = self.engine.process_tick(market_data, timestamp)
        
        if trades:
            self.logger.info(f"执行了 {len(trades)} 笔交易")
            for trade in trades:
                self.logger.info(f"  {trade.symbol} {trade.side} {trade.quantity:.4f} @ ${trade.price:.2f}")
    
    def run(self, 
            status_interval: int = 3600,
            recalibrate_interval: int = 86400):
        """
        运行 Dry Run
        
        Parameters:
        -----------
        status_interval : int
            状态报告间隔（秒）
        recalibrate_interval : int
            重新校准协整参数间隔（秒）
        """
        if not self._initialized:
            if not self.initialize():
                return
        
        self._running = True
        self.logger.info("开始 Dry Run 模式...")
        
        # 启动数据流
        self.data_feed.start_streaming()
        
        last_status_time = time.time()
        last_recalibrate_time = time.time()
        
        try:
            while self._running:
                current_time = time.time()
                
                # 定期打印状态
                if current_time - last_status_time >= status_interval:
                    self.engine.print_status()
                    last_status_time = current_time
                
                # 定期重新校准参数
                if current_time - last_recalibrate_time >= recalibrate_interval:
                    self._recalibrate_parameters()
                    last_recalibrate_time = current_time
                
                # 手动更新数据（补充自动更新）
                if self.data_feed.market_data is not None:
                    latest_time = self.data_feed.market_data.index[-1]
                    self.engine.process_tick(self.data_feed.market_data, latest_time)
                
                time.sleep(60)  # 每分钟检查一次
                
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止...")
        finally:
            self.stop()
    
    def _recalibrate_parameters(self):
        """重新校准协整参数"""
        self.logger.info("开始重新校准协整参数...")
        
        try:
            # 使用最新数据重新计算协整关系
            market_data = self.data_feed.market_data
            self.strategy = CryptoStatArbStrategy(market_data)
            
            pvalue_threshold = self.config['strategy']['cointegration']['pvalue_threshold']
            tradable_pairs = self.strategy.find_cointegrated_pairs(pvalue_threshold=pvalue_threshold)
            
            if len(tradable_pairs) == 0:
                self.logger.warning("重新校准失败：未找到协整交易对")
                return
            
            metrics = self.strategy.calculate_trading_metrics()
            
            # 更新现有交易对的参数
            for pair in self.pairs_config.keys():
                if pair in tradable_pairs.index and pair in metrics.index:
                    old_gamma = self.pairs_config[pair]['gamma']
                    new_gamma = tradable_pairs.at[pair, 'Gamma']
                    new_std = metrics.at[pair, 'Std']
                    new_constant = tradable_pairs.at[pair, 'Constant']
                    
                    # 只有当参数变化超过 10% 时才更新
                    if abs(new_gamma - old_gamma) / abs(old_gamma) > 0.1:
                        self.logger.info(f"更新 {pair} 参数: gamma {old_gamma:.4f} -> {new_gamma:.4f}")
                        
                        self.pairs_config[pair]['gamma'] = new_gamma
                        self.pairs_config[pair]['threshold'] = 1.5 * new_std
                        
                        self.cointegration_params[pair] = {
                            'constant': new_constant,
                            'gamma': new_gamma,
                            'std': new_std
                        }
                        
                        # 更新引擎中的状态
                        if pair in self.engine.pair_states:
                            self.engine.pair_states[pair].gamma = new_gamma
                            self.engine.pair_states[pair].threshold = 1.5 * new_std
                        
                        self.engine._cointegration_params[pair] = self.cointegration_params[pair]
            
            self.logger.info("协整参数校准完成")
            
        except Exception as e:
            self.logger.error(f"重新校准失败: {e}")
    
    def stop(self):
        """停止运行"""
        self._running = False
        
        if self.data_feed:
            self.data_feed.stop_streaming()
        
        if self.engine:
            self.engine.save_state()
            self.engine.print_status()
            
            # 导出结果
            output_dir = self.config.get('output', {}).get('results_dir', './results/dryrun')
            self.engine.export_results(output_dir)
        
        self.logger.info("Dry Run 已停止")
    
    def handle_signal(self, signum, frame):
        """处理系统信号"""
        self.logger.info(f"收到信号 {signum}，正在停止...")
        self.stop()
        sys.exit(0)


def load_config(config_path: str = 'config.yaml') -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='加密货币统计套利 Dry Run 模式')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='配置文件路径')
    parser.add_argument('--status-interval', type=int, default=3600,
                       help='状态报告间隔（秒），默认 1 小时')
    parser.add_argument('--recalibrate-interval', type=int, default=86400,
                       help='参数校准间隔（秒），默认 24 小时')
    parser.add_argument('--once', action='store_true',
                       help='只运行一次（用于测试）')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 创建管理器
    manager = DryRunManager(config)
    
    # 设置信号处理
    signal.signal(signal.SIGINT, manager.handle_signal)
    signal.signal(signal.SIGTERM, manager.handle_signal)
    
    print("=" * 60)
    print("加密货币统计套利 - Dry Run 模式")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"状态报告间隔: {args.status_interval} 秒")
    print(f"参数校准间隔: {args.recalibrate_interval} 秒")
    print("=" * 60)
    print("按 Ctrl+C 停止运行")
    print("=" * 60)
    
    if args.once:
        # 只运行一次（测试模式）
        if manager.initialize():
            # 处理当前数据
            if manager.data_feed.market_data is not None:
                latest_time = manager.data_feed.market_data.index[-1]
                manager.engine.process_tick(manager.data_feed.market_data, latest_time)
            manager.engine.print_status()
        manager.stop()
    else:
        # 长期运行
        manager.run(
            status_interval=args.status_interval,
            recalibrate_interval=args.recalibrate_interval
        )


if __name__ == "__main__":
    main()

