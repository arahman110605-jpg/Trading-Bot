import MetaTrader5 as mt5
import pandas as pd
import ta

mt5.initialize()

print("=" * 75)
print("     LIVE ENTRY CONFLUENCE RADAR (M5 / M15 / H1)")
print("=" * 75)

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    rates_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 250)
    rates_m15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 150)
    rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 250)
    
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['ema20'] = ta.trend.EMAIndicator(df_m5['close'], window=20).ema_indicator()
    df_m5['ema200'] = ta.trend.EMAIndicator(df_m5['close'], window=200).ema_indicator()
    
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['ema20'] = ta.trend.EMAIndicator(df_m15['close'], window=20).ema_indicator()
    
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['ema200'] = ta.trend.EMAIndicator(df_h1['close'], window=200).ema_indicator()
    
    c_m5 = df_m5['close'].iloc[-1]
    prev_c_m5 = df_m5['close'].iloc[-2]
    ema20_m5 = df_m5['ema20'].iloc[-1]
    prev_ema20_m5 = df_m5['ema20'].iloc[-2]
    ema200_m5 = df_m5['ema200'].iloc[-1]
    
    c_m15 = df_m15['close'].iloc[-1]
    ema20_m15 = df_m15['ema20'].iloc[-1]
    
    c_h1 = df_h1['close'].iloc[-1]
    ema200_h1 = df_h1['ema200'].iloc[-1]
    
    pip_size = 0.0001 if "JPY" not in sym else 0.01
    dist_pips = abs(c_m5 - ema20_m5) / pip_size
    
    h1_regime = "BULLISH (UP)" if c_h1 > ema200_h1 else "BEARISH (DOWN)"
    m15_struct = "BULLISH (UP)" if c_m15 > ema20_m15 else "BEARISH (DOWN)"
    m5_trend = "BULLISH (UP)" if c_m5 > ema200_m5 else "BEARISH (DOWN)"
    m5_loc = "ABOVE 20 EMA" if c_m5 > ema20_m5 else "BELOW 20 EMA"
    
    print(f"\n[{sym}] Price: {c_m5:.5f}")
    print(f"  H1 Macro Regime:   {h1_regime} (Price: {c_h1:.5f} vs EMA200: {ema200_h1:.5f})")
    print(f"  M15 Structure:     {m15_struct} (Price: {c_m15:.5f} vs EMA20: {ema20_m15:.5f})")
    print(f"  M5 Macro Trend:    {m5_trend} (Price: {c_m5:.5f} vs EMA200: {ema200_m5:.5f})")
    print(f"  M5 Micro Position: {m5_loc} (Price: {c_m5:.5f} vs EMA20: {ema20_m5:.5f})")
    print(f"  >> Trigger Distance: {dist_pips:.1f} pips to next M5 crossover")

print("\n" + "=" * 75)
mt5.shutdown()
