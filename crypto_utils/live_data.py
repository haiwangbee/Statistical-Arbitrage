"""
实时数据获取模块
支持从 Binance 获取实时 K 线数据用于 Dry Run
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Optional, Dict, Callable
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiveDataFeed:
    """
    实时数据源
    用于获取和维护最新的市场数据
    """
    
    def __init__(self, 
                 symbols: List[str],
                 interval: str = '1h',
                 lookback_hours: int = 168,
                 use_testnet: bool = False):
        """
        初始化实时数据源
        
        Parameters:
        -----------
        symbols : List[str]
            交易对列表
        interval : str
            K 线间隔 (1m, 5m, 15m, 1h, 4h, 1d)
        lookback_hours : int
            回溯小时数，用于初始化历史数据
        use_testnet : bool
            是否使用测试网
        """
        try:
            from binance.client import Client
            self.Client = Client
        except ImportError:
            logger.error("请先安装 python-binance: pip install python-binance")
            raise
        
        self.symbols = symbols
        self.interval = interval
        self.lookback_hours = lookback_hours
        self.use_testnet = use_testnet
        
        # 初始化客户端
        self.client = self.Client("", "")
        
        # 数据存储
        self.market_data: Optional[pd.DataFrame] = None
        self._last_update_time: Optional[datetime] = None
        
        # 间隔映射（毫秒）
        self.interval_ms = self._get_interval_ms(interval)
        
        # 回调函数
        self._on_update_callbacks: List[Callable] = []
        
        # 运行状态
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        
        logger.info(f"LiveDataFeed 初始化完成 - {len(symbols)} 个交易对, 间隔: {interval}")
    
    def _get_interval_ms(self, interval: str) -> int:
        """获取间隔的毫秒数"""
        mapping = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '8h': 8 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
        }
        return mapping.get(interval, 60 * 60 * 1000)
    
    def _get_interval_seconds(self) -> int:
        """获取间隔的秒数"""
        return self.interval_ms // 1000
    
    def add_update_callback(self, callback: Callable):
        """添加数据更新回调"""
        self._on_update_callbacks.append(callback)
    
    def fetch_historical_data(self) -> pd.DataFrame:
        """
        获取历史数据用于初始化
        
        Returns:
        --------
        pd.DataFrame
            Multi-index 格式的市场数据
        """
        logger.info(f"获取历史数据，回溯 {self.lookback_hours} 小时...")
        
        start_time = datetime.now() - timedelta(hours=self.lookback_hours)
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        data_dict = {}
        valid_symbols = []
        
        for symbol in self.symbols:
            try:
                klines = self.client.get_historical_klines(
                    symbol,
                    self.interval,
                    start_str
                )
                
                if len(klines) == 0:
                    logger.warning(f"跳过 {symbol}: 无数据")
                    continue
                
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                
                data_dict[symbol] = df[['open', 'high', 'low', 'close', 'volume']]
                valid_symbols.append(symbol)
                
                time.sleep(0.1)  # 避免请求过快
                
            except Exception as e:
                logger.warning(f"获取 {symbol} 数据失败: {e}")
                continue
        
        if len(valid_symbols) == 0:
            raise ValueError("所有交易对获取数据失败")
        
        # 找到公共时间索引
        common_index = None
        for symbol in valid_symbols:
            if common_index is None:
                common_index = data_dict[symbol].index
            else:
                common_index = common_index.intersection(data_dict[symbol].index)
        
        # 构建 Multi-index DataFrame
        spread = 0.0005  # 模拟点差
        all_data = {}
        
        for symbol in valid_symbols:
            df = data_dict[symbol].loc[common_index]
            
            all_data[(symbol, 'BidPrice')] = df['close'] * (1 - spread)
            all_data[(symbol, 'AskPrice')] = df['close'] * (1 + spread)
            all_data[(symbol, 'MidPrice')] = df['close']
            all_data[(symbol, 'BidVolume')] = df['volume'] / 2
            all_data[(symbol, 'AskVolume')] = df['volume'] / 2
            all_data[(symbol, 'MidVolume')] = df['volume']
            all_data[(symbol, 'High')] = df['high']
            all_data[(symbol, 'Low')] = df['low']
        
        result_df = pd.DataFrame(all_data)
        result_df.index.name = 'time'
        result_df = result_df.sort_index(axis=1)
        result_df = result_df.dropna()
        
        self.market_data = result_df
        self._last_update_time = datetime.now()
        self.symbols = valid_symbols  # 更新为有效的交易对
        
        logger.info(f"历史数据获取完成 - 形状: {result_df.shape}, "
                   f"时间范围: {result_df.index[0]} 到 {result_df.index[-1]}")
        
        return result_df
    
    def fetch_latest_candle(self, symbol: str) -> Optional[Dict]:
        """
        获取最新的 K 线数据
        
        Parameters:
        -----------
        symbol : str
            交易对
            
        Returns:
        --------
        Dict or None
            最新 K 线数据
        """
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=self.interval,
                limit=2  # 获取最近 2 根，确保拿到完整的最新一根
            )
            
            if len(klines) < 2:
                return None
            
            # 使用倒数第二根（已完成的 K 线）
            kline = klines[-2]
            
            return {
                'timestamp': pd.to_datetime(kline[0], unit='ms'),
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            }
            
        except Exception as e:
            logger.warning(f"获取 {symbol} 最新 K 线失败: {e}")
            return None
    
    def update_market_data(self) -> bool:
        """
        更新市场数据（添加最新的 K 线）
        
        Returns:
        --------
        bool
            是否成功更新
        """
        if self.market_data is None:
            logger.warning("请先调用 fetch_historical_data() 初始化数据")
            return False
        
        spread = 0.0005
        new_data = {}
        latest_timestamp = None
        
        for symbol in self.symbols:
            candle = self.fetch_latest_candle(symbol)
            if candle is None:
                return False
            
            if latest_timestamp is None:
                latest_timestamp = candle['timestamp']
            
            new_data[(symbol, 'BidPrice')] = candle['close'] * (1 - spread)
            new_data[(symbol, 'AskPrice')] = candle['close'] * (1 + spread)
            new_data[(symbol, 'MidPrice')] = candle['close']
            new_data[(symbol, 'BidVolume')] = candle['volume'] / 2
            new_data[(symbol, 'AskVolume')] = candle['volume'] / 2
            new_data[(symbol, 'MidVolume')] = candle['volume']
            new_data[(symbol, 'High')] = candle['high']
            new_data[(symbol, 'Low')] = candle['low']
            
            time.sleep(0.05)  # 避免请求过快
        
        # 检查是否是新的 K 线
        if latest_timestamp in self.market_data.index:
            # 更新现有 K 线
            for key, value in new_data.items():
                self.market_data.loc[latest_timestamp, key] = value
            logger.debug(f"更新现有 K 线: {latest_timestamp}")
        else:
            # 添加新 K 线
            new_row = pd.DataFrame(new_data, index=[latest_timestamp])
            self.market_data = pd.concat([self.market_data, new_row])
            self.market_data = self.market_data.sort_index()
            
            # 移除过旧的数据，保持窗口大小
            max_rows = self.lookback_hours * 2  # 保留 2 倍窗口
            if len(self.market_data) > max_rows:
                self.market_data = self.market_data.iloc[-max_rows:]
            
            logger.info(f"添加新 K 线: {latest_timestamp}")
            
            # 触发回调
            for callback in self._on_update_callbacks:
                try:
                    callback(self.market_data, latest_timestamp)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")
        
        self._last_update_time = datetime.now()
        return True
    
    def start_streaming(self, update_interval_seconds: Optional[int] = None):
        """
        启动实时数据流（在后台线程中运行）
        
        Parameters:
        -----------
        update_interval_seconds : int, optional
            更新间隔（秒），默认为 K 线间隔
        """
        if self._running:
            logger.warning("数据流已在运行中")
            return
        
        if update_interval_seconds is None:
            # 默认在 K 线完成后 10 秒更新
            update_interval_seconds = self._get_interval_seconds()
        
        self._running = True
        
        def _stream_loop():
            logger.info(f"数据流启动，更新间隔: {update_interval_seconds} 秒")
            
            while self._running:
                try:
                    # 计算到下一个 K 线完成的时间
                    now = datetime.now()
                    interval_seconds = self._get_interval_seconds()
                    
                    # 计算当前 K 线开始时间
                    current_candle_start = now.replace(
                        minute=(now.minute // (interval_seconds // 60)) * (interval_seconds // 60),
                        second=0,
                        microsecond=0
                    ) if interval_seconds < 3600 else now.replace(
                        minute=0,
                        second=0,
                        microsecond=0
                    )
                    
                    # 下一个 K 线开始时间
                    next_candle = current_candle_start + timedelta(seconds=interval_seconds)
                    
                    # 等待到下一个 K 线开始后 10 秒
                    wait_until = next_candle + timedelta(seconds=10)
                    wait_seconds = (wait_until - now).total_seconds()
                    
                    if wait_seconds > 0:
                        logger.debug(f"等待 {wait_seconds:.0f} 秒直到下一次更新")
                        time.sleep(min(wait_seconds, update_interval_seconds))
                    
                    # 更新数据
                    self.update_market_data()
                    
                except Exception as e:
                    logger.error(f"数据流错误: {e}")
                    time.sleep(60)  # 出错后等待 1 分钟重试
        
        self._update_thread = threading.Thread(target=_stream_loop, daemon=True)
        self._update_thread.start()
    
    def stop_streaming(self):
        """停止实时数据流"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        logger.info("数据流已停止")
    
    def get_current_prices(self) -> Dict[str, float]:
        """
        获取当前所有交易对的价格
        
        Returns:
        --------
        Dict[str, float]
            {symbol: price}
        """
        if self.market_data is None or len(self.market_data) == 0:
            return {}
        
        prices = {}
        for symbol in self.symbols:
            try:
                prices[symbol] = self.market_data[symbol, 'MidPrice'].iloc[-1]
            except:
                pass
        
        return prices
    
    @property
    def last_update_time(self) -> Optional[datetime]:
        """获取最后更新时间"""
        return self._last_update_time
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


if __name__ == "__main__":
    # 测试代码
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    feed = LiveDataFeed(
        symbols=symbols,
        interval='1h',
        lookback_hours=24
    )
    
    # 获取历史数据
    data = feed.fetch_historical_data()
    print(f"历史数据形状: {data.shape}")
    print(data.tail())
    
    # 获取当前价格
    prices = feed.get_current_prices()
    print(f"\n当前价格: {prices}")

