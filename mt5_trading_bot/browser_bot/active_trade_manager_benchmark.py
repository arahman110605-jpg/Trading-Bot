"""
================================================================================
ACTIVE TRADE MANAGEMENT ENGINE & BACKTEST BENCHMARK
================================================================================
Comprehensive Multi-Timeframe (H1, M15, M5) Thesis-Based Trade Manager
vs. Fixed Baseline Basket TP/SL

Metrics tracked:
- Avg Profit per Trade ($ and R)
- Expectancy ($ and R)
- Profit Factor
- Max Drawdown ($ and %)
- Avg Maximum Favorable Excursion (MFE)
- Avg Maximum Adverse Excursion (MAE)
- Profit Giveback (MFE - Realized PnL)
- Trailing Stop-Out Rate (%)
- Structural Invalidation Exit Rate (%)
- Average Holding Time (Minutes/Bars)
- Tail Risk (95th & 99th Percentile Drawdown/Losses)
================================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import ta
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple

class TradeState(Enum):
    INITIAL = "INITIAL"
    PROFIT_PROTECTION = "PROFIT_PROTECTION"
    TREND_RUN = "TREND_RUN"
    MOMENTUM_WEAKENING = "MOMENTUM_WEAKENING"
    EXIT_PENDING = "EXIT_PENDING"
    INVALIDATED = "INVALIDATED"
    CLOSED = "CLOSED"

@dataclass
class PositionRecord:
    ticket: int
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry_time: pd.Timestamp
    entry_price: float
    volume: float
    initial_atr: float
    initial_r_pips: float # Initial Risk Unit in pips
    initial_stop_price: float
    current_stop_price: float
    
    # State tracking
    state: TradeState = TradeState.INITIAL
    thesis_score: float = 100.0
    warning_bars: int = 0
    weakening_bars: int = 0
    
    # Excursion Tracking
    mfe_pips: float = 0.0
    mae_pips: float = 0.0
    
    # Exit Info
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    realized_pnl_usd: float = 0.0
    realized_r: float = 0.0
    bars_held: int = 0

def fetch_mt5_data(symbol: str, count: int = 15000) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch M5, M15, and H1 data synchronized from MT5"""
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, count // 3 + 500)
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, count // 12 + 500)
    
    if rates_m5 is None or rates_m15 is None or rates_h1 is None:
        raise ValueError(f"Failed to fetch historical rates for {symbol}")
        
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
    df_m5.set_index('time', inplace=True)
    
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
    df_m15.set_index('time', inplace=True)
    
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
    df_h1.set_index('time', inplace=True)
    
    return df_m5, df_m15, df_h1

def compute_indicators(df_m5: pd.DataFrame, df_m15: pd.DataFrame, df_h1: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # ── H1 INDICATORS ──
    df_h1['ema50'] = ta.trend.EMAIndicator(df_h1['close'], window=50).ema_indicator()
    df_h1['ema200'] = ta.trend.EMAIndicator(df_h1['close'], window=200).ema_indicator()
    df_h1['ema50_slope'] = df_h1['ema50'].diff(3) / 3.0
    
    # ── M15 STRUCTURE (Swing High / Swing Low detection) ──
    df_m15['ema20'] = ta.trend.EMAIndicator(df_m15['close'], window=20).ema_indicator()
    df_m15['ema50'] = ta.trend.EMAIndicator(df_m15['close'], window=50).ema_indicator()
    df_m15['swing_high'] = df_m15['high'].rolling(window=5, center=True).apply(lambda x: 1 if x[2] == max(x) else 0, raw=True)
    df_m15['swing_low'] = df_m15['low'].rolling(window=5, center=True).apply(lambda x: 1 if x[2] == min(x) else 0, raw=True)
    
    # ── M5 INTRADAY INDICATORS ──
    df_m5['ema20'] = ta.trend.EMAIndicator(df_m5['close'], window=20).ema_indicator()
    df_m5['ema50'] = ta.trend.EMAIndicator(df_m5['close'], window=50).ema_indicator()
    df_m5['ema200'] = ta.trend.EMAIndicator(df_m5['close'], window=200).ema_indicator()
    df_m5['ema20_slope'] = df_m5['ema20'].diff(2) / 2.0
    df_m5['atr14'] = ta.volatility.AverageTrueRange(df_m5['high'], df_m5['low'], df_m5['close'], window=14).average_true_range()
    df_m5['rsi14'] = ta.momentum.RSIIndicator(df_m5['close'], window=14).rsi()
    df_m5['volume_sma20'] = df_m5['tick_volume'].rolling(20).mean()
    df_m5['vol_ratio'] = df_m5['tick_volume'] / df_m5['volume_sma20'].replace(0, 1)
    
    # Swing points on M5 for precise structural trailing stops
    df_m5['swing_low_val'] = df_m5['low'].rolling(window=5).min()
    df_m5['swing_high_val'] = df_m5['high'].rolling(window=5).max()
    
    return df_m5, df_m15, df_h1

class ActiveTradeManager:
    """
    Stateful Active Trade Management Engine
    Tracks Thesis Score, State Machine Transitions, and Volatility-Adaptive Trailing
    """
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size

    def calculate_thesis_score(self, pos: PositionRecord, row_m5: pd.Series, prev_m5: pd.Series, row_m15: pd.Series, row_h1: pd.Series) -> float:
        """
        Compute dynamic Thesis Score (0 to 100) combining MTF factors:
        1. H1 Regime (25 pts)
        2. H1 EMA Slope (15 pts)
        3. M15 Structure (20 pts)
        4. M5 EMA20 Alignment & Slope (20 pts)
        5. M5 Momentum RSI (10 pts)
        6. Volatility & Volume Confirmation (10 pts)
        """
        score = 0.0
        
        if pos.direction == "BUY":
            # 1. H1 Macro Regime (25 pts)
            if row_h1['close'] > row_h1['ema200']:
                score += 15.0
            if row_h1['close'] > row_h1['ema50']:
                score += 10.0
            elif row_h1['close'] < row_h1['ema200']:
                score -= 10.0
                
            # 2. H1 Slope (15 pts)
            if row_h1['ema50_slope'] > 0:
                score += 15.0
            else:
                score += 0.0
                
            # 3. M15 Structure (20 pts)
            if row_m15['close'] > row_m15['ema20'] and row_m15['close'] > row_m15['ema50']:
                score += 20.0
            elif row_m15['close'] > row_m15['ema20']:
                score += 10.0
            elif row_m15['close'] < row_m15['ema50']:
                score -= 10.0
                
            # 4. M5 EMA20 state & slope (20 pts)
            if row_m5['close'] > row_m5['ema20']:
                score += 10.0
            if row_m5['ema20_slope'] > 0:
                score += 10.0
            elif row_m5['ema20_slope'] < 0:
                score -= 5.0
                
            # 5. M5 Momentum RSI (10 pts)
            if 45 <= row_m5['rsi14'] <= 70:
                score += 10.0
            elif row_m5['rsi14'] < 40:
                score += 0.0
            elif row_m5['rsi14'] > 75: # Overextended momentum
                score += 5.0
                
            # 6. Volume confirmation (10 pts)
            if row_m5['vol_ratio'] >= 1.0:
                score += 10.0
            else:
                score += 5.0

        else: # SELL
            # 1. H1 Macro Regime (25 pts)
            if row_h1['close'] < row_h1['ema200']:
                score += 15.0
            if row_h1['close'] < row_h1['ema50']:
                score += 10.0
            elif row_h1['close'] > row_h1['ema200']:
                score -= 10.0
                
            # 2. H1 Slope (15 pts)
            if row_h1['ema50_slope'] < 0:
                score += 15.0
                
            # 3. M15 Structure (20 pts)
            if row_m15['close'] < row_m15['ema20'] and row_m15['close'] < row_m15['ema50']:
                score += 20.0
            elif row_m15['close'] < row_m15['ema20']:
                score += 10.0
            elif row_m15['close'] > row_m15['ema50']:
                score -= 10.0
                
            # 4. M5 EMA20 state & slope (20 pts)
            if row_m5['close'] < row_m5['ema20']:
                score += 10.0
            if row_m5['ema20_slope'] < 0:
                score += 10.0
            elif row_m5['ema20_slope'] > 0:
                score -= 5.0
                
            # 5. M5 Momentum RSI (10 pts)
            if 30 <= row_m5['rsi14'] <= 55:
                score += 10.0
            elif row_m5['rsi14'] > 60:
                score += 0.0
            elif row_m5['rsi14'] < 25:
                score += 5.0
                
            # 6. Volume confirmation (10 pts)
            if row_m5['vol_ratio'] >= 1.0:
                score += 10.0
            else:
                score += 5.0
                
        return max(0.0, min(100.0, score))

    def update_position(self, pos: PositionRecord, row_m5: pd.Series, prev_m5: pd.Series, row_m15: pd.Series, row_h1: pd.Series) -> Tuple[bool, str]:
        """
        Evaluate candle close against state machine & structural rules.
        Returns: (should_close, exit_reason)
        """
        pos.bars_held += 1
        curr_price = row_m5['close']
        atr = row_m5['atr14']
        atr_pips = atr / self.pip_size
        
        # 1. Update Excursions (MFE & MAE)
        if pos.direction == "BUY":
            fav_pips = (row_m5['high'] - pos.entry_price) / self.pip_size
            adv_pips = (pos.entry_price - row_m5['low']) / self.pip_size
            current_r = (curr_price - pos.entry_price) / (pos.initial_r_pips * self.pip_size)
        else:
            fav_pips = (pos.entry_price - row_m5['low']) / self.pip_size
            adv_pips = (row_m5['high'] - pos.entry_price) / self.pip_size
            current_r = (pos.entry_price - curr_price) / (pos.initial_r_pips * self.pip_size)
            
        pos.mfe_pips = max(pos.mfe_pips, fav_pips)
        pos.mae_pips = max(pos.mae_pips, adv_pips)
        
        # 2. Check Intrabar Trailing Stop-Out (Emergency / Tick simulation with Bar Extremes)
        if pos.direction == "BUY":
            if row_m5['low'] <= pos.current_stop_price:
                return True, "TRAILING_STOP_HIT"
        else:
            if row_m5['high'] >= pos.current_stop_price:
                return True, "TRAILING_STOP_HIT"
                
        # 3. Calculate Thesis Score
        thesis_score = self.calculate_thesis_score(pos, row_m5, prev_m5, row_m15, row_h1)
        pos.thesis_score = thesis_score
        
        # 4. State Machine Transitions
        # INITIAL -> PROFIT_PROTECTION (at >= +1.2 R)
        if pos.state == TradeState.INITIAL:
            if current_r >= 1.2:
                pos.state = TradeState.PROFIT_PROTECTION
                # Move stop to Breakeven + 0.2 R (normalized buffer)
                if pos.direction == "BUY":
                    new_stop = pos.entry_price + (0.2 * pos.initial_r_pips * self.pip_size)
                    pos.current_stop_price = max(pos.current_stop_price, new_stop)
                else:
                    new_stop = pos.entry_price - (0.2 * pos.initial_r_pips * self.pip_size)
                    pos.current_stop_price = min(pos.current_stop_price, new_stop)

        # PROFIT_PROTECTION -> TREND_RUN (at >= +2.0 R and healthy Thesis Score >= 70)
        if pos.state in [TradeState.INITIAL, TradeState.PROFIT_PROTECTION]:
            if current_r >= 2.0 and thesis_score >= 70:
                pos.state = TradeState.TREND_RUN

        # Active Trailing in TREND_RUN (Structure & Volatility Aware)
        if pos.state == TradeState.TREND_RUN:
            if pos.direction == "BUY":
                # Trail below recent M5 swing low - 0.5 ATR
                swing_stop = row_m5['swing_low_val'] - (0.5 * atr)
                # Ensure stop only moves upward
                pos.current_stop_price = max(pos.current_stop_price, swing_stop)
            else:
                swing_stop = row_m5['swing_high_val'] + (0.5 * atr)
                # Ensure stop only moves downward
                pos.current_stop_price = min(pos.current_stop_price, swing_stop)

        # 5. Thesis Deterioration & Structural Invalidation Rules
        if pos.direction == "BUY":
            # Warning: Closed below M5 EMA20
            if row_m5['close'] < row_m5['ema20']:
                pos.warning_bars += 1
            else:
                pos.warning_bars = 0
                
            # Invalidation #1: Macro H1 Regime Invalidation
            if row_h1['close'] < row_h1['ema200'] and row_m5['close'] < row_m5['ema50']:
                return True, "MACRO_H1_INVALIDATION"
                
            # Invalidation #2: M15 Structural Breakdown
            if row_m15['close'] < row_m15['ema50'] and pos.warning_bars >= 2:
                return True, "M15_STRUCTURE_BREAK"
                
            # Momentum Weakening & Contextual Exhaustion
            if pos.state in [TradeState.TREND_RUN, TradeState.PROFIT_PROTECTION]:
                if thesis_score < 40 and row_m5['ema20_slope'] < 0 and pos.warning_bars >= 2:
                    pos.state = TradeState.MOMENTUM_WEAKENING
                    # Tighten stop right to previous bar low
                    pos.current_stop_price = max(pos.current_stop_price, prev_m5['low'])
                    
            # Exit Pending on severe thesis breakdown (< 30 pts with negative slope)
            if pos.state == TradeState.MOMENTUM_WEAKENING and thesis_score < 30:
                return True, "THESIS_EXHAUSTION_EXIT"

        else: # SELL
            # Warning: Closed above M5 EMA20
            if row_m5['close'] > row_m5['ema20']:
                pos.warning_bars += 1
            else:
                pos.warning_bars = 0
                
            # Invalidation #1: Macro H1 Regime Invalidation
            if row_h1['close'] > row_h1['ema200'] and row_m5['close'] > row_m5['ema50']:
                return True, "MACRO_H1_INVALIDATION"
                
            # Invalidation #2: M15 Structural Breakdown
            if row_m15['close'] > row_m15['ema50'] and pos.warning_bars >= 2:
                return True, "M15_STRUCTURE_BREAK"
                
            # Momentum Weakening
            if pos.state in [TradeState.TREND_RUN, TradeState.PROFIT_PROTECTION]:
                if thesis_score < 40 and row_m5['ema20_slope'] > 0 and pos.warning_bars >= 2:
                    pos.state = TradeState.MOMENTUM_WEAKENING
                    pos.current_stop_price = min(pos.current_stop_price, prev_m5['high'])
                    
            if pos.state == TradeState.MOMENTUM_WEAKENING and thesis_score < 30:
                return True, "THESIS_EXHAUSTION_EXIT"
                
        return False, ""

def run_simulation(symbol: str, count: int = 15000):
    pip_size = 0.0001 if "JPY" not in symbol else 0.01
    df_m5, df_m15, df_h1 = fetch_mt5_data(symbol, count)
    df_m5, df_m15, df_h1 = compute_indicators(df_m5, df_m15, df_h1)
    
    # Align M15 and H1 by forward-filling to M5 timestamps
    df_m15_re = df_m15.reindex(df_m5.index, method='ffill')
    df_h1_re = df_h1.reindex(df_m5.index, method='ffill')
    
    # ── 1. ACTIVE TRADE MANAGER BACKTEST ──
    manager = ActiveTradeManager(pip_size=pip_size)
    active_positions: List[PositionRecord] = []
    closed_active_trades: List[PositionRecord] = []
    
    # ── 2. BASELINE FIXED BASKET BACKTEST ──
    closed_baseline_trades = []
    baseline_active = []
    
    ticket_counter = 1000
    
    start_idx = 250 # warm-up for 200 EMA
    for i in range(start_idx, len(df_m5)):
        curr_time = df_m5.index[i]
        row_m5 = df_m5.iloc[i]
        prev_m5 = df_m5.iloc[i-1]
        row_m15 = df_m15_re.iloc[i]
        row_h1 = df_h1_re.iloc[i]
        
        # ── A. UPDATE ACTIVE TRADES IN ACTIVE MANAGER ──
        still_open = []
        for pos in active_positions:
            should_close, reason = manager.update_position(pos, row_m5, prev_m5, row_m15, row_h1)
            if should_close:
                pos.exit_time = curr_time
                if reason == "TRAILING_STOP_HIT":
                    pos.exit_price = pos.current_stop_price
                else:
                    pos.exit_price = row_m5['close']
                    
                pos.exit_reason = reason
                if pos.direction == "BUY":
                    pnl_pips = (pos.exit_price - pos.entry_price) / pip_size
                else:
                    pnl_pips = (pos.entry_price - pos.exit_price) / pip_size
                    
                pos.realized_pnl_usd = pnl_pips * (pos.volume * 10.0 if "JPY" not in symbol else pos.volume * 1000.0 / pos.exit_price)
                pos.realized_r = pnl_pips / pos.initial_r_pips
                closed_active_trades.append(pos)
            else:
                still_open.append(pos)
        active_positions = still_open
        
        # ── B. UPDATE BASELINE FIXED TP/SL TRADES ──
        still_base = []
        for b_pos in baseline_active:
            # Check fixed TP (+8.00) or hard stop (-20.00 / 10%)
            if b_pos['dir'] == "BUY":
                cur_pnl = ((row_m5['close'] - b_pos['entry']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
                high_pnl = ((row_m5['high'] - b_pos['entry']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
                low_pnl = ((row_m5['low'] - b_pos['entry']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
            else:
                cur_pnl = ((b_pos['entry'] - row_m5['close']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
                high_pnl = ((b_pos['entry'] - row_m5['low']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
                low_pnl = ((b_pos['entry'] - row_m5['high']) / pip_size) * (b_pos['vol'] * 10.0 if "JPY" not in symbol else b_pos['vol'] * 1000.0 / row_m5['close'])
                
            b_pos['mfe'] = max(b_pos['mfe'], high_pnl)
            b_pos['mae'] = min(b_pos['mae'], low_pnl)
            b_pos['bars'] += 1
            
            if high_pnl >= 8.0:
                b_pos['exit_pnl'] = 8.0
                b_pos['reason'] = "FIXED_TP_HIT"
                closed_baseline_trades.append(b_pos)
            elif low_pnl <= -20.0:
                b_pos['exit_pnl'] = -20.0
                b_pos['reason'] = "HARD_STOP_HIT"
                closed_baseline_trades.append(b_pos)
            else:
                still_base.append(b_pos)
        baseline_active = still_base
        
        # ── C. ENTRY GENERATOR (Same entry signals for both models) ──
        if len(active_positions) == 0: # Only enter if flat on active
            atr = row_m5['atr14']
            r_pips = max(12.0, (atr / pip_size) * 1.5)
            
            # BUY Signal
            if row_m5['close'] > row_m5['ema200'] and row_m5['close'] > row_m5['ema20'] and prev_m5['close'] <= prev_m5['ema20']:
                stop_price = row_m5['close'] - (r_pips * pip_size)
                ticket_counter += 1
                pos = PositionRecord(
                    ticket=ticket_counter,
                    symbol=symbol,
                    direction="BUY",
                    entry_time=curr_time,
                    entry_price=row_m5['close'],
                    volume=0.02,
                    initial_atr=atr,
                    initial_r_pips=r_pips,
                    initial_stop_price=stop_price,
                    current_stop_price=stop_price
                )
                active_positions.append(pos)
                
                # Baseline equivalent
                baseline_active.append({
                    'ticket': ticket_counter,
                    'dir': 'BUY',
                    'entry': row_m5['close'],
                    'vol': 0.02,
                    'mfe': 0.0,
                    'mae': 0.0,
                    'bars': 0
                })
                
            # SELL Signal
            elif row_m5['close'] < row_m5['ema200'] and row_m5['close'] < row_m5['ema20'] and prev_m5['close'] >= prev_m5['ema20']:
                stop_price = row_m5['close'] + (r_pips * pip_size)
                ticket_counter += 1
                pos = PositionRecord(
                    ticket=ticket_counter,
                    symbol=symbol,
                    direction="SELL",
                    entry_time=curr_time,
                    entry_price=row_m5['close'],
                    volume=0.02,
                    initial_atr=atr,
                    initial_r_pips=r_pips,
                    initial_stop_price=stop_price,
                    current_stop_price=stop_price
                )
                active_positions.append(pos)
                
                baseline_active.append({
                    'ticket': ticket_counter,
                    'dir': 'SELL',
                    'entry': row_m5['close'],
                    'vol': 0.02,
                    'mfe': 0.0,
                    'mae': 0.0,
                    'bars': 0
                })
                
    return closed_active_trades, closed_baseline_trades

def analyze_and_compare(active_trades: List[PositionRecord], base_trades: List[Dict], symbol: str):
    print("=" * 80)
    print(f"  ACTIVE TRADE MANAGER VS. FIXED BASELINE COMPARISON: {symbol}")
    print("=" * 80)
    
    # ── 1. ACTIVE MANAGER METRICS ──
    act_df = pd.DataFrame([{
        'pnl_usd': t.realized_pnl_usd,
        'r_mult': t.realized_r,
        'mfe_pips': t.mfe_pips,
        'mae_pips': t.mae_pips,
        'bars_held': t.bars_held,
        'reason': t.exit_reason
    } for t in active_trades])
    
    base_df = pd.DataFrame(base_trades)
    
    if len(act_df) == 0 or len(base_df) == 0:
        print("Insufficient trades for analysis.")
        return

    # Active metrics
    act_wins = act_df[act_df['pnl_usd'] > 0]
    act_losses = act_df[act_df['pnl_usd'] <= 0]
    act_tot_pnl = act_df['pnl_usd'].sum()
    act_pf = abs(act_wins['pnl_usd'].sum() / act_losses['pnl_usd'].sum()) if len(act_losses) > 0 and act_losses['pnl_usd'].sum() != 0 else np.nan
    act_win_rate = (len(act_wins) / len(act_df)) * 100.0
    act_expectancy = act_df['pnl_usd'].mean()
    act_avg_r = act_df['r_mult'].mean()
    act_giveback = (act_df['mfe_pips'] - (act_df['pnl_usd'] / 0.20)).mean()
    
    # Invalidation & Trailing Distribution
    trail_exits = (act_df['reason'] == "TRAILING_STOP_HIT").sum() / len(act_df) * 100.0
    struct_exits = act_df['reason'].isin(["M15_STRUCTURE_BREAK", "MACRO_H1_INVALIDATION", "THESIS_EXHAUSTION_EXIT"]).sum() / len(act_df) * 100.0
    
    # Active Max Drawdown
    act_cum = act_df['pnl_usd'].cumsum()
    act_peak = act_cum.cummax()
    act_dd = (act_peak - act_cum).max()
    
    # Active Tail Risk (95th & 99th percentile loss)
    act_var95 = np.percentile(act_df['pnl_usd'], 5)
    act_var99 = np.percentile(act_df['pnl_usd'], 1)
    
    # ── 2. BASELINE METRICS ──
    base_wins = base_df[base_df['exit_pnl'] > 0]
    base_losses = base_df[base_df['exit_pnl'] <= 0]
    base_tot_pnl = base_df['exit_pnl'].sum()
    base_pf = abs(base_wins['exit_pnl'].sum() / base_losses['exit_pnl'].sum()) if len(base_losses) > 0 and base_losses['exit_pnl'].sum() != 0 else np.nan
    base_win_rate = (len(base_wins) / len(base_df)) * 100.0
    base_expectancy = base_df['exit_pnl'].mean()
    
    base_cum = base_df['exit_pnl'].cumsum()
    base_peak = base_cum.cummax()
    base_dd = (base_peak - base_cum).max()
    
    base_var95 = np.percentile(base_df['exit_pnl'], 5)
    base_var99 = np.percentile(base_df['exit_pnl'], 1)

    # ── COMPARATIVE OUTPUT TABLE ──
    print(f"{'Performance Metric':<38} | {'Fixed Baseline':<18} | {'Active Trade Manager':<20}")
    print("-" * 80)
    print(f"{'Total Sample Trades':<38} | {len(base_df):<18} | {len(act_df):<20}")
    print(f"{'Win Rate (%)':<38} | {base_win_rate:<17.1f}% | {act_win_rate:<19.1f}%")
    print(f"{'Total Net Profit ($)':<38} | ${base_tot_pnl:<17.2f} | ${act_tot_pnl:<19.2f}")
    print(f"{'Expectancy per Trade ($ / R)':<38} | ${base_expectancy:<17.2f} | ${act_expectancy:<8.2f} ({act_avg_r:+.2f} R)")
    print(f"{'Profit Factor (PF)':<38} | {base_pf:<18.2f} | {act_pf:<20.2f}")
    print(f"{'Maximum Drawdown ($)':<38} | ${base_dd:<17.2f} | ${act_dd:<19.2f}")
    print(f"{'Tail Risk (95th %ile Loss)':<38} | ${base_var95:<17.2f} | ${act_var95:<19.2f}")
    print(f"{'Tail Risk (99th %ile Loss)':<38} | ${base_var99:<17.2f} | ${act_var99:<19.2f}")
    print(f"{'Avg Maximum Adverse Excursion (MAE)':<38} | ${base_df['mae'].mean():<17.2f} | {act_df['mae_pips'].mean():<19.1f} pips")
    print(f"{'Avg Maximum Favorable Excursion (MFE)':<38} | ${base_df['mfe'].mean():<17.2f} | {act_df['mfe_pips'].mean():<19.1f} pips")
    print(f"{'Avg Profit Giveback':<38} | {'N/A (Fixed TP)':<18} | {act_giveback:<19.1f} pips")
    print(f"{'Stopped by Trailing (%)':<38} | {'0.0% (None)':<18} | {trail_exits:<19.1f}%")
    print(f"{'Structural Invalidation Exits (%)':<38} | {'0.0% (Waits full SL)':<18} | {struct_exits:<19.1f}%")
    print(f"{'Average Holding Time (Bars)':<38} | {base_df['bars'].mean():<18.1f} | {act_df['bars_held'].mean():<19.1f} bars")
    print("=" * 80)
    
    # Statistical Verdict
    print("\n[INSTITUTIONAL VALIDATION VERDICT]")
    if act_expectancy > base_expectancy and act_dd <= base_dd and abs(act_var95) <= abs(base_var95):
        print(">> ACCEPTED: Active Trade Manager delivers superior expectancy with strictly reduced tail risk and lower drawdown.")
    elif act_expectancy > base_expectancy:
        print(">> CONDITIONALLY ACCEPTED: Superior expectancy with comparable risk profile.")
    else:
        print(">> REJECTED: Fixed basket model exhibits higher statistical efficiency.")

def main():
    if not mt5.initialize():
        print("MT5 initialization failed.")
        return
        
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        try:
            act_trades, base_trades = run_simulation(sym, count=12000)
            analyze_and_compare(act_trades, base_trades, sym)
        except Exception as e:
            print(f"Error evaluating {sym}: {e}")
            
    mt5.shutdown()

if __name__ == "__main__":
    main()
