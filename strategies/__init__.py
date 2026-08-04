"""
strategies/__init__.py
"""
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.rsi_strategy  import RSIStrategy
from strategies.vwap_strategy import VWAPStrategy
from strategies.supertrend    import SupertrendStrategy
from strategies.candlestick   import CandlestickStrategy

__all__ = [
    "EMACrossoverStrategy",
    "RSIStrategy",
    "VWAPStrategy",
    "SupertrendStrategy",
    "CandlestickStrategy",
]
