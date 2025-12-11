"""
加密货币统计套利策略
基于协整关系的配对交易策略
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional
import logging

from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import adfuller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CryptoStatArbStrategy:
    """
    加密货币统计套利策略类
    """
    
    def __init__(self, market_data: pd.DataFrame):
        """
        初始化策略
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            市场数据，Multi-index列格式：(symbol, price_type)
        """
        self.market_data = market_data
        self.symbols = list(market_data.columns.get_level_values(level=0).unique())
        self.cointegration_results = None
        self.tradable_pairs = None
        self.z_values = {}
        
        # 检查并报告数据质量
        for symbol in self.symbols:
            nan_count = self.market_data[symbol, 'MidPrice'].isnull().sum()
            if nan_count > 0:
                logger.warning(f"{symbol} 包含 {nan_count} 个NaN值 "
                             f"({nan_count/len(self.market_data)*100:.2f}%)")
        
        logger.info(f"策略初始化完成，共有 {len(self.symbols)} 个交易对")
        
    def fit_ols(self, y: pd.Series, x: pd.Series) -> Tuple[float, float, float, pd.Series]:
        """
        估计长期和短期协整关系
        
        长期关系: y_t = c + gamma * x_t + z_t
        短期关系: y_t - y_(t-1) = alpha * z_(t-1) + epsilon_t
        
        Parameters:
        -----------
        y : pd.Series
            第一个时间序列
        x : pd.Series
            第二个时间序列
            
        Returns:
        --------
        c : float
            常数项
        gamma : float
            对冲比率
        alpha : float
            误差修正速度
        z : pd.Series
            残差序列（误差修正项）
        """
        assert isinstance(y, pd.Series), 'y应为pd.Series类型'
        assert isinstance(x, pd.Series), 'x应为pd.Series类型'
        
        # 处理NaN值：删除任一序列中包含NaN的行
        valid_idx = ~(y.isnull() | x.isnull())
        y = y[valid_idx]
        x = x[valid_idx]
        
        assert len(y) > 0, 'y在清理NaN后没有有效数据'
        assert len(x) > 0, 'x在清理NaN后没有有效数据'
        
        # 长期关系回归
        long_run_ols = OLS(y, add_constant(x))
        long_run_ols_fit = long_run_ols.fit()
        
        c, gamma = long_run_ols_fit.params
        z = long_run_ols_fit.resid
        
        # 短期关系回归
        short_run_ols = OLS(y.diff().iloc[1:], (z.shift().iloc[1:]))
        short_run_ols_fit = short_run_ols.fit()
        
        alpha = short_run_ols_fit.params[0]
        
        return c, gamma, alpha, z
    
    def granger_cointegration_test(self, y: pd.Series, x: pd.Series) -> Tuple[float, float]:
        """
        Engle-Granger协整检验
        
        Parameters:
        -----------
        y : pd.Series
            第一个时间序列
        x : pd.Series
            第二个时间序列
            
        Returns:
        --------
        adfstat : float
            ADF检验统计量（越负说明协整关系越强）
        pvalue : float
            p值（越小说明协整关系越显著）
        """
        c, gamma, alpha, z = self.fit_ols(y, x)
        
        # 对残差进行ADF检验
        adfstat, pvalue, usedlag, nobs, crit_values = adfuller(z, maxlag=1, autolag=None)
        
        return adfstat, pvalue
    
    def find_cointegrated_pairs(self, pvalue_threshold: float = 0.01) -> pd.DataFrame:
        """
        寻找所有协整的交易对
        
        Parameters:
        -----------
        pvalue_threshold : float
            p值阈值，默认0.01
            
        Returns:
        --------
        pd.DataFrame
            协整检验结果
        """
        logger.info("开始寻找协整交易对...")
        
        results = {
            'Pairs': [],
            'Constant': [],
            'Gamma': [],
            'Alpha': [],
            'P-Value': []
        }
        
        self.z_values = {}
        
        for i, symbol1 in enumerate(self.symbols):
            for j, symbol2 in enumerate(self.symbols):
                if i >= j:  # 避免重复和自身配对
                    continue
                    
                try:
                    # 获取价格序列
                    price1 = self.market_data[symbol1, 'MidPrice']
                    price2 = self.market_data[symbol2, 'MidPrice']
                    
                    # 检查NaN比例
                    nan_ratio1 = price1.isnull().sum() / len(price1)
                    nan_ratio2 = price2.isnull().sum() / len(price2)
                    
                    # 如果NaN过多，跳过
                    if nan_ratio1 > 0.1 or nan_ratio2 > 0.1:
                        logger.warning(f"跳过 {symbol1}-{symbol2}: NaN比例过高 "
                                     f"({nan_ratio1*100:.1f}%, {nan_ratio2*100:.1f}%)")
                        continue
                    
                    # 取对数（会在fit_ols中处理NaN）
                    y = np.log(price1.replace(0, np.nan))  # 避免log(0)
                    x = np.log(price2.replace(0, np.nan))
                    
                    constant, gamma, alpha, zvalue = self.fit_ols(y, x)
                    adfstat, pvalue = self.granger_cointegration_test(y, x)
                    
                    pairs = (symbol1, symbol2)
                    results['Pairs'].append(pairs)
                    results['Constant'].append(constant)
                    results['Gamma'].append(gamma)
                    results['Alpha'].append(alpha)
                    results['P-Value'].append(pvalue)
                    
                    self.z_values[pairs] = zvalue
                    
                except Exception as e:
                    logger.warning(f"处理交易对 {symbol1}-{symbol2} 时出错: {e}")
                    continue
        
        self.cointegration_results = pd.DataFrame(results).round(4).set_index('Pairs')
        
        # 筛选可交易的配对
        self.tradable_pairs = self.cointegration_results[
            self.cointegration_results['P-Value'] < pvalue_threshold
        ].sort_values('P-Value')
        
        logger.info(f"找到 {len(self.tradable_pairs)} 个协整交易对 (p-value < {pvalue_threshold})")
        
        return self.tradable_pairs
    
    def calculate_trading_metrics(self) -> pd.DataFrame:
        """
        计算交易指标（均值、标准差、OU参数等）
        
        Returns:
        --------
        pd.DataFrame
            交易指标汇总
        """
        if self.tradable_pairs is None:
            raise ValueError("请先调用 find_cointegrated_pairs() 方法")
            
        metrics = {
            'Pair': [],
            'LongRunMean': [],
            'Std': [],
            'ZeroCrossings': [],
            'HalfLife': []
        }
        
        for pair in self.tradable_pairs.index:
            zvalue = self.z_values[pair]
            
            # 基本统计量
            mean = zvalue.mean()
            std = zvalue.std()
            
            # 零点穿越次数
            zero_crossings = ((np.array(zvalue[:-1]) * np.array(zvalue[1:])) < 0).sum()
            
            # 半衰期估计（均值回归速度）
            # 使用.at而非.loc来避免多维度索引问题
            try:
                alpha = self.tradable_pairs.at[pair, 'Alpha']
            except:
                # 如果.at失败，尝试使用iloc
                pair_idx = self.tradable_pairs.index.get_loc(pair)
                if isinstance(pair_idx, slice):
                    pair_idx = pair_idx.start
                alpha = self.tradable_pairs.iloc[pair_idx]['Alpha']
            
            half_life = -np.log(2) / alpha if alpha < 0 else np.inf
            
            metrics['Pair'].append(pair)
            metrics['LongRunMean'].append(round(mean, 4))
            metrics['Std'].append(round(std, 4))
            metrics['ZeroCrossings'].append(zero_crossings)
            metrics['HalfLife'].append(round(half_life, 2) if half_life != np.inf else np.inf)
        
        metrics_df = pd.DataFrame(metrics).set_index('Pair')
        return metrics_df
    
    def visualize_pair(self, pair: Tuple[str, str], save_path: Optional[str] = None):
        """
        可视化交易对的误差修正项
        
        Parameters:
        -----------
        pair : Tuple[str, str]
            交易对
        save_path : str, optional
            保存路径
        """
        if pair not in self.z_values:
            raise ValueError(f"交易对 {pair} 不存在")
            
        zvalue = self.z_values[pair]
        std = zvalue.std()
        mean = zvalue.mean()
        
        plt.figure(figsize=(15, 5))
        plt.plot(zvalue.index, zvalue, color='r', linewidth=0.8)
        plt.xlabel('时间')
        plt.ylabel('误差修正项 (Z-Value)')
        plt.title(f'{pair[0]} vs {pair[1]} 误差修正项')
        
        # 绘制阈值线
        upper = mean + 1.96 * std
        lower = mean - 1.96 * std
        
        plt.fill_between(zvalue.index, lower, upper, facecolor="dodgerblue", alpha=0.3)
        plt.hlines(upper, zvalue.index[0], zvalue.index[-1], colors='dodgerblue', linestyles='--', label='±1.96σ')
        plt.hlines(lower, zvalue.index[0], zvalue.index[-1], colors='dodgerblue', linestyles='--')
        plt.hlines(mean, zvalue.index[0], zvalue.index[-1], colors='green', linestyles='--', label='均值')
        
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"图表已保存到: {save_path}")
            
        plt.show()
    
    def optimize_threshold(self, 
                          pair: Tuple[str, str],
                          gamma: float,
                          std: float,
                          threshold_range: np.ndarray = None,
                          limit: float = 10000.0) -> pd.DataFrame:
        """
        优化单个交易对的阈值
        
        Parameters:
        -----------
        pair : Tuple[str, str]
            交易对
        gamma : float
            对冲比率
        std : float
            z-value标准差
        threshold_range : np.ndarray
            阈值范围，默认为 [0.5σ, 3.0σ]
        limit : float
            单边最大持仓金额
            
        Returns:
        --------
        pd.DataFrame
            不同阈值下的PnL结果
        """
        if threshold_range is None:
            threshold_range = np.linspace(0.5, 3.0, 10)
            
        symbol1, symbol2 = pair
        results = []
        
        for threshold_multiplier in threshold_range:
            threshold = threshold_multiplier * std
            
            # 计算该阈值下的持仓
            positions1, positions2 = self._calculate_positions(
                symbol1, symbol2, gamma, threshold, limit
            )
            
            # 计算PnL
            pnl = self._calculate_pnl(symbol1, symbol2, positions1, positions2)
            
            results.append({
                'Threshold': round(threshold, 6),
                'ThresholdMultiplier': round(threshold_multiplier, 2),
                'TotalPnL': round(pnl, 2),
                'NumTrades': (np.diff(positions1) != 0).sum()
            })
        
        return pd.DataFrame(results)
    
    def _calculate_positions(self,
                            symbol1: str,
                            symbol2: str,
                            gamma: float,
                            threshold: float,
                            limit: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算给定阈值下的持仓序列
        
        Returns:
        --------
        positions1 : np.ndarray
            symbol1的持仓序列
        positions2 : np.ndarray
            symbol2的持仓序列
        """
        zvalue = self.z_values[(symbol1, symbol2)]
        
        positions1 = []
        positions2 = []
        
        current_position = 0  # 0: 空仓, 1: 多symbol2空symbol1, -1: 空symbol2多symbol1
        current_pos1 = 0
        current_pos2 = 0
        
        for idx, time in enumerate(self.market_data.index):
            data = self.market_data.loc[time]
            z = zvalue.iloc[idx]
            
            bid_price_1 = data[symbol1, 'BidPrice']
            ask_price_1 = data[symbol1, 'AskPrice']
            bid_price_2 = data[symbol2, 'BidPrice']
            ask_price_2 = data[symbol2, 'AskPrice']
            
            bid_vol_1 = data[symbol1, 'BidVolume']
            ask_vol_1 = data[symbol1, 'AskVolume']
            bid_vol_2 = data[symbol2, 'BidVolume']
            ask_vol_2 = data[symbol2, 'AskVolume']
            
            # 平仓条件
            if ((z <= 0) and (current_position == 1)) or ((z >= 0) and (current_position == -1)):
                current_pos1 = 0
                current_pos2 = 0
                current_position = 0
            
            # 开仓条件：多symbol2，空symbol1
            if (z >= threshold) and (current_position == 0):
                hedge_ratio = gamma * (bid_price_1 / ask_price_2)
                max_order_1 = np.floor(limit / bid_price_1)
                max_order_2 = np.floor(limit / ask_price_2)
                
                trade = np.floor(min(
                    bid_vol_1 * hedge_ratio,
                    ask_vol_2,
                    max_order_1 * hedge_ratio,
                    max_order_2
                ))
                
                current_pos1 = -np.floor(trade / hedge_ratio)
                current_pos2 = trade
                current_position = 1
            
            # 开仓条件：空symbol2，多symbol1
            elif (z <= -threshold) and (current_position == 0):
                hedge_ratio = gamma * (ask_price_1 / bid_price_2)
                max_order_1 = np.floor(limit / ask_price_1)
                max_order_2 = np.floor(limit / bid_price_2)
                
                trade = np.floor(min(
                    ask_vol_1 * hedge_ratio,
                    bid_vol_2,
                    max_order_1 * hedge_ratio,
                    max_order_2
                ))
                
                current_pos1 = np.floor(trade / hedge_ratio)
                current_pos2 = -trade
                current_position = -1
            
            positions1.append(current_pos1)
            positions2.append(current_pos2)
        
        return np.array(positions1), np.array(positions2)
    
    def _calculate_pnl(self,
                      symbol1: str,
                      symbol2: str,
                      positions1: np.ndarray,
                      positions2: np.ndarray) -> float:
        """
        计算PnL
        
        Returns:
        --------
        float
            总PnL
        """
        # 持仓变化
        pos_diff1 = np.diff(positions1, prepend=0)
        pos_diff2 = np.diff(positions2, prepend=0)
        
        # 价格
        ask_price_1 = self.market_data[symbol1, 'AskPrice'].values
        bid_price_1 = self.market_data[symbol1, 'BidPrice'].values
        ask_price_2 = self.market_data[symbol2, 'AskPrice'].values
        bid_price_2 = self.market_data[symbol2, 'BidPrice'].values
        
        # 计算每笔交易的成本
        # 买入用ask价格，卖出用bid价格
        pnl1 = np.where(pos_diff1 > 0, 
                       pos_diff1 * -ask_price_1,  # 买入是负现金流
                       pos_diff1 * -bid_price_1)   # 卖出是正现金流
        
        pnl2 = np.where(pos_diff2 > 0,
                       pos_diff2 * -ask_price_2,
                       pos_diff2 * -bid_price_2)
        
        total_pnl = pnl1.sum() + pnl2.sum()
        
        return total_pnl


if __name__ == "__main__":
    # 使用示例
    logger.info("加密货币统计套利策略模块")

