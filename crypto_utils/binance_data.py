"""
Binance数据下载模块
支持下载历史K线数据用于回测
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceDataDownloader:
    """
    Binance历史数据下载器
    """
    
    def __init__(self, use_testnet: bool = False):
        """
        初始化Binance数据下载器
        
        Parameters:
        -----------
        use_testnet : bool
            是否使用测试网
        """
        try:
            from binance.client import Client
            self.Client = Client
        except ImportError:
            logger.error("请先安装python-binance: pip install python-binance")
            raise
            
        self.use_testnet = use_testnet
        # 不需要API密钥就可以下载历史数据
        self.client = self.Client("", "")
        
    def get_historical_klines(self, 
                             symbol: str, 
                             interval: str, 
                             start_time: str,
                             end_time: Optional[str] = None) -> pd.DataFrame:
        """
        下载历史K线数据
        
        Parameters:
        -----------
        symbol : str
            交易对符号，例如 'BTCUSDT'
        interval : str
            K线时间间隔，例如 '1m', '5m', '1h', '1d'
        start_time : str
            开始时间，格式：'2023-01-01'
        end_time : str, optional
            结束时间，格式：'2023-12-31'，默认为当前时间
            
        Returns:
        --------
        pd.DataFrame
            包含OHLCV数据的DataFrame
        """
        logger.info(f"开始下载 {symbol} 的历史数据，时间间隔：{interval}")
        
        try:
            # 获取K线数据
            klines = self.client.get_historical_klines(
                symbol, 
                interval, 
                start_time,
                end_time
            )
            
            # 转换为DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # 数据类型转换
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            # 只保留需要的列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"成功下载 {len(df)} 条数据")
            return df
            
        except Exception as e:
            logger.error(f"下载数据失败: {e}")
            raise
            
    def download_multiple_symbols(self,
                                  symbols: List[str],
                                  interval: str,
                                  start_time: str,
                                  end_time: Optional[str] = None,
                                  save_path: Optional[str] = None) -> dict:
        """
        批量下载多个交易对的历史数据
        
        Parameters:
        -----------
        symbols : List[str]
            交易对列表，例如 ['BTCUSDT', 'ETHUSDT']
        interval : str
            K线时间间隔
        start_time : str
            开始时间
        end_time : str, optional
            结束时间
        save_path : str, optional
            保存路径，如果提供则保存为CSV文件
            
        Returns:
        --------
        dict
            {symbol: DataFrame} 的字典
        """
        data_dict = {}
        
        for symbol in symbols:
            try:
                df = self.get_historical_klines(symbol, interval, start_time, end_time)
                data_dict[symbol] = df
                
                if save_path:
                    file_path = f"{save_path}/{symbol}_{interval}.csv"
                    df.to_csv(file_path)
                    logger.info(f"已保存数据到: {file_path}")
                    
                # 避免请求过快
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"下载 {symbol} 失败: {e}")
                continue
                
        return data_dict
    
    def prepare_pairs_data(self, 
                          symbols: List[str],
                          interval: str,
                          start_time: str,
                          end_time: Optional[str] = None,
                          drop_nan_threshold: float = 0.1) -> pd.DataFrame:
        """
        准备配对交易所需的数据格式
        模拟原项目中的bid/ask价格结构
        
        Parameters:
        -----------
        symbols : List[str]
            交易对列表
        interval : str
            K线时间间隔
        start_time : str
            开始时间
        end_time : str, optional
            结束时间
        drop_nan_threshold : float
            NaN比例阈值，超过此比例的交易对将被剔除（默认10%）
            
        Returns:
        --------
        pd.DataFrame
            Multi-index列的DataFrame，包含每个交易对的BidPrice, AskPrice, MidPrice等
        """
        data_dict = self.download_multiple_symbols(symbols, interval, start_time, end_time)
        
        # 检查数据质量，剔除NaN过多的交易对
        valid_symbols = []
        for symbol, df in data_dict.items():
            nan_ratio = df['close'].isnull().sum() / len(df)
            if nan_ratio > drop_nan_threshold:
                logger.warning(f"剔除 {symbol}: NaN比例过高 ({nan_ratio*100:.2f}%)")
            else:
                valid_symbols.append(symbol)
        
        if len(valid_symbols) == 0:
            raise ValueError("所有交易对的数据质量都不符合要求")
        
        logger.info(f"保留 {len(valid_symbols)}/{len(symbols)} 个交易对")
        
        # 创建multi-index DataFrame
        all_data = {}
        
        # 1. 找到公共时间索引
        common_index = None
        for symbol in valid_symbols:
            if common_index is None:
                common_index = data_dict[symbol].index
            else:
                common_index = common_index.intersection(data_dict[symbol].index)
                
        logger.info(f"公共时间段数据点: {len(common_index)}")
        
        if len(common_index) == 0:
             raise ValueError("交易对之间没有重叠的时间段")

        for symbol in valid_symbols:
            # 只取公共时间段的数据
            df = data_dict[symbol].loc[common_index]
            
            # 使用close价格作为中间价
            # 模拟bid/ask spread (通常为0.01-0.1%)
            spread = 0.0005  # 0.05% spread
            
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
        
        # 按列名排序
        result_df = result_df.sort_index(axis=1)
        
        # 再次清理任何可能的NaN
        result_df = result_df.dropna()
        
        logger.info(f"成功准备配对交易数据，形状：{result_df.shape}")
        return result_df
    
    def get_top_volume_pairs(self, 
                            quote_asset: str = 'USDT',
                            top_n: int = 20) -> List[str]:
        """
        获取交易量最大的前N个交易对
        
        Parameters:
        -----------
        quote_asset : str
            计价货币，例如 'USDT', 'BTC'
        top_n : int
            返回前N个交易对
            
        Returns:
        --------
        List[str]
            交易对列表
        """
        try:
            # 获取24小时ticker数据
            tickers = self.client.get_ticker()
            
            # 筛选特定计价货币的交易对
            filtered_tickers = [
                t for t in tickers 
                if t['symbol'].endswith(quote_asset) and 
                float(t['quoteVolume']) > 0
            ]
            
            # 按交易量排序
            sorted_tickers = sorted(
                filtered_tickers, 
                key=lambda x: float(x['quoteVolume']), 
                reverse=True
            )
            
            # 返回前N个
            top_symbols = [t['symbol'] for t in sorted_tickers[:top_n]]
            
            logger.info(f"获取到交易量前{top_n}的交易对：{top_symbols}")
            return top_symbols
            
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            # 返回默认的主流交易对
            default_pairs = [
                f'{coin}{quote_asset}' for coin in 
                ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'DOGE', 
                 'AVAX', 'MATIC', 'LINK', 'UNI', 'LTC', 'ATOM', 'ETC']
            ]
            return default_pairs[:top_n]


if __name__ == "__main__":
    # 使用示例
    downloader = BinanceDataDownloader()
    
    # 示例1：下载单个交易对
    # btc_data = downloader.get_historical_klines(
    #     symbol='BTCUSDT',
    #     interval='1h',
    #     start_time='2024-01-01',
    #     end_time='2024-01-31'
    # )
    # print(btc_data.head())
    
    # 示例2：获取热门交易对
    top_pairs = downloader.get_top_volume_pairs(quote_asset='USDT', top_n=10)
    print("交易量前10的交易对：", top_pairs)
    
    # 示例3：准备配对交易数据
    # pairs_data = downloader.prepare_pairs_data(
    #     symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
    #     interval='1h',
    #     start_time='2024-01-01',
    #     end_time='2024-01-31'
    # )
    # print(pairs_data.head())

