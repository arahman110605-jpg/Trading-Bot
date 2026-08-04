"""
strategies/supertrend.py — Supertrend Trend-Following Strategy.

Supertrend is an ATR-based directional indicator.
When it flips from bearish (red) to bullish (green) → BUY
When it flips from bullish (green) to bearish (red) → SELL

SL is placed at the Supertrend band value (the natural support/resistance level).
Settings: ATR period=10, Multiplier=3 (configurable)
"""

import pandas as pd
import numpy as np

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL


class SupertrendStrategy(BaseStrategy):
    name = "supertrend"

    def __init__(
        self,
        atr_period:  int   = config.SUPERTREND_ATR_PERIOD,
        multiplier:  float = config.SUPERTREND_MULTIPLIER,
        rr:          float = config.REWARD_TO_RISK_RATIO,
    ):
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.rr         = rr

    def _compute_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute Supertrend indicator. Returns df with 'supertrend' and 'st_direction' columns."""
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        # ATR using Wilder smoothing (matches TradingView)
        atr = self._atr(df, self.atr_period)

        # Basic upper and lower bands
        hl2 = (high + low) / 2
        basic_upper = (hl2 + self.multiplier * atr).values.copy().astype(float)
        basic_lower = (hl2 - self.multiplier * atr).values.copy().astype(float)
        close_arr   = close.values.astype(float)

        final_upper = basic_upper.copy()
        final_lower = basic_lower.copy()
        supertrend  = np.full(len(df), np.nan)
        direction   = np.zeros(len(df), dtype=int)

        for i in range(1, len(df)):
            # Final Upper Band
            if basic_upper[i] < final_upper[i-1] or close_arr[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i-1]

            # Final Lower Band
            if basic_lower[i] > final_lower[i-1] or close_arr[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i-1]

            # Supertrend direction
            prev_st = supertrend[i-1] if i > 1 and not np.isnan(supertrend[i-1]) else final_upper[i]
            if prev_st == final_upper[i-1]:
                if close_arr[i] > final_upper[i]:
                    supertrend[i] = final_lower[i]
                    direction[i]  = 1
                else:
                    supertrend[i] = final_upper[i]
                    direction[i]  = -1
            else:
                if close_arr[i] < final_lower[i]:
                    supertrend[i] = final_upper[i]
                    direction[i]  = -1
                else:
                    supertrend[i] = final_lower[i]
                    direction[i]  = 1

        result = df.copy()
        result["supertrend"]   = supertrend
        result["st_direction"] = direction
        result["final_upper"]  = final_upper
        result["final_lower"]  = final_lower
        return result

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if len(df) < self.atr_period + 5:
            return NO_SIGNAL(symbol, self.name)

        st_df = self._compute_supertrend(df)
        entry = df["close"].iloc[-1]

        prev_dir = int(st_df["st_direction"].iloc[-2])
        curr_dir = int(st_df["st_direction"].iloc[-1])

        # ── BUY: Supertrend flipped bullish ──
        if prev_dir == -1 and curr_dir == 1:
            # SL = Supertrend lower band (natural support level)
            sl  = round(float(st_df["supertrend"].iloc[-1]), 2)
            sl  = min(sl, entry * 0.99)   # Safety: SL never above entry
            tgt = round(entry + (entry - sl) * self.rr, 2)
            st_val = round(float(st_df["supertrend"].iloc[-1]), 2)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=0.85,
                notes=f"Supertrend flipped BULLISH @ ST={st_val}",
            )

        # ── SELL: Supertrend flipped bearish ──
        if prev_dir == 1 and curr_dir == -1:
            # SL = Supertrend upper band (natural resistance level)
            sl  = round(float(st_df["supertrend"].iloc[-1]), 2)
            sl  = max(sl, entry * 1.01)   # Safety: SL never below entry
            tgt = round(entry - (sl - entry) * self.rr, 2)
            st_val = round(float(st_df["supertrend"].iloc[-1]), 2)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=0.85,
                notes=f"Supertrend flipped BEARISH @ ST={st_val}",
            )

        return NO_SIGNAL(symbol, self.name)
