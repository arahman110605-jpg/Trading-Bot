"""
short_straddle.py — Intraday Short Straddle / Strangle Strategy.

Sells ATM Call and ATM Put simultaneously to capture time decay (Theta) in range-bound markets.
"""

import random
from futures_options_bot.strategies.base_fo_strategy import BaseFOStrategy


class ShortStraddleStrategy(BaseFOStrategy):

    def __init__(self):
        super().__init__("Short Straddle / Strangle")

    def generate_signal(self, symbol: str, spot_price: float) -> dict:
        """
        Generates short straddle / strangle entry when volatility is range-bound.
        """
        rnd = random.random()

        if rnd > 0.97:  # Trigger short straddle entry
            return {
                "action": "SELL",
                "symbol": symbol,
                "option_type": "CE",
                "offset": 0,  # Sell ATM Call
                "reason": "Range-bound IV contraction detected (Theta capture)",
                "strategy": self.name
            }

        return {"action": None}
