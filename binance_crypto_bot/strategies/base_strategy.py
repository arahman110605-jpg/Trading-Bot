"""
base_strategy.py — Abstract base strategy class for Crypto trading strategies.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class BaseCryptoStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze candlestick data and return signal dictionary:
        {
            "action": "BUY" | "SELL" | "HOLD",
            "symbol": str,
            "price": float,
            "stop_loss": float,
            "take_profit": float,
            "reason": str,
            "strategy": str
        }
        """
        pass
