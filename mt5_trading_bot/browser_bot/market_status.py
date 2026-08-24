import MetaTrader5 as mt5
import pandas as pd
import sys
import ta

sys.path.insert(0, 'd:/trading bot/mt5_trading_bot')

if not mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', login=5054521327, server='MetaQuotes-Demo'):
    print("MT5 Init Failed")
    sys.exit(1)

symbols = ["EURUSD", "GBPUSD", "USDJPY"]

print("=== M5 MARKET CONDITION SNAPSHOT ===")
for sym in symbols:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 250)
    if rates is None or len(rates) < 220:
        print(f"{sym}: No data")
        continue
    
    df = pd.DataFrame(rates)
    c = df['close']
    df['ema5'] = ta.trend.EMAIndicator(close=c, window=5).ema_indicator()
    df['ema13'] = ta.trend.EMAIndicator(close=c, window=13).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(close=c, window=14).rsi()
    macd = ta.trend.MACD(close=c, window_fast=12, window_slow=26, window_sign=9)
    df['macd_diff'] = macd.macd_diff()
    
    curr = df.iloc[-2]
    prev = df.iloc[-3]
    latest = df.iloc[-1]
    
    bull_cross = (curr['ema5'] > curr['ema13']) and (prev['ema5'] <= prev['ema13'])
    bear_cross = (curr['ema5'] < curr['ema13']) and (prev['ema5'] >= prev['ema13'])
    
    print(f"\n[{sym}] Price: {latest['close']:.5f}")
    print(f"  EMA200: {curr['ema200']:.5f} | Trend: {'UPTREND (Price > EMA200)' if curr['close'] > curr['ema200'] else 'DOWNTREND (Price < EMA200)'}")
    print(f"  EMA5: {curr['ema5']:.5f} | EMA13: {curr['ema13']:.5f} | BullCross: {bull_cross} | BearCross: {bear_cross}")
    print(f"  RSI(14): {curr['rsi']:.1f} (Valid: 35-65 -> {35 <= curr['rsi'] <= 65})")
    print(f"  MACD Hist: {curr['macd_diff']:.6f} ({'Positive' if curr['macd_diff'] > 0 else 'Negative'})")

mt5.shutdown()
