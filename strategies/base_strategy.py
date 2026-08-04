"""
strategies/base_strategy.py — Abstract base class for all trading strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Signal:
    """Encapsulates a trading signal produced by a strategy."""
    symbol: str
    direction: str          # "BUY" | "SELL" | "NONE"
    strategy: str
    entry_price: float
    stop_loss: float
    target: float
    confidence: float = 1.0  # 0.0 – 1.0
    notes: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.direction in ("BUY", "SELL")

    @property
    def risk(self) -> float:
        if self.direction == "BUY":
            return abs(self.entry_price - self.stop_loss)
        return abs(self.stop_loss - self.entry_price)

    @property
    def reward(self) -> float:
        if self.direction == "BUY":
            return abs(self.target - self.entry_price)
        return abs(self.entry_price - self.target)

    @property
    def rr_ratio(self) -> float:
        return round(self.reward / self.risk, 2) if self.risk > 0 else 0.0

    def __str__(self) -> str:
        return (
            f"[{self.strategy}] {self.direction} {self.symbol} "
            f"@ {self.entry_price:.2f} | SL={self.stop_loss:.2f} "
            f"| TGT={self.target:.2f} | R:R={self.rr_ratio}"
        )


NO_SIGNAL = lambda symbol, strategy: Signal(
    symbol=symbol,
    direction="NONE",
    strategy=strategy,
    entry_price=0,
    stop_loss=0,
    target=0,
)


class BaseStrategy(ABC):
    """
    All strategies inherit from this class and implement `generate_signal`.
    """

    name: str = "base"

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Signal:
        """
        Given an OHLCV DataFrame, return a Signal.
        Subclasses must implement _compute().
        """
        if df is None or len(df) < 30:
            return NO_SIGNAL(symbol, self.name)
        try:
            return self._compute(symbol, df)
        except Exception as e:
            from utils.logger import get_logger
            get_logger(self.name).error("Error computing signal for %s: %s", symbol, e)
            return NO_SIGNAL(symbol, self.name)

    @abstractmethod
    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        """Core signal computation. Must be implemented by subclasses."""
        ...

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute Average True Range."""
        high = df["high"]
        low  = df["low"]
        close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - close).abs(),
            (low  - close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _compute_target_and_sl(
        direction: str,
        entry: float,
        atr: float,
        atr_sl_mult: float = 1.5,
        rr: float = 2.0,
    ):
        """Compute stop-loss and target from ATR."""
        sl_dist = atr * atr_sl_mult
        tgt_dist = sl_dist * rr
        if direction == "BUY":
            return entry - sl_dist, entry + tgt_dist
        else:
            return entry + sl_dist, entry - tgt_dist
