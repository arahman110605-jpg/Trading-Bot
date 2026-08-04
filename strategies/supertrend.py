"""
strategies/supertrend.py — Supertrend Trend-Following Strategy.

Supertrend is an ATR-based directional indicator.
When it flips from bearish (red) to bullish (green) → BUY
When it flips from bullish (green) to bearish (red) → SELL

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
        """Compute Supertrend indicator. Returns df with 'supertrend' and 'direction' columns."""
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        # ATR
        atr = self._atr(df, self.atr_period)

        # Basic upper and lower bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + (self.multiplier * atr)
        basic_lower = hl2 - (self.multiplier * atr)

        final_upper = basic_upper.copy()
        final_lower = basic_lower.copy()
        supertrend  = pd.Series(index=df.index, dtype=float)
        direction   = pd.Series(index=df.index, dtype=int)  # 1=up (buy), -1=down (sell)

        for i in range(1, len(df)):
            # Final Upper Band
            if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]

            # Final Lower Band
            if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]

            # Supertrend direction
            prev_st = supertrend.iloc[i-1] if i > 1 else final_upper.iloc[i]
            if prev_st == final_upper.iloc[i-1]:
                if close.iloc[i] > final_upper.iloc[i]:
                    supertrend.iloc[i] = final_lower.iloc[i]
                    direction.iloc[i]  = 1
                else:
                    supertrend.iloc[i] = final_upper.iloc[i]
                    direction.iloc[i]  = -1
            else:
                if close.iloc[i] < final_lower.iloc[i]:
                    supertrend.iloc[i] = final_upper.iloc[i]
                    direction.iloc[i]  = -1
                else:
                    supertrend.iloc[i] = final_lower.iloc[i]
                    direction.iloc[i]  = 1

        result = df.copy()
        result["supertrend"] = supertrend
        result["st_direction"] = direction
        return result

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if len(df) < self.atr_period + 5:
            return NO_SIGNAL(symbol, self.name)

        st_df = self._compute_supertrend(df)
        atr   = self._atr(df).iloc[-1]

        prev_dir = st_df["st_direction"].iloc[-2]
        curr_dir = st_df["st_direction"].iloc[-1]
        entry    = df["close"].iloc[-1]

        # ── BUY: Supertrend flipped bullish ──
        if prev_dir == -1 and curr_dir == 1:
            sl, tgt = self._compute_target_and_sl("BUY", entry, atr, rr=self.rr)
            st_val  = round(st_df["supertrend"].iloc[-1], 2)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.85,
                notes=f"Supertrend flipped BULLISH @ {st_val}",
            )

        # ── SELL: Supertrend flipped bearish ──
        if prev_dir == 1 and curr_dir == -1:
            sl, tgt = self._compute_target_and_sl("SELL", entry, atr, rr=self.rr)
            st_val  = round(st_df["supertrend"].iloc[-1], 2)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.85,
                notes=f"Supertrend flipped BEARISH @ {st_val}",
            )

        return NO_SIGNAL(symbol, self.name)
