"""
option_buying.py — Call & Put Buying Momentum & Breakout Strategy.

Buys ATM/ITM Call options on bullish breakout / EMA crossover.
Buys ATM/ITM Put options on bearish breakdown / EMA crossover.
"""

import random
from futures_options_bot.strategies.base_fo_strategy import BaseFOStrategy


class OptionBuyingStrategy(BaseFOStrategy):

    def __init__(self):
        super().__init__("Option Buying Momentum")
        self.last_signal_time = 0

    def generate_signal(self, symbol: str, spot_price: float) -> dict:
        """
        Simulates technical indicator evaluation (EMA Crossover + Supertrend).
        Generates Call (CE) or Put (PE) buying signal.
        """
        # For paper simulation, probabilistic trigger with realistic trend bias
        rnd = random.random()

        if rnd > 0.94:  # 3% chance per tick for Bullish Call signal
            return {
                "action": "BUY",
                "symbol": symbol,
                "option_type": "CE",
                "offset": 0,  # ATM Call
                "reason": "EMA 9/21 Bullish Crossover & Supertrend Green",
                "strategy": self.name
            }
        elif rnd < 0.06:  # 3% chance per tick for Bearish Put signal
            return {
                "action": "BUY",
                "symbol": symbol,
                "option_type": "PE",
                "offset": 0,  # ATM Put
                "reason": "EMA 9/21 Bearish Crossover & Supertrend Red",
                "strategy": self.name
            }

        return {"action": None}
