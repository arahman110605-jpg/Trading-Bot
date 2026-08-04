"""
strategies/ema_crossover.py — EMA 9/21 Golden/Death Cross Strategy.

BUY  signal: EMA(9) crosses ABOVE EMA(21) + price above EMA(21)
SELL signal: EMA(9) crosses BELOW EMA(21) + price below EMA(21)

Filter: RSI must be between 40-65 (avoid extreme conditions)
"""

import pandas as pd

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL


class EMACrossoverStrategy(BaseStrategy):
    name = "ema_crossover"

    def __init__(
        self,
        fast: int = config.EMA_FAST,
        slow: int = config.EMA_SLOW,
        rr: float = config.REWARD_TO_RISK_RATIO,
    ):
        self.fast = fast
        self.slow = slow
        self.rr   = rr

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        close = df["close"]

        # Calculate EMAs
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()

        # RSI filter
        delta  = close.diff()
        gain   = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
        loss   = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
        rs     = gain / loss.replace(0, float("nan"))
        rsi    = 100 - (100 / (1 + rs))

        # Latest and previous values
        prev_fast = ema_fast.iloc[-2]
        prev_slow = ema_slow.iloc[-2]
        curr_fast = ema_fast.iloc[-1]
        curr_slow = ema_slow.iloc[-1]
        curr_rsi  = rsi.iloc[-1]
        entry     = close.iloc[-1]

        # ATR for SL/Target
        atr = self._atr(df).iloc[-1]

        # ── BUY: Golden Cross ──
        if (prev_fast < prev_slow) and (curr_fast > curr_slow):
            if 40 < curr_rsi < 70:  # Avoid overbought
                sl, tgt = self._compute_target_and_sl("BUY", entry, atr, rr=self.rr)
                return Signal(
                    symbol=symbol,
                    direction="BUY",
                    strategy=self.name,
                    entry_price=round(entry, 2),
                    stop_loss=round(sl, 2),
                    target=round(tgt, 2),
                    confidence=0.75,
                    notes=f"EMA{self.fast} crossed above EMA{self.slow} | RSI={curr_rsi:.1f}",
                )

        # ── SELL: Death Cross ──
        if (prev_fast > prev_slow) and (curr_fast < curr_slow):
            if 30 < curr_rsi < 60:  # Avoid oversold
                sl, tgt = self._compute_target_and_sl("SELL", entry, atr, rr=self.rr)
                return Signal(
                    symbol=symbol,
                    direction="SELL",
                    strategy=self.name,
                    entry_price=round(entry, 2),
                    stop_loss=round(sl, 2),
                    target=round(tgt, 2),
                    confidence=0.75,
                    notes=f"EMA{self.fast} crossed below EMA{self.slow} | RSI={curr_rsi:.1f}",
                )

        return NO_SIGNAL(symbol, self.name)
