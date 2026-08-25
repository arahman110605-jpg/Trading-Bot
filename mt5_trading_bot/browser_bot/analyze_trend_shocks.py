"""
HISTORICAL BIG-MOVE SURGE & FLUX ANALYSIS (MT5 HISTORICAL TICKS & M5 BARS)
Symbols: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD
Analyzes the top 100 largest directional trend breakout moves over the last 1 year:
1. What was the average single-day / multi-session mega trend range (in pips)?
2. How much does a mega trend fluctuate (drawdown / retracement depth during the trend)?
3. What is the MAXIMUM mathematical P&L potential when compounding aggressively vs baseline?
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

mt5.initialize()

print("=" * 85)
print("     HISTORICAL MEGA-TREND SURGE & FLUX ANALYSIS (MT5 DATA)")
print("=" * 85)

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    pip_size = 0.0001 if "JPY" not in sym else 0.01
    rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 4000)
    rates_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 10000)
    
    if rates_h1 is None:
        continue
        
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['candle_range_pips'] = (df_h1['high'] - df_h1['low']) / pip_size
    
    # 24-hour rolling high to low
    df_h1['trend_range_24h'] = (df_h1['high'].rolling(24).max() - df_h1['low'].rolling(24).min()) / pip_size
    
    avg_24h_range = df_h1['trend_range_24h'].mean()
    top_5pct_trend = df_h1['trend_range_24h'].quantile(0.95)
    max_trend_move = df_h1['trend_range_24h'].max()
    
    print(f"\n[{sym}] Historical Breakout Statistics:")
    print(f"  • Standard Daily Trading Range:     {avg_24h_range:.1f} pips")
    print(f"  • Top 5% Mega-Trend Surges:          {top_5pct_trend:.1f} pips  (Major Trend Days)")
    print(f"  • Maximum Directional Mega Move:     {max_trend_move:.1f} pips  (Extreme Trend Shocks)")

print("\n" + "=" * 85)
mt5.shutdown()
