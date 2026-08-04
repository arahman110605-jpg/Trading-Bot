"""
credit_spreads.py — Hedged Option Spreads Strategy (Bull Call / Bear Put / Iron Condor).
"""

import random
from futures_options_bot.strategies.base_fo_strategy import BaseFOStrategy


class CreditSpreadsStrategy(BaseFOStrategy):

    def __init__(self):
        super().__init__("Hedged Credit Spreads")

    def generate_signal(self, symbol: str, spot_price: float) -> dict:
        rnd = random.random()

        if rnd < 0.03:  # Bull Call Spread
            return {
                "action": "BUY",
                "symbol": symbol,
                "option_type": "CE",
                "offset": 1,  # Buy ITM1 Call
                "reason": "Bull Call Spread — Defined Risk Trend",
                "strategy": self.name
            }

        return {"action": None}
