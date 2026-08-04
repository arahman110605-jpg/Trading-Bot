"""
base_fo_strategy.py — Abstract Base Class for F&O Strategies.
"""

from abc import ABC, abstractmethod


class BaseFOStrategy(ABC):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, symbol: str, spot_price: float) -> dict:
        """
        Evaluates current underlying market data and returns signal dictionary:
          {
            "action": "BUY" | "SELL" | None,
            "symbol": symbol,
            "option_type": "CE" | "PE" | "FUT",
            "offset": 0,  # 0=ATM, 1=ITM1, -1=OTM1
            "strategy": self.name
          }
        """
        pass
