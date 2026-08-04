import sys
sys.stdout.reconfigure(encoding='utf-8')

print('=== PHASE 1: Import tests ===')
from strategies import EMACrossoverStrategy, RSIStrategy, VWAPStrategy, SupertrendStrategy, CandlestickStrategy, ORBStrategy
print('All 6 strategies imported OK')
from engine.risk_manager import RiskManager, _now_ist
from engine.order_manager import OrderManager
from engine.strategy_runner import StrategyRunner, _compute_adx
print('All engine modules imported OK')

print()
print('=== PHASE 2: Signal generation tests ===')
import pandas as pd, numpy as np
from datetime import datetime, timedelta

def make_df(n=120):
    dates = [datetime.now() - timedelta(minutes=i*5) for i in range(n, 0, -1)]
    np.random.seed(42)
    closes = 1000 + np.cumsum(np.random.randn(n) * 3)
    opens  = closes + np.random.randn(n) * 2
    highs  = np.maximum(opens, closes) + abs(np.random.randn(n))
    lows   = np.minimum(opens, closes) - abs(np.random.randn(n))
    vols   = np.random.randint(100000, 500000, n)
    return pd.DataFrame({'open': opens,'high': highs,'low': lows,'close': closes,'volume': vols},
                        index=pd.DatetimeIndex(dates))

df = make_df()
for Strat in [EMACrossoverStrategy, RSIStrategy, VWAPStrategy, SupertrendStrategy, CandlestickStrategy, ORBStrategy]:
    s = Strat()
    sig = s.generate_signal('TEST', df)
    print(f'  {s.name:<16} -> {sig.direction:<5}  conf={sig.confidence:.0%}')

print()
print('=== PHASE 3: ADX computation test ===')
adx = _compute_adx(df)
print(f'  ADX = {adx}')

print()
print('=== PHASE 4: Risk manager IST timezone test ===')
now_ist = _now_ist()
fmt = now_ist.strftime('%Y-%m-%d %H:%M:%S')
print(f'  Current IST time: {fmt}')
print(f'  Timezone: {now_ist.tzname()}')

print()
print('=== ALL TESTS PASSED ===')
