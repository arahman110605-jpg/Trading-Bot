"""
Price Action & Candlestick Anatomy Engine (SMC / Liquidity / Order Flow)
Analyzes:
1. Candle Body-to-Wick Ratio & Rejection Wicks (Pinbars / Hammer / Shooting Star)
2. Fair Value Gaps (FVG) / Imbalances & Liquidity Sweeps
3. Momentum Exhaustion & Micro Structure Breaks (CHoCH / BOS)
4. Dynamic Structure Exits (Exiting on opposite rejection / liquidity sweep)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def analyze_candle_behavior(df: pd.DataFrame):
    """
    Evaluates institutional candlestick behavior:
    - Buying/Selling Volume Pressure
    - Wick Rejection (Absorption of Liquidity)
    - Momentum Body vs Indecision (Doji / Exhaustion)
    """
    if len(df) < 50:
        return None

    c = df['close'].values
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    
    # Last 3 closed candles
    curr_o, curr_c, curr_h, curr_l = o[-1], c[-1], h[-1], l[-1]
    prev_o, prev_c, prev_h, prev_l = o[-2], c[-2], h[-2], l[-2]
    
    curr_body = abs(curr_c - curr_o)
    curr_range = curr_h - curr_l if (curr_h - curr_l) > 0 else 0.0001
    
    upper_wick = curr_h - max(curr_o, curr_c)
    lower_wick = min(curr_o, curr_c) - curr_l
    
    # 1. Bullish Liquidity Sweep & Hammer (Strong Rejection of Lows)
    bullish_rejection = (lower_wick >= curr_body * 2.0) and (lower_wick / curr_range >= 0.55) and (curr_c >= prev_l)
    
    # 2. Bearish Liquidity Sweep & Shooting Star (Strong Rejection of Highs)
    bearish_rejection = (upper_wick >= curr_body * 2.0) and (upper_wick / curr_range >= 0.55) and (curr_c <= prev_h)
    
    # 3. Momentum Engulfing / Institutional Displacement
    bull_displacement = (curr_c > curr_o) and (curr_body >= curr_range * 0.70) and (curr_c > prev_h)
    bear_displacement = (curr_c < curr_o) and (curr_body >= curr_range * 0.70) and (curr_c < prev_l)
    
    # 4. Fair Value Gap (FVG) Bullish & Bearish
    bull_fvg = (l[-1] > h[-3]) # Imbalance between bar 1 high and bar 3 low
    bear_fvg = (h[-1] < l[-3])
    
    return {
        'bullish_rejection': bullish_rejection,
        'bearish_rejection': bearish_rejection,
        'bull_displacement': bull_displacement,
        'bear_displacement': bear_displacement,
        'bull_fvg': bull_fvg,
        'bear_fvg': bear_fvg,
        'upper_wick_pct': round((upper_wick / curr_range) * 100, 1),
        'lower_wick_pct': round((lower_wick / curr_range) * 100, 1),
        'body_pct': round((curr_body / curr_range) * 100, 1)
    }

if __name__ == "__main__":
    mt5.initialize()
    for s in ["EURUSD", "GBPUSD"]:
        rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M5, 0, 50)
        if rates is not None:
            df = pd.DataFrame(rates)
            analysis = analyze_candle_behavior(df)
            print(f"\n[{s} CANDLE ANATOMY NOW]:")
            print(f"  Body: {analysis['body_pct']}% | Lower Wick: {analysis['lower_wick_pct']}% | Upper Wick: {analysis['upper_wick_pct']}%")
            print(f"  Bull Rejection: {analysis['bullish_rejection']} | Bear Rejection: {analysis['bearish_rejection']}")
            print(f"  Displacement: {'BULLISH EXPANSION' if analysis['bull_displacement'] else ('BEARISH EXPANSION' if analysis['bear_displacement'] else 'Normal')}")
    mt5.shutdown()
