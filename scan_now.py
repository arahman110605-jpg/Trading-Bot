import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from broker.angel_client import AngelClient
import config
from strategies import EMACrossoverStrategy, RSIStrategy, VWAPStrategy, SupertrendStrategy, CandlestickStrategy, ORBStrategy
from engine.strategy_runner import _compute_adx

client = AngelClient()
strategies = [EMACrossoverStrategy(), RSIStrategy(), VWAPStrategy(), SupertrendStrategy(), CandlestickStrategy(), ORBStrategy()]

now_str = time.strftime("%H:%M:%S")
print(f"=== REAL-TIME SCAN AT {now_str} IST ===")
print(f"Watchlist count: {len(config.WATCHLIST)}")

total_signals = 0
for symbol in config.WATCHLIST[:15]:
    time.sleep(0.6)
    df = client.get_historical_data(symbol, interval='5minute', days=3)
    if df is None or df.empty or len(df) < 30:
        print(f"{symbol:<12}: Insufficient data")
        continue

    adx = _compute_adx(df)
    print(f"Scanning {symbol:<12} | 5-min candles={len(df)} | ADX={adx:.1f} | Last close={df['close'].iloc[-1]}")
    for strat in strategies:
        sig = strat.generate_signal(symbol, df)
        if sig.is_actionable:
            total_signals += 1
            print(f"  📶 SIGNAL! {sig.direction:<4} {symbol:<10} [{strat.name:<12}] conf={sig.confidence:.0%} entry={sig.entry_price}")

print(f"\nTotal actionable signals generated: {total_signals}")
