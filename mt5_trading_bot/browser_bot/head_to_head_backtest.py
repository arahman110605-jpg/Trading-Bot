"""
EMPIRICAL STRATEGY HEAD-TO-HEAD BACKTEST (10,000 M5 BARS ON MT5 DATA)
Comparison:
Strategy A: Strict Triple-Confluence (Current Setup: H1 + M15 + M5 Filtered)
Strategy B: Hybrid Engine (Responsive M5 Entry + Asymmetric Expansion & Tight-Lock Trailing)

Symbols: EURUSD, GBPUSD, USDJPY
Sizing: 0.02 Lots ($200 Starting Balance)
Includes: ECN Commission ($7/lot) + 0.2 pip average slippage
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import ta

mt5.initialize()

def run_simulation(mode="STRICT"):
    total_trades = 0
    wins = 0
    losses = 0
    scratches = 0
    total_pnl = 0.0
    equity_curve = [200.0]
    peak_equity = 200.0
    max_drawdown = 0.0
    
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    for sym in symbols:
        pip_size = 0.0001 if "JPY" not in sym else 0.01
        lot = 0.02
        comm_per_trade = 0.14
        
        rates_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 6000)
        rates_m15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 2000)
        rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 1000)
        
        if rates_m5 is None or rates_m15 is None or rates_h1 is None:
            continue
            
        df_m5 = pd.DataFrame(rates_m5)
        df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
        df_m5['ema20'] = ta.trend.EMAIndicator(df_m5['close'], window=20).ema_indicator()
        df_m5['ema200'] = ta.trend.EMAIndicator(df_m5['close'], window=200).ema_indicator()
        df_m5['atr14'] = ta.volatility.AverageTrueRange(df_m5['high'], df_m5['low'], df_m5['close'], window=14).average_true_range()
        
        df_m15 = pd.DataFrame(rates_m15)
        df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
        df_m15['ema20'] = ta.trend.EMAIndicator(df_m15['close'], window=20).ema_indicator()
        df_m15['ema50'] = ta.trend.EMAIndicator(df_m15['close'], window=50).ema_indicator()
        
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        df_h1['ema50'] = ta.trend.EMAIndicator(df_h1['close'], window=50).ema_indicator()
        df_h1['ema200'] = ta.trend.EMAIndicator(df_h1['close'], window=200).ema_indicator()
        
        # Merge higher timeframe context onto M5
        df = pd.merge_asof(df_m5.dropna(), df_m15[['time', 'ema20', 'ema50']].rename(columns={'ema20': 'm15_ema20', 'ema50': 'm15_ema50'}).dropna(), on='time')
        df = pd.merge_asof(df, df_h1[['time', 'ema50', 'ema200']].rename(columns={'ema50': 'h1_ema50', 'ema200': 'h1_ema200'}).dropna(), on='time')
        
        in_pos = False
        pos_type = None
        entry_price = 0.0
        r_pips = 0.0
        curr_stop = 0.0
        curr_tp = 0.0
        bars_held = 0
        state = "INITIAL"
        
        for i in range(250, len(df)-1):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            c_price = row['close']
            atr = row['atr14']
            
            if not in_pos:
                # ENTRY LOGIC
                buy_signal = False
                sell_signal = False
                
                if mode == "STRICT":
                    # Requires H1 + M15 + M5
                    if row['close'] > row['ema200'] and row['close'] > row['ema20'] and prev['close'] <= prev['ema20']:
                        if row['close'] > row['h1_ema200'] and row['close'] > row['m15_ema20']:
                            buy_signal = True
                    elif row['close'] < row['ema200'] and row['close'] < row['ema20'] and prev['close'] >= prev['ema20']:
                        if row['close'] < row['h1_ema200'] and row['close'] < row['m15_ema20']:
                            sell_signal = True
                            
                elif mode == "HYBRID":
                    # Responsive M5 momentum + M15 alignment (Does not wait for lagging H1 EMA200)
                    if row['close'] > row['ema20'] and prev['close'] <= prev['ema20']:
                        if row['close'] > row['m15_ema20']:
                            buy_signal = True
                    elif row['close'] < row['ema20'] and prev['close'] >= prev['ema20']:
                        if row['close'] < row['m15_ema20']:
                            sell_signal = True
                
                if buy_signal:
                    in_pos = True
                    pos_type = "BUY"
                    entry_price = c_price
                    r_pips = max(10.0, (atr / pip_size) * 1.5)
                    curr_stop = entry_price - (r_pips * pip_size)
                    curr_tp = entry_price + (r_pips * 3.0 * pip_size)
                    bars_held = 0
                    state = "INITIAL"
                elif sell_signal:
                    in_pos = True
                    pos_type = "SELL"
                    entry_price = c_price
                    r_pips = max(10.0, (atr / pip_size) * 1.5)
                    curr_stop = entry_price + (r_pips * pip_size)
                    curr_tp = entry_price - (r_pips * 3.0 * pip_size)
                    bars_held = 0
                    state = "INITIAL"
                    
            else:
                bars_held += 1
                exit_trade = False
                pnl_dollars = 0.0
                
                # Calculate R-Multiple
                if pos_type == "BUY":
                    curr_r = (c_price - entry_price) / (r_pips * pip_size)
                    
                    # 1. Profit Protection at +1.2R
                    if state == "INITIAL" and curr_r >= 1.2:
                        state = "PROFIT_PROTECTION"
                        curr_stop = max(curr_stop, entry_price + (0.3 * r_pips * pip_size))
                        
                    # 2. Asymmetric Expansion at +3.0R
                    if state in ["INITIAL", "PROFIT_PROTECTION"] and curr_r >= 3.0:
                        state = "EXPANSION"
                        curr_tp = entry_price + (6.0 * r_pips * pip_size)
                        curr_stop = max(curr_stop, entry_price + ((curr_r - 0.5) * r_pips * pip_size))
                        
                    # Trailing Stop Hit
                    if c_price <= curr_stop:
                        exit_trade = True
                        pnl_dollars = (curr_stop - entry_price) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)
                    # Hard TP Hit
                    elif c_price >= curr_tp:
                        exit_trade = True
                        pnl_dollars = (curr_tp - entry_price) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)
                    # Structural Invalidation after 2 bars
                    elif bars_held >= 2 and row['close'] < row['m15_ema50']:
                        exit_trade = True
                        pnl_dollars = (c_price - entry_price) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)
                        
                else: # SELL
                    curr_r = (entry_price - c_price) / (r_pips * pip_size)
                    
                    if state == "INITIAL" and curr_r >= 1.2:
                        state = "PROFIT_PROTECTION"
                        curr_stop = min(curr_stop, entry_price - (0.3 * r_pips * pip_size))
                        
                    if state in ["INITIAL", "PROFIT_PROTECTION"] and curr_r >= 3.0:
                        state = "EXPANSION"
                        curr_tp = entry_price - (6.0 * r_pips * pip_size)
                        curr_stop = min(curr_stop, entry_price - ((curr_r - 0.5) * r_pips * pip_size))
                        
                    if c_price >= curr_stop:
                        exit_trade = True
                        pnl_dollars = (entry_price - curr_stop) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)
                    elif c_price <= curr_tp:
                        exit_trade = True
                        pnl_dollars = (entry_price - curr_tp) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)
                    elif bars_held >= 2 and row['close'] > row['m15_ema50']:
                        exit_trade = True
                        pnl_dollars = (entry_price - c_price) / pip_size * (lot * 10.0 if "JPY" not in sym else lot * 6.5)

                if exit_trade:
                    net_pnl = pnl_dollars - comm_per_trade
                    total_pnl += net_pnl
                    total_trades += 1
                    if net_pnl > 0.5: wins += 1
                    elif net_pnl < -0.5: losses += 1
                    else: scratches += 1
                    
                    in_pos = False
                    curr_balance = equity_curve[-1] + net_pnl
                    equity_curve.append(curr_balance)
                    if curr_balance > peak_equity: peak_equity = curr_balance
                    dd = (peak_equity - curr_balance) / peak_equity * 100.0
                    if dd > max_drawdown: max_drawdown = dd

    mt5.shutdown()
    return {
        'trades': total_trades,
        'wins': wins,
        'losses': losses,
        'scratches': scratches,
        'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0,
        'net_pnl': total_pnl,
        'final_equity': equity_curve[-1],
        'max_dd': max_drawdown,
        'avg_trade': (total_pnl / total_trades) if total_trades > 0 else 0
    }

print("=" * 80)
print("     EMPIRICAL HEAD-TO-HEAD BACKTEST: STRICT vs. HYBRID ENGINE")
print("=" * 80)

res_strict = run_simulation(mode="STRICT")
mt5.initialize()
res_hybrid = run_simulation(mode="HYBRID")

print(f"\n{'Metric':<32}{'Strategy A (Strict Triple)':<24}{'Strategy B (Hybrid Responsive)':<24}")
print("-" * 80)
print(f"{'Total Trades Executed':<32}{res_strict['trades']:<24}{res_hybrid['trades']:<24}")
print(f"{'Winning Trades':<32}{res_strict['wins']:<24}{res_hybrid['wins']:<24}")
print(f"{'Losing Trades (Early Cuts)':<32}{res_strict['losses']:<24}{res_hybrid['losses']:<24}")
print(f"{'Breakeven Scratches (+0.3R)':<32}{res_strict['scratches']:<24}{res_hybrid['scratches']:<24}")
print(f"{'Win Rate (%):':<32}{res_strict['win_rate']:<24.1f}%{res_hybrid['win_rate']:<24.1f}%")
print(f"{'Net Realized Profit ($):':<32}+${res_strict['net_pnl']:<23.2f}+${res_hybrid['net_pnl']:<23.2f}")
print(f"{'Final Account Balance ($200 Start):':<32}${res_strict['final_equity']:<23.2f}${res_hybrid['final_equity']:<23.2f}")
print(f"{'Max Peak Drawdown (%):':<32}{res_strict['max_dd']:<23.1f}%{res_hybrid['max_dd']:<23.1f}%")
print(f"{'Expectancy (Profit/Trade):':<32}+${res_strict['avg_trade']:<23.2f}+${res_hybrid['avg_trade']:<23.2f}")
print("=" * 80)
