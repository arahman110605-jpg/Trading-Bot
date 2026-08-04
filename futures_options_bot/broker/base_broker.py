"""
base_broker.py — Abstract Base Class for F&O Broker Interface.
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseFOBroker(ABC):

    @abstractmethod
    def connect((self) -> bool:
        """Authenticate with the broker API."""
        pass

    @abstractmethod
    def get_underlying_ltp(self, symbol: str) -> float:
        """Fetch real-time spot price of underlying index or stock."""
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str, expiry_date) -> list:
        """Fetch available options strikes (CE and PE) for an underlying."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, option_type: str, strike: float,
                    transaction_type: str, quantity: int, order_type: str = "MARKET",
                    price: float = 0.0) -> dict:
        """Place an F&O order (CE/PE/FUT)."""
        pass

    @abstractmethod
    def get_positions(self) -> list:
        """Get currently active open F&O positions."""
        pass

    @abstractmethod
    def square_off_all(self) -> bool:
        """Close all open F&O positions immediately."""
        pass
