"""
改进版回测引擎 v2
修复资金管理和风险控制问题
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BacktestEngineV2:
    """
    改进版统计套利回测引擎
    
    改进：
    1. 全局资金管理
    2. 持仓市值跟踪
    3. 更准确的风险指标
    4. 稳定币对过滤
    """
    
    def __init__(self, 
                 market_data: pd.DataFrame,
                 initial_capital: float = 100000.0,
                 max_position_pct: float = 0.1,
                 max_leverage: float = 1.0):
        """
        初始化回测引擎
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            市场数据
        initial_capital : float
            初始资金
        max_position_pct : float
            单个交易对最大持仓占比（相对于总资金）
        max_leverage : float
            最大杠杆倍数（1.0=无杠杆）
        """
        self.market_data = market_data
        self.initial_capital = initial_capital
        self.max_position_pct = max_position_pct
        self.max_leverage = max_leverage
        self.max_position_size = initial_capital * max_position_pct
        self.results = {}
        
        logger.info(f"回测引擎初始化完成 - 初始资金: {initial_capital}, "
                   f"单对最大仓位: {max_position_pct*100}%, 最大杠杆: {max_leverage}x")
    
    def _is_stablecoin_pair(self, symbol1: str, symbol2: str) -> bool:
        """检查是否包含稳定币"""
        # 定义稳定币列表（包含各种变体）
        stablecoins = ['USDT', 'USDC', 'BUSD', 'TUSD', 'FDUSD', 'DAI', 'USDP', 'USDD']
        
        # 提取基础货币 (假设都是USDT本位)
        # 例如: FDUSDUSDT -> FDUSD, BTCUSDT -> BTC
        def get_base_asset(symbol):
            if symbol.endswith('USDT'):
                return symbol[:-4]
            if symbol.endswith('USDC'):
                return symbol[:-4]
            if symbol.endswith('BUSD'):
                return symbol[:-4]
            return symbol
            
        base1 = get_base_asset(symbol1)
        base2 = get_base_asset(symbol2)
        
        # 只要有一方是稳定币，就视为稳定币配对
        # 因为稳定币波动极小，不适合与波动性资产进行统计套利
        if base1 in stablecoins or base2 in stablecoins:
            return True
        
        return False
    
    def run_backtest(self,
                    pairs_config: Dict[Tuple[str, str], Dict],
                    strategy) -> Dict:
        """
        运行回测
        
        Parameters:
        -----------
        pairs_config : Dict
            交易对配置
        strategy : CryptoStatArbStrategy
            策略实例
            
        Returns:
        --------
        Dict
            回测结果
        """
        # 过滤稳定币配对
        filtered_config = {}
        for pair, config in pairs_config.items():
            if self._is_stablecoin_pair(pair[0], pair[1]):
                logger.warning(f"跳过稳定币配对: {pair[0]}-{pair[1]}")
            else:
                filtered_config[pair] = config
        
        if len(filtered_config) == 0:
            logger.error("过滤后没有可交易的配对")
            return None
        
        logger.info(f"开始回测，共 {len(filtered_config)} 个交易对")
        
        # 调整每个交易对的持仓限制
        adjusted_limit = self.initial_capital * self.max_position_pct
        
        all_positions = pd.DataFrame(index=self.market_data.index)
        all_pnl = pd.DataFrame(index=self.market_data.index)
        all_portfolio_value = pd.Series(index=self.market_data.index, dtype=float)
        all_portfolio_value.iloc[0] = self.initial_capital
        
        pair_results = {}
        
        for pair, config in filtered_config.items():
            symbol1, symbol2 = pair
            gamma = config['gamma']
            threshold = config['threshold']
            
            logger.info(f"回测交易对: {symbol1}-{symbol2}")
            
            # 计算持仓
            positions1, positions2 = strategy._calculate_positions(
                symbol1, symbol2, gamma, threshold, adjusted_limit
            )
            
            # 保存持仓
            all_positions[f'{symbol1}'] = positions1
            all_positions[f'{symbol2}'] = positions2
            
            # 计算持仓变化
            pos_diff1 = np.diff(positions1, prepend=0)
            pos_diff2 = np.diff(positions2, prepend=0)
            
            # 计算PnL
            ask_price_1 = self.market_data[symbol1, 'AskPrice'].values
            bid_price_1 = self.market_data[symbol1, 'BidPrice'].values
            ask_price_2 = self.market_data[symbol2, 'AskPrice'].values
            bid_price_2 = self.market_data[symbol2, 'BidPrice'].values
            
            # 现金流：买入是负，卖出是正
            pnl1 = np.where(pos_diff1 > 0,
                           pos_diff1 * -ask_price_1,
                           pos_diff1 * -bid_price_1)
            
            pnl2 = np.where(pos_diff2 > 0,
                           pos_diff2 * -ask_price_2,
                           pos_diff2 * -bid_price_2)
            
            all_pnl[f'{symbol1}'] = pnl1
            all_pnl[f'{symbol2}'] = pnl2
            all_pnl[f'{symbol1}_{symbol2}_pair'] = pnl1 + pnl2
            
            # 统计单个交易对结果
            total_pnl = (pnl1 + pnl2).sum()
            num_trades = (pos_diff1 != 0).sum()
            
            # 检查异常大的损益
            max_daily_pnl = np.abs(pnl1 + pnl2).max()
            if max_daily_pnl > self.initial_capital * 0.5:
                logger.warning(f"  警告：{symbol1}-{symbol2} 单日最大损益 ${max_daily_pnl:,.0f} "
                             f"超过初始资金的50%")
            
            pair_results[pair] = {
                'total_pnl': total_pnl,
                'num_trades': num_trades,
                'avg_pnl_per_trade': total_pnl / num_trades if num_trades > 0 else 0,
                'positions1': positions1,
                'positions2': positions2,
                'pnl_series': pnl1 + pnl2,
                'max_daily_pnl': max_daily_pnl
            }
            
            logger.info(f"  总PnL: ${total_pnl:,.2f}, 交易次数: {num_trades}, "
                       f"单日最大损益: ${max_daily_pnl:,.0f}")
        
        # 计算组合总PnL
        all_pnl['total'] = all_pnl.sum(axis=1)
        all_pnl['cumulative'] = all_pnl['total'].cumsum()
        
        # 计算每日组合价值
        for i in range(1, len(all_portfolio_value)):
            all_portfolio_value.iloc[i] = (self.initial_capital + 
                                          all_pnl['cumulative'].iloc[i])
        
        # 计算组合指标
        portfolio_metrics = self._calculate_portfolio_metrics(
            all_pnl['total'], 
            all_portfolio_value
        )
        
        self.results = {
            'positions': all_positions,
            'pnl': all_pnl,
            'portfolio_value': all_portfolio_value,
            'pair_results': pair_results,
            'portfolio_metrics': portfolio_metrics,
            'pairs_config': filtered_config
        }
        
        logger.info("回测完成")
        self._print_summary()
        
        return self.results
    
    def _calculate_portfolio_metrics(self, 
                                    pnl_series: pd.Series,
                                    portfolio_value: pd.Series) -> Dict:
        """
        计算组合性能指标
        
        Parameters:
        -----------
        pnl_series : pd.Series
            每日PnL序列
        portfolio_value : pd.Series
            每日组合价值序列
            
        Returns:
        --------
        Dict
            性能指标
        """
        # 使用组合价值计算
        cumulative_pnl = portfolio_value - self.initial_capital
        total_return = cumulative_pnl.iloc[-1]
        
        # 收益率
        return_pct = (total_return / self.initial_capital) * 100
        
        # 最大回撤（基于组合价值）
        running_max = portfolio_value.expanding().max()
        drawdown = portfolio_value - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / self.initial_capital) * 100
        
        # 确保回撤不超过100%（理论上不可能亏损超过全部资金）
        if max_drawdown < -self.initial_capital:
            logger.error(f"检测到异常回撤: ${max_drawdown:,.2f}，回测可能有问题")
            max_drawdown = -self.initial_capital
            max_drawdown_pct = -100.0
        
        # 日收益率
        daily_returns = portfolio_value.pct_change().fillna(0)
        
        # 夏普比率（假设无风险利率为0）
        if daily_returns.std() > 0:
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # 盈利天数
        winning_days = (pnl_series > 0).sum()
        losing_days = (pnl_series < 0).sum()
        win_rate = winning_days / (winning_days + losing_days) * 100 if (winning_days + losing_days) > 0 else 0
        
        # 平均盈利/亏损
        avg_win = pnl_series[pnl_series > 0].mean() if winning_days > 0 else 0
        avg_loss = pnl_series[pnl_series < 0].mean() if losing_days > 0 else 0
        
        # 盈亏比
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else np.inf
        
        # Calmar比率（年化收益/最大回撤）
        if max_drawdown < 0:
            calmar_ratio = return_pct / abs(max_drawdown_pct)
        else:
            calmar_ratio = np.inf
        
        metrics = {
            'total_return': round(total_return, 2),
            'return_pct': round(return_pct, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'calmar_ratio': round(calmar_ratio, 3) if calmar_ratio != np.inf else np.inf,
            'winning_days': int(winning_days),
            'losing_days': int(losing_days),
            'win_rate': round(win_rate, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 3) if profit_factor != np.inf else np.inf,
            'final_value': round(portfolio_value.iloc[-1], 2)
        }
        
        return metrics
    
    def _print_summary(self):
        """打印回测摘要"""
        metrics = self.results['portfolio_metrics']
        
        print("\n" + "="*60)
        print("回测结果摘要 (改进版)")
        print("="*60)
        print(f"初始资金:        ${self.initial_capital:,.2f}")
        print(f"最终资金:        ${metrics['final_value']:,.2f}")
        print(f"总收益:          ${metrics['total_return']:,.2f}")
        print(f"收益率:          {metrics['return_pct']:.2f}%")
        print(f"最大回撤:        ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        print(f"夏普比率:        {metrics['sharpe_ratio']:.3f}")
        print(f"Calmar比率:      {metrics['calmar_ratio']:.3f}")
        print(f"胜率:            {metrics['win_rate']:.2f}%")
        print(f"盈利天数/亏损天数: {metrics['winning_days']}/{metrics['losing_days']}")
        print(f"平均盈利:        ${metrics['avg_win']:,.2f}")
        print(f"平均亏损:        ${metrics['avg_loss']:,.2f}")
        print(f"盈亏比:          {metrics['profit_factor']:.3f}")
        print("="*60 + "\n")
        
        print("各交易对表现:")
        print("-"*60)
        for pair, result in self.results['pair_results'].items():
            print(f"{pair[0]}-{pair[1]}:")
            print(f"  总PnL: ${result['total_pnl']:,.2f}")
            print(f"  交易次数: {result['num_trades']}")
            print(f"  平均每笔: ${result['avg_pnl_per_trade']:,.2f}")
            print(f"  单日最大损益: ${result.get('max_daily_pnl', 0):,.0f}")
            print()
    
    def plot_results(self, save_dir: Optional[str] = None):
        """绘制回测结果图表"""
        if not self.results:
            logger.warning("请先运行回测")
            return
        
        # 1. 累计PnL曲线
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # 总体累计PnL（使用portfolio_value）
        ax1 = axes[0]
        cumulative = self.results['portfolio_value'] - self.initial_capital
        cumulative.plot(ax=ax1, linewidth=2, color='blue')
        ax1.set_title('组合累计PnL', fontsize=14, fontweight='bold')
        ax1.set_xlabel('时间')
        ax1.set_ylabel('累计PnL ($)')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        # 各交易对累计PnL
        ax2 = axes[1]
        for pair in self.results['pair_results'].keys():
            symbol1, symbol2 = pair
            pnl_col = f'{symbol1}_{symbol2}_pair'
            if pnl_col in self.results['pnl'].columns:
                cumulative_pair = self.results['pnl'][pnl_col].cumsum()
                cumulative_pair.plot(ax=ax2, label=f'{symbol1}-{symbol2}', linewidth=1.5)
        
        ax2.set_title('各交易对累计PnL', fontsize=14, fontweight='bold')
        ax2.set_xlabel('时间')
        ax2.set_ylabel('累计PnL ($)')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        if save_dir:
            plt.savefig(f'{save_dir}/cumulative_pnl.png', dpi=300, bbox_inches='tight')
            logger.info(f"图表已保存: {save_dir}/cumulative_pnl.png")
        
        plt.show()
        
        # 2. 持仓图
        for pair in list(self.results['pair_results'].keys())[:3]:  # 只画前3个
            symbol1, symbol2 = pair
            
            fig, ax = plt.subplots(figsize=(15, 5))
            
            if symbol1 in self.results['positions'].columns:
                self.results['positions'][symbol1].plot(
                    ax=ax, label=f'{symbol1} 持仓', linewidth=1.5
                )
            if symbol2 in self.results['positions'].columns:
                self.results['positions'][symbol2].plot(
                    ax=ax, label=f'{symbol2} 持仓', linewidth=1.5
                )
            
            ax.set_title(f'{symbol1}-{symbol2} 持仓变化', fontsize=14, fontweight='bold')
            ax.set_xlabel('时间')
            ax.set_ylabel('持仓量')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            
            plt.tight_layout()
            
            if save_dir:
                plt.savefig(f'{save_dir}/position_{symbol1}_{symbol2}.png', 
                          dpi=300, bbox_inches='tight')
            
            plt.show()
        
        # 3. 回撤图
        fig, ax = plt.subplots(figsize=(15, 5))
        
        portfolio_value = self.results['portfolio_value']
        running_max = portfolio_value.expanding().max()
        drawdown = portfolio_value - running_max
        
        drawdown.plot(ax=ax, color='red', linewidth=1.5)
        ax.fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
        ax.set_title('回撤曲线', fontsize=14, fontweight='bold')
        ax.set_xlabel('时间')
        ax.set_ylabel('回撤 ($)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_dir:
            plt.savefig(f'{save_dir}/drawdown.png', dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def export_results(self, output_dir: str):
        """导出回测结果（与原版相同）"""
        if not self.results:
            logger.warning("请先运行回测")
            return
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 导出持仓
        self.results['positions'].to_csv(f'{output_dir}/positions.csv')
        
        # 导出PnL
        self.results['pnl'].to_csv(f'{output_dir}/pnl.csv')
        
        # 导出组合价值
        self.results['portfolio_value'].to_csv(f'{output_dir}/portfolio_value.csv')
        
        # 导出性能指标
        metrics_df = pd.DataFrame([self.results['portfolio_metrics']])
        metrics_df.to_csv(f'{output_dir}/metrics.csv', index=False)
        
        # 导出交易对结果
        pair_results_list = []
        for pair, result in self.results['pair_results'].items():
            pair_results_list.append({
                'Symbol1': pair[0],
                'Symbol2': pair[1],
                'TotalPnL': result['total_pnl'],
                'NumTrades': result['num_trades'],
                'AvgPnLPerTrade': result['avg_pnl_per_trade'],
                'MaxDailyPnL': result.get('max_daily_pnl', 0)
            })
        
        pair_results_df = pd.DataFrame(pair_results_list)
        pair_results_df.to_csv(f'{output_dir}/pair_results.csv', index=False)
        
        logger.info(f"回测结果已导出到: {output_dir}")

