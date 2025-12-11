"""
加密货币统计套利工具包
"""

from .binance_data import BinanceDataDownloader
from .crypto_arb_strategy import CryptoStatArbStrategy
from .backtest_engine import BacktestEngine

__all__ = [
    'BinanceDataDownloader',
    'CryptoStatArbStrategy', 
    'BacktestEngine'
]

__version__ = '1.0.0'

