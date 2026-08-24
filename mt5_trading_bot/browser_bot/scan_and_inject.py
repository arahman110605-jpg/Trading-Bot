import MetaTrader5 as mt5
import pandas as pd
import sys
import urllib.request
import json
import time

sys.path.insert(0, 'd:/trading bot/mt5_trading_bot')
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', login=5054521327, server='MetaQuotes-Demo')
acc = mt5.account_info()
print(f"MT5 Connected: {acc.login} | Balance: {acc.balance} USD" if acc else "FAILED")

strategy = TrendMomentumStrategy(
    ema_fast=config.EMA_FAST, ema_slow=config.EMA_SLOW, ema_trend=config.EMA_TREND,
    rsi_period=config.RSI_PERIOD, rsi_buy_min=config.RSI_BUY_MIN, rsi_buy_max=config.RSI_BUY_MAX,
    rsi_sell_min=config.RSI_SELL_MIN, rsi_sell_max=config.RSI_SELL_MAX,
    atr_period=config.ATR_PERIOD, atr_sl_mult=config.ATR_SL_MULTIPLIER, atr_tp_mult=config.ATR_TP_MULTIPLIER
)

print("\nScanning live market...\n")
found_signals = {}

for sym in ['EURUSD', 'GBPUSD', 'USDJPY']:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 250)
    if rates is not None and len(rates) >= 220:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        sig = strategy.generate_signal(df)
        if sig:
            print(f"LIVE SIGNAL >> {sym}: {sig['signal']} @ {sig['price']} | SL: {sig['stop_loss']} | TP: {sig['take_profit']}")
            found_signals[sym] = sig
        else:
            print(f"{sym}: No signal on current M15 candle")
    else:
        print(f"{sym}: Insufficient data")

mt5.shutdown()

# Inject found signals into bridge
if found_signals:
    print("\nInjecting live signals into bridge server...")
    for sym, sig in found_signals.items():
        payload = {
            'symbol': sym,
            'signal': sig['signal'],
            'price': sig['price'],
            'stop_loss': sig['stop_loss'],
            'take_profit': sig['take_profit'],
            'reason': sig.get('reason', 'Live MT5 M15 Signal'),
            'timestamp': time.time()
        }
        req = urllib.request.Request(
            'http://localhost:8765/inject_signal',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req)
        print(f"Injected {sym}: {json.loads(res.read())['status']}")
else:
    print("\nNo signals generated currently - market is in consolidation phase")
    print("Strategy is waiting for clean trend + pullback alignment")
