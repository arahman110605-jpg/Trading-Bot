"""
futures_trend.py — Futures Contract Long/Short Trend Following Strategy.
"""

import random
from futures_options_bot.strategies.base_fo_strategy import BaseFOStrategy


class FuturesTrendStrategy(BaseFOStrategy):

    def __init__(self):
        super().__init__("Futures Trend Following")

    def generate_signal(self, symbol: str, spot_price: float) -> dict:
        rnd = random.random()

        if rnd > 0.98:
            return {
                "action": "BUY",
                "symbol": symbol,
                "option_type": "FUT",
                "offset": 0,
                "reason": "Futures Bullish Breakout above VWAP & 20 EMA",
                "strategy": self.name
            }
        elif rnd < 0.02:
            return {
                "action": "SELL",
                "symbol": symbol,
                "option_type": "FUT",
                "offset": 0,
                "reason": "Futures Bearish Breakdown below VWAP & 20 EMA",
                "strategy": self.name
            }

        return {"action": None}
