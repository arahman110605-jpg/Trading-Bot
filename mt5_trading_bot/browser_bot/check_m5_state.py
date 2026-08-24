import MetaTrader5 as mt5
import pandas as pd
import ta

mt5.initialize()

print("=== M5 LIVE CANDLE CHECK ===")
for base in ["EURUSD#", "GBPUSD#"]:
    rates = mt5.copy_rates_from_pos(base, mt5.TIMEFRAME_M5, 0, 250)
    if rates is None:
        print(f"{base}: No data")
        continue
    df = pd.DataFrame(rates)
    c = df['close']
    df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()
    df['ema20'] = ta.trend.EMAIndicator(close=c, window=20).ema_indicator()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    trend = "UPTREND (Bullish)" if curr['close'] > curr['ema200'] else "DOWNTREND (Bearish)"
    cross_up = (curr['close'] > curr['ema20'] and prev['close'] <= prev['ema20'])
    cross_down = (curr['close'] < curr['ema20'] and prev['close'] >= prev['ema20'])
    
    print(f"\n[{base}] Price: {curr['close']:.5f} | EMA20: {curr['ema20']:.5f} | EMA200: {curr['ema200']:.5f}")
    print(f"  Macro Trend: {trend}")
    print(f"  Distance from EMA20: {abs(curr['close'] - curr['ema20']) / (0.0001):.1f} pips")
    print(f"  Crossing EMA20 Right Now: {cross_up or cross_down}")

mt5.shutdown()
