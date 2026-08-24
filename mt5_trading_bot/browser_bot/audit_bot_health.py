import MetaTrader5 as mt5
import pandas as pd
import ta

if not mt5.initialize():
    print("MT5 Init Failed:", mt5.last_error())
    exit(1)

acc = mt5.account_info()
print("=" * 60)
print(f"  ACCOUNT: #{acc.login} | Name: {acc.name} | Balance: ${acc.balance:.2f} | Server: {acc.server}")
print("=" * 60)

# 1. Check Open Positions
positions = mt5.positions_get()
print(f"\n[1] OPEN POSITIONS: {len(positions) if positions else 0}")
if positions:
    for p in positions:
        print(f"  Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {'BUY' if p.type==0 else 'SELL'} | Lots: {p.volume} | Open: {p.price_open} | Profit: ${p.profit:.2f}")
else:
    print("  No positions currently open.")

# 2. Check Live M5 Technical Market State for all 3 pairs
print("\n[2] LIVE M5 MARKET STATE & DISTANCE TO ENTRY:")
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 250)
    if rates is None:
        print(f"  {sym}: No data")
        continue
    df = pd.DataFrame(rates)
    c = df['close']
    df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()
    df['ema20'] = ta.trend.EMAIndicator(close=c, window=20).ema_indicator()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    pip_size = 0.0001 if 'JPY' not in sym else 0.01
    
    trend = "UPTREND (Bullish)" if curr['close'] > curr['ema200'] else "DOWNTREND (Bearish)"
    dist_ema20 = abs(curr['close'] - curr['ema20']) / pip_size
    
    cross_up = (curr['close'] > curr['ema20'] and prev['close'] <= prev['ema20'])
    cross_down = (curr['close'] < curr['ema20'] and prev['close'] >= prev['ema20'])
    
    print(f"\n  [{sym}] Price: {curr['close']:.5f}")
    print(f"    Macro Trend: {trend} (EMA200: {curr['ema200']:.5f})")
    print(f"    EMA20: {curr['ema20']:.5f} | Distance: {dist_ema20:.1f} pips")
    print(f"    Trigger Condition Met (Crossover): {cross_up or cross_down}")

mt5.shutdown()
