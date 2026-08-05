import sys, time
sys.stdout.reconfigure(encoding='utf-8')

from broker.angel_client import AngelClient
import config
from engine.risk_manager import RiskManager
from utils.trade_journal import TradeJournal
from engine.order_manager import OrderManager
from engine.strategy_runner import StrategyRunner, _compute_adx, TREND_ONLY_STRATEGIES

client = AngelClient()
journal = TradeJournal()
risk_mgr = RiskManager(journal=journal)
order_mgr = OrderManager(kite=client, risk=risk_mgr, journal=journal)
runner = StrategyRunner(kite=client, order_mgr=order_mgr, risk_mgr=risk_mgr)

print("=== DEBUGGING STRATEGY RUNNER TICK ===")
print("Market open?", risk_mgr.is_market_open())
allowed, reason = risk_mgr.is_new_entry_allowed()
print("New entry allowed?", allowed, "| Reason:", reason)

print("\nScanning Watchlist:")
for symbol in config.WATCHLIST:
    time.sleep(0.6)
    df = client.get_historical_data(symbol, interval=config.CANDLE_INTERVAL, days=5)
    if df is None or df.empty or len(df) < 30:
        print(f"{symbol:<12}: Insufficient data ({len(df) if df is not None else 0} candles)")
        continue

    adx = _compute_adx(df)
    trending = adx >= config.ADX_TREND_THRESHOLD
    print(f"{symbol:<12}: {len(df)} candles | ADX={adx:.1f} ({'TRENDING' if trending else 'MIXED/CHOPPY'})")

    for strategy in runner.strategies:
        if strategy.name in TREND_ONLY_STRATEGIES and not trending:
            continue

        sig = strategy.generate_signal(symbol, df)
        if sig.is_actionable:
            valid_risk, risk_reason = risk_mgr.validate_signal(sig)
            print(f"  📶 SIGNAL! [{strategy.name}] {sig.direction} {symbol} @ {sig.entry_price} | conf={sig.confidence:.0%} | valid_risk={valid_risk} ({risk_reason})")
