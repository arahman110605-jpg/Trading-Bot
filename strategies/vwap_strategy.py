"""
strategies/vwap_strategy.py — VWAP Mean Reversion / Momentum Strategy.

VWAP (Volume Weighted Average Price) resets each trading day.

BUY  signal: Price dips below VWAP by deviation% then bounces back above it
             (mean reversion — price snapping back)
SELL signal: Price rises above VWAP by deviation% then falls back below it

Only trade from 9:30 AM to 2:30 PM (avoid open/close volatility).
"""

from __future__ import annotations

import pandas as pd
from datetime import time as dtime

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL


class VWAPStrategy(BaseStrategy):
    name = "vwap"

    def __init__(
        self,
        deviation_pct: float = config.VWAP_DEVIATION_PCT,
        rr: float = config.REWARD_TO_RISK_RATIO,
    ):
        self.deviation_pct = deviation_pct
        self.rr = rr

    @staticmethod
    def _compute_vwap(df: pd.DataFrame) -> pd.Series:
        """Compute intraday cumulative VWAP (resets each day)."""
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        tp_vol = typical_price * df["volume"]

        vwap_values = []
        cum_tp_vol = 0.0
        cum_vol = 0.0

        for i, (idx, row) in enumerate(df.iterrows()):
            # Reset at start of each new day
            if i > 0:
                prev_date = df.index[i - 1].date()
                curr_date = idx.date()
                if curr_date != prev_date:
                    cum_tp_vol = 0.0
                    cum_vol = 0.0

            cum_tp_vol += tp_vol.iloc[i]
            cum_vol    += row["volume"]
            vwap_values.append(cum_tp_vol / cum_vol if cum_vol > 0 else typical_price.iloc[i])

        return pd.Series(vwap_values, index=df.index)

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        # Only signal during core trading hours
        now = df.index[-1]
        if hasattr(now, "time"):
            t = now.time()
            if t < dtime(9, 30) or t > dtime(14, 30):
                return NO_SIGNAL(symbol, self.name)

        vwap = self._compute_vwap(df)
        close = df["close"]
        atr   = self._atr(df)

        curr_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        curr_vwap  = vwap.iloc[-1]
        curr_atr   = atr.iloc[-1]
        deviation  = self.deviation_pct / 100

        # ── BUY: Price was below VWAP and crosses back above ──
        if (prev_close < curr_vwap * (1 - deviation)) and (curr_close > curr_vwap):
            sl, tgt = self._compute_target_and_sl("BUY", curr_close, curr_atr, rr=self.rr)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(curr_close, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.70,
                notes=f"Price bounced back above VWAP ({curr_vwap:.2f})",
            )

        # ── SELL: Price was above VWAP and crosses back below ──
        if (prev_close > curr_vwap * (1 + deviation)) and (curr_close < curr_vwap):
            sl, tgt = self._compute_target_and_sl("SELL", curr_close, curr_atr, rr=self.rr)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(curr_close, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.70,
                notes=f"Price fell back below VWAP ({curr_vwap:.2f})",
            )

        return NO_SIGNAL(symbol, self.name)
