"""
Backtest: How many signals fire during 2 PM - 5 PM IST on M5
and what would P&L look like with $905 balance
"""
import MetaTrader5 as mt5
import pandas as pd
import ta
from datetime import datetime, timezone, timedelta

mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe',
               login=5054521327, server='MetaQuotes-Demo')

IST = timezone(timedelta(hours=5, minutes=30))
SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY']
BALANCE = 905.0
LEVERAGE = 100
MARGIN_USE = 0.75

def get_signal(df):
    if len(df) < 220:
        return None
    df = df.copy()
    c = df['close']
    df['ema5']   = ta.trend.EMAIndicator(close=c, window=5).ema_indicator()
    df['ema13']  = ta.trend.EMAIndicator(close=c, window=13).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()
    df['rsi']    = ta.momentum.RSIIndicator(close=c, window=14).rsi()
    macd = ta.trend.MACD(close=c, window_fast=12, window_slow=26, window_sign=9)
    df['macd_diff'] = macd.macd_diff()
    df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

    curr = df.iloc[-2]
    prev = df.iloc[-3]
    price = df.iloc[-1]['close']
    if pd.isna(curr['ema200']) or pd.isna(curr['atr']) or curr['atr'] <= 0:
        return None
    atr = curr['atr']
    bull = (curr['ema5'] > curr['ema13']) and (prev['ema5'] <= prev['ema13'])
    bear = (curr['ema5'] < curr['ema13']) and (prev['ema5'] >= prev['ema13'])
    if curr['close'] > curr['ema200'] and bull and curr['macd_diff'] > 0 and 35 <= curr['rsi'] <= 65:
        return {'signal':'BUY','price':price,'sl':atr*1.2,'tp':atr*2.5,'atr':atr}
    if curr['close'] < curr['ema200'] and bear and curr['macd_diff'] < 0 and 35 <= curr['rsi'] <= 65:
        return {'signal':'SELL','price':price,'sl':atr*1.2,'tp':atr*2.5,'atr':atr}
    return None

# Scan last 30 days of M5 data and count signals in 2-5 PM IST window
print("=" * 55)
print("  SIGNAL ANALYSIS: 2 PM - 5 PM IST | Last 30 Days")
print("=" * 55)

total_signals = []
daily_counts = {}

for sym in SYMBOLS:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 8640)  # 30 days M5
    if rates is None:
        continue
    df_all = pd.DataFrame(rates)
    df_all['time'] = pd.to_datetime(df_all['time'], unit='s', utc=True).dt.tz_convert(IST)
    df_all.rename(columns={'tick_volume':'volume'}, inplace=True)

    signals_sym = []
    pip = 0.0001 if 'JPY' not in sym else 0.01

    for i in range(220, len(df_all)):
        row_time = df_all.iloc[i]['time']
        hour = row_time.hour
        if not (14 <= hour < 17):  # 2 PM to 5 PM IST
            continue
        chunk = df_all.iloc[i-220:i+1].reset_index(drop=True)
        sig = get_signal(chunk)
        if sig:
            # Check not duplicate (no signal within last 10 bars)
            if signals_sym and (df_all.iloc[i]['time'] - signals_sym[-1]['time']).seconds < 600:
                continue
            price = sig['price']
            lots = round(max(0.01, min(round((BALANCE * MARGIN_USE / (100000 * price / LEVERAGE)) / 0.01) * 0.01, 5.0)), 2)
            pip_val = lots * (10 if 'JPY' not in sym else 1000)
            win_pnl  = round(sig['tp'] / pip * pip_val, 2)
            loss_pnl = round(-sig['sl'] / pip * pip_val, 2)
            signals_sym.append({
                'time': df_all.iloc[i]['time'],
                'sym': sym,
                'dir': sig['signal'],
                'lots': lots,
                'atr_pips': round(sig['atr'] / pip, 1),
                'sl_pips': round(sig['sl'] / pip, 1),
                'tp_pips': round(sig['tp'] / pip, 1),
                'win': win_pnl,
                'loss': loss_pnl
            })
            date_key = str(row_time.date())
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1

    total_signals.extend(signals_sym)
    print(f"\n  {sym}: {len(signals_sym)} signals in last 30 days ({len(signals_sym)/30:.1f}/day avg)")
    for s in signals_sym[-5:]:
        print(f"    {s['time'].strftime('%d %b %H:%M')} | {s['dir']} | {s['lots']}L | TP:{s['tp_pips']}pips (+${s['win']}) SL:{s['sl_pips']}pips (-${abs(s['loss'])})")

print("\n" + "=" * 55)
print("  TODAY's FORECAST (2-5 PM IST)")
print("=" * 55)
total_day_avg = len(total_signals) / 30
wins_day = round(total_day_avg * 0.60)
losses_day = round(total_day_avg * 0.40)

if total_signals:
    avg_win  = sum(s['win']  for s in total_signals) / len(total_signals)
    avg_loss = sum(s['loss'] for s in total_signals) / len(total_signals)
    avg_lots = sum(s['lots'] for s in total_signals) / len(total_signals)
    print(f"  Expected trades:  {total_day_avg:.1f} per session")
    print(f"  Avg lot size:     {avg_lots:.2f}")
    print(f"  Win (60%):        +${avg_win:.2f} per trade")
    print(f"  Loss (40%):       -${abs(avg_loss):.2f} per trade")
    print(f"\n  SCENARIOS WITH $905 BALANCE:")
    for n in [2, 3, 4, 5]:
        w = round(n * 0.6)
        l = n - w
        pnl = round(w * avg_win + l * avg_loss, 2)
        bal = round(905 + pnl, 2)
        print(f"  {n} trades | {w}W {l}L | P&L: ${pnl:+.2f} | Balance: ${bal:.2f}")

print("=" * 55)
mt5.shutdown()
