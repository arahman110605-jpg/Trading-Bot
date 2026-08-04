"""
strategies/orb_strategy.py — Opening Range Breakout (ORB) Strategy.

One of the highest win-rate NSE intraday strategies.

Rules:
  - Define the Opening Range as the High and Low of the first N minutes (default: 15 min)
    i.e. 09:15 to 09:30 AM
  - BUY  when price breaks ABOVE the Opening High with high volume
  - SELL when price breaks BELOW the Opening Low  with high volume
  - Active only during: 09:30 AM – 12:00 PM (morning momentum window)

Win Rate: ~60–70% on trending days (ADX > 25)
"""

from __future__ import annotations

from datetime import time as dtime

import pandas as pd

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL


class ORBStrategy(BaseStrategy):
    name = "orb"

    def __init__(
        self,
        orb_minutes: int   = config.ORB_MINUTES,
        rr:          float = config.REWARD_TO_RISK_RATIO,
    ):
        self.orb_minutes = orb_minutes
        self.rr          = rr

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if df is None or len(df) < 10:
            return NO_SIGNAL(symbol, self.name)

        # Only active during morning momentum window: 09:30 AM – 12:00 PM
        if hasattr(df.index, "time"):
            last_time = df.index[-1].time()
            orb_end   = dtime(9, 15 + self.orb_minutes)   # e.g. 09:30 after 15 min ORB
            trade_end = dtime(12, 0)
            if not (orb_end <= last_time <= trade_end):
                return NO_SIGNAL(symbol, self.name)

        # Extract Opening Range candles (first N minutes after 09:15)
        try:
            today = df.index[-1].date()
            today_df = df[df.index.date == today]
        except AttributeError:
            # Fallback: use first orb_minutes worth of candles from the data
            today_df = df

        # Number of 5-min candles in the ORB window
        candles_in_orb = self.orb_minutes // 5
        if len(today_df) < candles_in_orb + 1:
            return NO_SIGNAL(symbol, self.name)

        orb_candles = today_df.iloc[:candles_in_orb]
        orb_high    = float(orb_candles["high"].max())
        orb_low     = float(orb_candles["low"].min())
        orb_range   = orb_high - orb_low

        # Minimum range filter: ORB range must be meaningful (at least 0.2% of price)
        entry = float(df["close"].iloc[-1])
        if orb_range < entry * 0.002:
            return NO_SIGNAL(symbol, self.name)

        # Volume filter: breakout candle volume must be above average
        vol_avg = df["volume"].rolling(20).mean().iloc[-1]
        vol_ok  = df["volume"].iloc[-1] >= vol_avg * config.VOLUME_FILTER_MULT

        curr_close = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2])
        atr        = self._atr(df).iloc[-1]

        # ── BUY: Price breaks ABOVE opening range high ──
        if prev_close <= orb_high and curr_close > orb_high and vol_ok:
            sl  = round(orb_low, 2)                            # SL at bottom of ORB
            sl  = min(sl, entry - atr * 0.5)                   # At least 0.5 ATR below entry
            tgt = round(entry + (entry - sl) * self.rr, 2)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=0.82,
                notes=f"ORB Breakout UP | Range={orb_low:.2f}-{orb_high:.2f} | Broke {orb_high:.2f}",
            )

        # ── SELL: Price breaks BELOW opening range low ──
        if prev_close >= orb_low and curr_close < orb_low and vol_ok:
            sl  = round(orb_high, 2)                           # SL at top of ORB
            sl  = max(sl, entry + atr * 0.5)                   # At least 0.5 ATR above entry
            tgt = round(entry - (sl - entry) * self.rr, 2)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=0.82,
                notes=f"ORB Breakdown DOWN | Range={orb_low:.2f}-{orb_high:.2f} | Broke {orb_low:.2f}",
            )

        return NO_SIGNAL(symbol, self.name)
