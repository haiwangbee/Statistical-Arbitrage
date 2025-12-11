"""
Dry Run 交易引擎
用于在真实市场数据上模拟交易，不实际下单
支持长期运行和状态持久化
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
import json
import os
import pickle
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Position:
    """持仓信息"""
    
    def __init__(self, symbol: str, quantity: float = 0, avg_price: float = 0):
        self.symbol = symbol
        self.quantity = quantity  # 正数为多头，负数为空头
        self.avg_price = avg_price
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        
    def update_unrealized_pnl(self, current_price: float):
        """更新未实现盈亏"""
        if self.quantity != 0:
            self.unrealized_pnl = self.quantity * (current_price - self.avg_price)
        else:
            self.unrealized_pnl = 0
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        pos = cls(data['symbol'], data['quantity'], data['avg_price'])
        pos.realized_pnl = data.get('realized_pnl', 0)
        pos.unrealized_pnl = data.get('unrealized_pnl', 0)
        return pos


class Trade:
    """交易记录"""
    
    def __init__(self, 
                 timestamp: datetime,
                 symbol: str,
                 side: str,  # 'BUY' or 'SELL'
                 quantity: float,
                 price: float,
                 pair: Tuple[str, str],
                 signal_type: str):  # 'OPEN' or 'CLOSE'
        self.timestamp = timestamp
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.value = quantity * price
        self.pair = pair
        self.signal_type = signal_type
        self.commission = self.value * 0.001  # 0.1% 手续费
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'value': self.value,
            'pair': list(self.pair),
            'signal_type': self.signal_type,
            'commission': self.commission
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Trade':
        trade = cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            symbol=data['symbol'],
            side=data['side'],
            quantity=data['quantity'],
            price=data['price'],
            pair=tuple(data['pair']),
            signal_type=data['signal_type']
        )
        trade.commission = data.get('commission', 0)
        return trade


class PairState:
    """交易对状态"""
    
    def __init__(self, pair: Tuple[str, str], gamma: float, threshold: float):
        self.pair = pair
        self.gamma = gamma
        self.threshold = threshold
        self.current_position = 0  # 0: 空仓, 1: 多symbol2空symbol1, -1: 空symbol2多symbol1
        self.z_value = 0.0
        self.last_signal_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            'pair': list(self.pair),
            'gamma': self.gamma,
            'threshold': self.threshold,
            'current_position': self.current_position,
            'z_value': self.z_value,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PairState':
        state = cls(
            pair=tuple(data['pair']),
            gamma=data['gamma'],
            threshold=data['threshold']
        )
        state.current_position = data['current_position']
        state.z_value = data.get('z_value', 0)
        state.last_signal_time = datetime.fromisoformat(data['last_signal_time']) if data.get('last_signal_time') else None
        return state


class DryRunEngine:
    """
    Dry Run 交易引擎
    模拟真实交易环境，但不实际下单
    """
    
    def __init__(self,
                 initial_capital: float = 100000.0,
                 max_position_pct: float = 0.1,
                 commission_rate: float = 0.001,
                 slippage_rate: float = 0.0005,
                 state_file: Optional[str] = None):
        """
        初始化 Dry Run 引擎
        
        Parameters:
        -----------
        initial_capital : float
            初始资金
        max_position_pct : float
            单个交易对最大持仓占比
        commission_rate : float
            手续费率
        slippage_rate : float
            滑点率
        state_file : str, optional
            状态持久化文件路径
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_position_pct = max_position_pct
        self.max_position_size = initial_capital * max_position_pct
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.state_file = state_file
        
        # 持仓管理
        self.positions: Dict[str, Position] = {}
        
        # 交易对状态
        self.pair_states: Dict[Tuple[str, str], PairState] = {}
        
        # 交易记录
        self.trades: List[Trade] = []
        
        # 性能跟踪
        self.portfolio_history: List[Dict] = []
        self.daily_pnl: List[Dict] = []
        
        # 运行统计
        self.start_time: Optional[datetime] = None
        self.total_trades = 0
        self.winning_trades = 0
        self.total_commission = 0.0
        
        # 协整参数缓存
        self._cointegration_params: Dict[Tuple[str, str], Dict] = {}
        
        logger.info(f"DryRun 引擎初始化完成 - 初始资金: ${initial_capital:,.2f}")
        
        # 尝试恢复状态
        if state_file and os.path.exists(state_file):
            self.load_state()
    
    def initialize_pairs(self, 
                         pairs_config: Dict[Tuple[str, str], Dict],
                         cointegration_params: Dict[Tuple[str, str], Dict]):
        """
        初始化交易对
        
        Parameters:
        -----------
        pairs_config : Dict
            交易对配置 {pair: {'gamma': float, 'threshold': float}}
        cointegration_params : Dict
            协整参数 {pair: {'constant': float, 'gamma': float, 'std': float}}
        """
        for pair, config in pairs_config.items():
            self.pair_states[pair] = PairState(
                pair=pair,
                gamma=config['gamma'],
                threshold=config['threshold']
            )
            
            # 初始化两个交易对的持仓
            symbol1, symbol2 = pair
            if symbol1 not in self.positions:
                self.positions[symbol1] = Position(symbol1)
            if symbol2 not in self.positions:
                self.positions[symbol2] = Position(symbol2)
        
        self._cointegration_params = cointegration_params
        
        logger.info(f"初始化了 {len(pairs_config)} 个交易对")
        
        if self.start_time is None:
            self.start_time = datetime.now()
    
    def calculate_z_value(self, 
                          pair: Tuple[str, str],
                          price1: float,
                          price2: float) -> float:
        """
        计算 Z 值（误差修正项）
        
        z = log(price1) - constant - gamma * log(price2)
        """
        params = self._cointegration_params.get(pair, {})
        constant = params.get('constant', 0)
        gamma = self.pair_states[pair].gamma
        
        z = np.log(price1) - constant - gamma * np.log(price2)
        return z
    
    def generate_signals(self, 
                         market_data: pd.DataFrame,
                         timestamp: datetime) -> List[Dict]:
        """
        生成交易信号
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            市场数据
        timestamp : datetime
            当前时间戳
            
        Returns:
        --------
        List[Dict]
            交易信号列表
        """
        signals = []
        
        try:
            current_data = market_data.loc[timestamp]
        except KeyError:
            # 如果时间戳不存在，使用最新数据
            current_data = market_data.iloc[-1]
        
        for pair, state in self.pair_states.items():
            symbol1, symbol2 = pair
            
            try:
                bid_price_1 = current_data[symbol1, 'BidPrice']
                ask_price_1 = current_data[symbol1, 'AskPrice']
                mid_price_1 = current_data[symbol1, 'MidPrice']
                bid_price_2 = current_data[symbol2, 'BidPrice']
                ask_price_2 = current_data[symbol2, 'AskPrice']
                mid_price_2 = current_data[symbol2, 'MidPrice']
                
                # 计算 Z 值
                z = self.calculate_z_value(pair, mid_price_1, mid_price_2)
                state.z_value = z
                
                threshold = state.threshold
                current_pos = state.current_position
                
                # 平仓信号
                if ((z <= 0) and (current_pos == 1)) or ((z >= 0) and (current_pos == -1)):
                    signals.append({
                        'pair': pair,
                        'action': 'CLOSE',
                        'z_value': z,
                        'prices': {
                            symbol1: {'bid': bid_price_1, 'ask': ask_price_1, 'mid': mid_price_1},
                            symbol2: {'bid': bid_price_2, 'ask': ask_price_2, 'mid': mid_price_2}
                        }
                    })
                
                # 开仓信号：多 symbol2，空 symbol1
                elif (z >= threshold) and (current_pos == 0):
                    signals.append({
                        'pair': pair,
                        'action': 'OPEN',
                        'direction': 1,  # 多 symbol2，空 symbol1
                        'z_value': z,
                        'prices': {
                            symbol1: {'bid': bid_price_1, 'ask': ask_price_1, 'mid': mid_price_1},
                            symbol2: {'bid': bid_price_2, 'ask': ask_price_2, 'mid': mid_price_2}
                        }
                    })
                
                # 开仓信号：空 symbol2，多 symbol1
                elif (z <= -threshold) and (current_pos == 0):
                    signals.append({
                        'pair': pair,
                        'action': 'OPEN',
                        'direction': -1,  # 空 symbol2，多 symbol1
                        'z_value': z,
                        'prices': {
                            symbol1: {'bid': bid_price_1, 'ask': ask_price_1, 'mid': mid_price_1},
                            symbol2: {'bid': bid_price_2, 'ask': ask_price_2, 'mid': mid_price_2}
                        }
                    })
                    
            except Exception as e:
                logger.warning(f"处理交易对 {pair} 时出错: {e}")
                continue
        
        return signals
    
    def execute_signal(self, signal: Dict, timestamp: datetime) -> List[Trade]:
        """
        执行交易信号（模拟）
        
        Parameters:
        -----------
        signal : Dict
            交易信号
        timestamp : datetime
            执行时间
            
        Returns:
        --------
        List[Trade]
            执行的交易列表
        """
        executed_trades = []
        pair = signal['pair']
        symbol1, symbol2 = pair
        state = self.pair_states[pair]
        prices = signal['prices']
        
        if signal['action'] == 'CLOSE':
            # 平仓
            pos1 = self.positions[symbol1]
            pos2 = self.positions[symbol2]
            
            if pos1.quantity != 0:
                # 平掉 symbol1 的仓位
                if pos1.quantity > 0:
                    # 持有多头，卖出平仓
                    price = prices[symbol1]['bid'] * (1 - self.slippage_rate)
                    pnl = pos1.quantity * (price - pos1.avg_price)
                else:
                    # 持有空头，买入平仓
                    price = prices[symbol1]['ask'] * (1 + self.slippage_rate)
                    pnl = pos1.quantity * (price - pos1.avg_price)  # quantity 是负数
                
                trade = Trade(
                    timestamp=timestamp,
                    symbol=symbol1,
                    side='SELL' if pos1.quantity > 0 else 'BUY',
                    quantity=abs(pos1.quantity),
                    price=price,
                    pair=pair,
                    signal_type='CLOSE'
                )
                executed_trades.append(trade)
                
                pos1.realized_pnl += pnl - trade.commission
                self.capital += pnl - trade.commission
                self.total_commission += trade.commission
                pos1.quantity = 0
                pos1.avg_price = 0
            
            if pos2.quantity != 0:
                # 平掉 symbol2 的仓位
                if pos2.quantity > 0:
                    price = prices[symbol2]['bid'] * (1 - self.slippage_rate)
                    pnl = pos2.quantity * (price - pos2.avg_price)
                else:
                    price = prices[symbol2]['ask'] * (1 + self.slippage_rate)
                    pnl = pos2.quantity * (price - pos2.avg_price)
                
                trade = Trade(
                    timestamp=timestamp,
                    symbol=symbol2,
                    side='SELL' if pos2.quantity > 0 else 'BUY',
                    quantity=abs(pos2.quantity),
                    price=price,
                    pair=pair,
                    signal_type='CLOSE'
                )
                executed_trades.append(trade)
                
                pos2.realized_pnl += pnl - trade.commission
                self.capital += pnl - trade.commission
                self.total_commission += trade.commission
                pos2.quantity = 0
                pos2.avg_price = 0
            
            state.current_position = 0
            
            # 统计
            if sum(t.value for t in executed_trades) > 0:
                self.winning_trades += 1
            
        elif signal['action'] == 'OPEN':
            direction = signal['direction']
            gamma = state.gamma
            
            if direction == 1:
                # 多 symbol2，空 symbol1
                # 卖出 symbol1（做空）
                price1 = prices[symbol1]['bid'] * (1 - self.slippage_rate)
                # 买入 symbol2（做多）
                price2 = prices[symbol2]['ask'] * (1 + self.slippage_rate)
                
                hedge_ratio = gamma * (price1 / price2)
                max_order_1 = np.floor(self.max_position_size / price1)
                max_order_2 = np.floor(self.max_position_size / price2)
                
                order_size_2 = min(max_order_1 * hedge_ratio, max_order_2)
                order_size_1 = np.floor(order_size_2 / hedge_ratio)
                
                if order_size_1 > 0 and order_size_2 > 0:
                    # 做空 symbol1
                    trade1 = Trade(
                        timestamp=timestamp,
                        symbol=symbol1,
                        side='SELL',
                        quantity=order_size_1,
                        price=price1,
                        pair=pair,
                        signal_type='OPEN'
                    )
                    executed_trades.append(trade1)
                    
                    pos1 = self.positions[symbol1]
                    pos1.quantity = -order_size_1
                    pos1.avg_price = price1
                    self.total_commission += trade1.commission
                    
                    # 做多 symbol2
                    trade2 = Trade(
                        timestamp=timestamp,
                        symbol=symbol2,
                        side='BUY',
                        quantity=order_size_2,
                        price=price2,
                        pair=pair,
                        signal_type='OPEN'
                    )
                    executed_trades.append(trade2)
                    
                    pos2 = self.positions[symbol2]
                    pos2.quantity = order_size_2
                    pos2.avg_price = price2
                    self.total_commission += trade2.commission
                    
                    state.current_position = 1
                    
            elif direction == -1:
                # 空 symbol2，多 symbol1
                # 买入 symbol1（做多）
                price1 = prices[symbol1]['ask'] * (1 + self.slippage_rate)
                # 卖出 symbol2（做空）
                price2 = prices[symbol2]['bid'] * (1 - self.slippage_rate)
                
                hedge_ratio = gamma * (price1 / price2)
                max_order_1 = np.floor(self.max_position_size / price1)
                max_order_2 = np.floor(self.max_position_size / price2)
                
                order_size_2 = min(max_order_1 * hedge_ratio, max_order_2)
                order_size_1 = np.floor(order_size_2 / hedge_ratio)
                
                if order_size_1 > 0 and order_size_2 > 0:
                    # 做多 symbol1
                    trade1 = Trade(
                        timestamp=timestamp,
                        symbol=symbol1,
                        side='BUY',
                        quantity=order_size_1,
                        price=price1,
                        pair=pair,
                        signal_type='OPEN'
                    )
                    executed_trades.append(trade1)
                    
                    pos1 = self.positions[symbol1]
                    pos1.quantity = order_size_1
                    pos1.avg_price = price1
                    self.total_commission += trade1.commission
                    
                    # 做空 symbol2
                    trade2 = Trade(
                        timestamp=timestamp,
                        symbol=symbol2,
                        side='SELL',
                        quantity=order_size_2,
                        price=price2,
                        pair=pair,
                        signal_type='OPEN'
                    )
                    executed_trades.append(trade2)
                    
                    pos2 = self.positions[symbol2]
                    pos2.quantity = -order_size_2
                    pos2.avg_price = price2
                    self.total_commission += trade2.commission
                    
                    state.current_position = -1
        
        # 记录交易
        self.trades.extend(executed_trades)
        self.total_trades += len(executed_trades)
        
        # 更新状态
        if executed_trades:
            state.last_signal_time = timestamp
            self.save_state()
        
        return executed_trades
    
    def update_portfolio(self, market_data: pd.DataFrame, timestamp: datetime):
        """
        更新组合价值
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            市场数据
        timestamp : datetime
            当前时间
        """
        try:
            current_data = market_data.loc[timestamp]
        except KeyError:
            current_data = market_data.iloc[-1]
        
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0
        
        for symbol, pos in self.positions.items():
            if pos.quantity != 0:
                try:
                    current_price = current_data[symbol, 'MidPrice']
                    pos.update_unrealized_pnl(current_price)
                    total_unrealized_pnl += pos.unrealized_pnl
                except:
                    pass
            total_realized_pnl += pos.realized_pnl
        
        portfolio_value = self.initial_capital + total_realized_pnl + total_unrealized_pnl
        
        # 确保 timestamp 是字符串格式
        if isinstance(timestamp, (pd.Timestamp, datetime)):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)
        
        self.portfolio_history.append({
            'timestamp': timestamp_str,
            'portfolio_value': float(portfolio_value),
            'realized_pnl': float(total_realized_pnl),
            'unrealized_pnl': float(total_unrealized_pnl),
            'capital': float(self.capital),
            'total_commission': float(self.total_commission)
        })
    
    def process_tick(self, 
                     market_data: pd.DataFrame, 
                     timestamp: datetime) -> List[Trade]:
        """
        处理一个时间点的数据
        
        Parameters:
        -----------
        market_data : pd.DataFrame
            市场数据
        timestamp : datetime
            当前时间
            
        Returns:
        --------
        List[Trade]
            执行的交易列表
        """
        all_trades = []
        
        # 生成信号
        signals = self.generate_signals(market_data, timestamp)
        
        # 执行信号
        for signal in signals:
            trades = self.execute_signal(signal, timestamp)
            all_trades.extend(trades)
            
            if trades:
                pair = signal['pair']
                action = signal['action']
                z = signal['z_value']
                logger.info(f"[{timestamp}] {pair[0]}-{pair[1]} {action} | Z={z:.4f} | "
                           f"执行 {len(trades)} 笔交易")
        
        # 更新组合价值
        self.update_portfolio(market_data, timestamp)
        
        return all_trades
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        if not self.portfolio_history:
            current_value = self.initial_capital
        else:
            current_value = self.portfolio_history[-1]['portfolio_value']
        
        total_return = current_value - self.initial_capital
        return_pct = (total_return / self.initial_capital) * 100
        
        # 计算最大回撤
        if len(self.portfolio_history) > 0:
            values = pd.Series([h['portfolio_value'] for h in self.portfolio_history])
            running_max = values.expanding().max()
            drawdown = values - running_max
            max_drawdown = drawdown.min()
            max_drawdown_pct = (max_drawdown / self.initial_capital) * 100
        else:
            max_drawdown = 0
            max_drawdown_pct = 0
        
        # 活跃持仓
        active_positions = {
            symbol: pos.to_dict() 
            for symbol, pos in self.positions.items() 
            if pos.quantity != 0
        }
        
        # 交易对状态
        pair_status = {}
        for pair, state in self.pair_states.items():
            pair_status[f"{pair[0]}-{pair[1]}"] = {
                'position': state.current_position,
                'z_value': round(state.z_value, 4),
                'threshold': round(state.threshold, 4)
            }
        
        return {
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'current_time': datetime.now().isoformat(),
            'initial_capital': self.initial_capital,
            'current_value': round(current_value, 2),
            'total_return': round(total_return, 2),
            'return_pct': round(return_pct, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': round(self.winning_trades / max(1, self.total_trades // 2) * 100, 2),
            'total_commission': round(self.total_commission, 2),
            'active_positions': active_positions,
            'pair_status': pair_status
        }
    
    def print_status(self):
        """打印当前状态"""
        status = self.get_status()
        
        print("\n" + "=" * 60)
        print("DRY RUN 状态报告")
        print("=" * 60)
        print(f"运行时间:     {status['start_time']} 至 {status['current_time']}")
        print(f"初始资金:     ${status['initial_capital']:,.2f}")
        print(f"当前净值:     ${status['current_value']:,.2f}")
        print(f"总收益:       ${status['total_return']:,.2f} ({status['return_pct']:.2f}%)")
        print(f"最大回撤:     ${status['max_drawdown']:,.2f} ({status['max_drawdown_pct']:.2f}%)")
        print(f"交易次数:     {status['total_trades']}")
        print(f"胜率:         {status['win_rate']:.2f}%")
        print(f"总手续费:     ${status['total_commission']:,.2f}")
        
        print("\n" + "-" * 60)
        print("交易对状态:")
        for pair_name, pair_info in status['pair_status'].items():
            pos_str = '空仓' if pair_info['position'] == 0 else (
                '多2空1' if pair_info['position'] == 1 else '空2多1'
            )
            print(f"  {pair_name}: {pos_str} | Z={pair_info['z_value']:.4f} | 阈值=±{pair_info['threshold']:.4f}")
        
        if status['active_positions']:
            print("\n" + "-" * 60)
            print("活跃持仓:")
            for symbol, pos_info in status['active_positions'].items():
                print(f"  {symbol}: {pos_info['quantity']:.4f} @ ${pos_info['avg_price']:.2f} | "
                      f"未实现盈亏: ${pos_info['unrealized_pnl']:.2f}")
        
        print("=" * 60 + "\n")
    
    def _serialize_value(self, obj):
        """将对象转换为 JSON 可序列化的格式"""
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._serialize_value(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_value(v) for v in obj]
        else:
            return obj
    
    def save_state(self):
        """保存状态到文件"""
        if not self.state_file:
            return
        
        # 序列化 portfolio_history 中的时间戳
        serialized_history = []
        for record in self.portfolio_history[-10000:]:
            serialized_record = self._serialize_value(record)
            serialized_history.append(serialized_record)
        
        state = {
            'version': '1.0',
            'saved_at': datetime.now().isoformat(),
            'initial_capital': self.initial_capital,
            'capital': float(self.capital),
            'max_position_pct': float(self.max_position_pct),
            'commission_rate': float(self.commission_rate),
            'slippage_rate': float(self.slippage_rate),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'total_trades': int(self.total_trades),
            'winning_trades': int(self.winning_trades),
            'total_commission': float(self.total_commission),
            'positions': {k: self._serialize_value(v.to_dict()) for k, v in self.positions.items()},
            'pair_states': {f"{k[0]}_{k[1]}": self._serialize_value(v.to_dict()) for k, v in self.pair_states.items()},
            'cointegration_params': {f"{k[0]}_{k[1]}": self._serialize_value(v) for k, v in self._cointegration_params.items()},
            'trades': [self._serialize_value(t.to_dict()) for t in self.trades[-1000:]],  # 只保留最近 1000 笔
            'portfolio_history': serialized_history
        }
        
        # 确保目录存在
        Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
        
        # 写入临时文件，然后重命名（原子操作）
        temp_file = self.state_file + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(temp_file, self.state_file)
        
        logger.debug(f"状态已保存到: {self.state_file}")
    
    def load_state(self):
        """从文件恢复状态"""
        if not self.state_file or not os.path.exists(self.state_file):
            return False
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.capital = state['capital']
            self.start_time = datetime.fromisoformat(state['start_time']) if state.get('start_time') else None
            self.total_trades = state.get('total_trades', 0)
            self.winning_trades = state.get('winning_trades', 0)
            self.total_commission = state.get('total_commission', 0)
            
            # 恢复持仓
            self.positions = {
                k: Position.from_dict(v) 
                for k, v in state.get('positions', {}).items()
            }
            
            # 恢复交易对状态
            self.pair_states = {}
            for k, v in state.get('pair_states', {}).items():
                pair = tuple(k.split('_'))
                self.pair_states[pair] = PairState.from_dict(v)
            
            # 恢复协整参数
            self._cointegration_params = {}
            for k, v in state.get('cointegration_params', {}).items():
                pair = tuple(k.split('_'))
                self._cointegration_params[pair] = v
            
            # 恢复交易记录
            self.trades = [Trade.from_dict(t) for t in state.get('trades', [])]
            
            # 恢复组合历史
            self.portfolio_history = state.get('portfolio_history', [])
            
            logger.info(f"状态已从 {self.state_file} 恢复 | "
                       f"资金: ${self.capital:,.2f} | 交易次数: {self.total_trades}")
            
            return True
            
        except Exception as e:
            logger.error(f"恢复状态失败: {e}")
            return False
    
    def export_results(self, output_dir: str):
        """导出结果"""
        os.makedirs(output_dir, exist_ok=True)
        
        # 导出交易记录
        if self.trades:
            trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
            trades_df.to_csv(f'{output_dir}/trades.csv', index=False)
        
        # 导出组合历史
        if self.portfolio_history:
            portfolio_df = pd.DataFrame(self.portfolio_history)
            portfolio_df.to_csv(f'{output_dir}/portfolio_history.csv', index=False)
        
        # 导出状态
        status = self.get_status()
        with open(f'{output_dir}/status.json', 'w') as f:
            json.dump(status, f, indent=2)
        
        logger.info(f"结果已导出到: {output_dir}")


if __name__ == "__main__":
    # 测试代码
    engine = DryRunEngine(
        initial_capital=100000.0,
        max_position_pct=0.1,
        state_file='./data/dryrun_state.json'
    )
    
    print("DryRun 引擎测试完成")

