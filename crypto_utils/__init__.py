"""
加密货币统计套利工具包
"""

from .binance_data import BinanceDataDownloader
from .crypto_arb_strategy import CryptoStatArbStrategy
from .backtest_engine import BacktestEngine
from .live_data import LiveDataFeed
from .dryrun_engine import DryRunEngine

__all__ = [
    'BinanceDataDownloader',
    'CryptoStatArbStrategy', 
    'BacktestEngine',
    'LiveDataFeed',
    'DryRunEngine'
]

__version__ = '1.1.0'

