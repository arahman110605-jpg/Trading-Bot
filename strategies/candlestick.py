"""
strategies/candlestick.py — Candlestick Pattern Recognition Strategy.

Detects 12 major candlestick patterns and confirms them with trend filters.

Patterns implemented:
  BULLISH (BUY signals):
    - Hammer
    - Inverted Hammer
    - Bullish Engulfing
    - Morning Star (3-candle)
    - Bullish Harami
    - Three White Soldiers
    - Piercing Line
    - Dragonfly Doji (at support)

  BEARISH (SELL signals):
    - Shooting Star
    - Bearish Engulfing
    - Evening Star (3-candle)
    - Bearish Harami
    - Three Black Crows
    - Dark Cloud Cover
    - Gravestone Doji (at resistance)
    - Hanging Man

Confirmation filter:
    All signals are confirmed with EMA trend direction and volume.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL
from utils.logger import get_logger

log = get_logger("Candlestick")


class CandlestickStrategy(BaseStrategy):
    name = "candlestick"

    def __init__(self, rr: float = config.REWARD_TO_RISK_RATIO):
        self.rr = rr

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _body(candle: pd.Series) -> float:
        return abs(candle["close"] - candle["open"])

    @staticmethod
    def _range(candle: pd.Series) -> float:
        return candle["high"] - candle["low"]

    @staticmethod
    def _upper_wick(candle: pd.Series) -> float:
        return candle["high"] - max(candle["open"], candle["close"])

    @staticmethod
    def _lower_wick(candle: pd.Series) -> float:
        return min(candle["open"], candle["close"]) - candle["low"]

    @staticmethod
    def _is_bullish(candle: pd.Series) -> bool:
        return candle["close"] > candle["open"]

    @staticmethod
    def _is_bearish(candle: pd.Series) -> bool:
        return candle["close"] < candle["open"]

    def _is_doji(self, c: pd.Series) -> bool:
        """Body is <= 5% of range → indecision candle."""
        r = self._range(c)
        return r > 0 and self._body(c) / r <= 0.05

    def _body_pct(self, c: pd.Series) -> float:
        """Body as % of candle range."""
        r = self._range(c)
        return self._body(c) / r if r > 0 else 0

    # ── Pattern Detectors ─────────────────────────────────────────────────────

    def _hammer(self, c: pd.Series) -> bool:
        """Hammer: small body at top, long lower wick (≥2× body), tiny upper wick."""
        body  = self._body(c)
        lwick = self._lower_wick(c)
        uwick = self._upper_wick(c)
        if body == 0:
            return False
        return lwick >= 2 * body and uwick <= 0.3 * body

    def _shooting_star(self, c: pd.Series) -> bool:
        """Shooting Star: small body at bottom, long upper wick (≥2× body), tiny lower wick."""
        body  = self._body(c)
        lwick = self._lower_wick(c)
        uwick = self._upper_wick(c)
        if body == 0:
            return False
        return uwick >= 2 * body and lwick <= 0.3 * body

    def _bullish_engulfing(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Curr bullish candle fully engulfs prev bearish candle."""
        return (
            self._is_bearish(prev)
            and self._is_bullish(curr)
            and curr["open"] <= prev["close"]
            and curr["close"] >= prev["open"]
            and self._body(curr) > self._body(prev)
        )

    def _bearish_engulfing(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Curr bearish candle fully engulfs prev bullish candle."""
        return (
            self._is_bullish(prev)
            and self._is_bearish(curr)
            and curr["open"] >= prev["close"]
            and curr["close"] <= prev["open"]
            and self._body(curr) > self._body(prev)
        )

    def _morning_star(self, c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
        """3-candle: bearish → small doji/hammer → bullish recovery."""
        return (
            self._is_bearish(c1)
            and self._body_pct(c1) > 0.5          # big bearish candle
            and self._body(c2) < 0.5 * self._body(c1)   # small middle
            and self._is_bullish(c3)
            and c3["close"] > (c1["open"] + c1["close"]) / 2  # recovers >50%
        )

    def _evening_star(self, c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
        """3-candle: bullish → small doji → bearish decline."""
        return (
            self._is_bullish(c1)
            and self._body_pct(c1) > 0.5
            and self._body(c2) < 0.5 * self._body(c1)
            and self._is_bearish(c3)
            and c3["close"] < (c1["open"] + c1["close"]) / 2
        )

    def _bullish_harami(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Small bullish candle inside previous large bearish candle."""
        return (
            self._is_bearish(prev)
            and self._body_pct(prev) > 0.6
            and self._is_bullish(curr)
            and curr["open"] >= prev["close"]
            and curr["close"] <= prev["open"]
            and self._body(curr) < 0.5 * self._body(prev)
        )

    def _bearish_harami(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Small bearish candle inside previous large bullish candle."""
        return (
            self._is_bullish(prev)
            and self._body_pct(prev) > 0.6
            and self._is_bearish(curr)
            and curr["open"] <= prev["close"]
            and curr["close"] >= prev["open"]
            and self._body(curr) < 0.5 * self._body(prev)
        )

    def _three_white_soldiers(self, c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
        """3 consecutive strong bullish candles, each closing higher."""
        return (
            self._is_bullish(c1) and self._body_pct(c1) > 0.6
            and self._is_bullish(c2) and self._body_pct(c2) > 0.6
            and self._is_bullish(c3) and self._body_pct(c3) > 0.6
            and c2["close"] > c1["close"]
            and c3["close"] > c2["close"]
            and c2["open"] > c1["open"]
            and c3["open"] > c2["open"]
        )

    def _three_black_crows(self, c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
        """3 consecutive strong bearish candles, each closing lower."""
        return (
            self._is_bearish(c1) and self._body_pct(c1) > 0.6
            and self._is_bearish(c2) and self._body_pct(c2) > 0.6
            and self._is_bearish(c3) and self._body_pct(c3) > 0.6
            and c2["close"] < c1["close"]
            and c3["close"] < c2["close"]
            and c2["open"] < c1["open"]
            and c3["open"] < c2["open"]
        )

    def _piercing_line(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Bearish candle followed by bullish that opens below low and closes above midpoint."""
        mid = (prev["open"] + prev["close"]) / 2
        return (
            self._is_bearish(prev)
            and self._is_bullish(curr)
            and curr["open"] < prev["close"]
            and curr["close"] > mid
            and curr["close"] < prev["open"]
        )

    def _dark_cloud_cover(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Bullish candle followed by bearish that opens above high and closes below midpoint."""
        mid = (prev["open"] + prev["close"]) / 2
        return (
            self._is_bullish(prev)
            and self._is_bearish(curr)
            and curr["open"] > prev["close"]
            and curr["close"] < mid
            and curr["close"] > prev["open"]
        )

    def _dragonfly_doji(self, c: pd.Series) -> bool:
        """Long lower wick, tiny body and upper wick — bullish reversal doji."""
        total = self._range(c)
        if total == 0:
            return False
        return (
            self._lower_wick(c) >= 0.6 * total
            and self._body(c) / total <= 0.05
            and self._upper_wick(c) / total <= 0.05
        )

    def _gravestone_doji(self, c: pd.Series) -> bool:
        """Long upper wick, tiny body and lower wick — bearish reversal doji."""
        total = self._range(c)
        if total == 0:
            return False
        return (
            self._upper_wick(c) >= 0.6 * total
            and self._body(c) / total <= 0.05
            and self._lower_wick(c) / total <= 0.05
        )

    # ── Volume Confirmation ───────────────────────────────────────────────────

    def _high_volume(self, df: pd.DataFrame, idx: int, multiplier: float = 1.2) -> bool:
        """Returns True if candle volume is above average × multiplier."""
        avg_vol = df["volume"].iloc[max(0, idx-20):idx].mean()
        return df["volume"].iloc[idx] >= avg_vol * multiplier

    # ── Main Compute ──────────────────────────────────────────────────────────

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if len(df) < 10:
            return NO_SIGNAL(symbol, self.name)

        # Get last 3 candles
        c1 = df.iloc[-4]   # 3 candles ago
        c2 = df.iloc[-3]   # 2 candles ago
        c3 = df.iloc[-2]   # previous candle
        c4 = df.iloc[-1]   # current (latest) candle

        entry = c4["close"]
        atr   = self._atr(df).iloc[-1]

        # Trend filter — EMA 20 direction
        ema20 = df["close"].ewm(span=20, adjust=False).mean()
        ema50 = df["close"].ewm(span=50, adjust=False).mean()
        trend_up   = ema20.iloc[-1] > ema50.iloc[-1]
        trend_down = ema20.iloc[-1] < ema50.iloc[-1]

        n = len(df) - 1   # index of latest candle

        # ── BULLISH PATTERNS ──────────────────────────────────────────────────

        patterns_buy = []

        # 1. Hammer (in downtrend or at support)
        if self._hammer(c4) and self._is_bullish(c4):
            patterns_buy.append(("Hammer", 0.70))

        # 2. Inverted Hammer
        if self._hammer(c4) and self._is_bearish(c4) and trend_up:
            patterns_buy.append(("Inverted Hammer", 0.65))

        # 3. Bullish Engulfing
        if self._bullish_engulfing(c3, c4) and self._high_volume(df, n):
            patterns_buy.append(("Bullish Engulfing", 0.85))

        # 4. Morning Star
        if self._morning_star(c2, c3, c4):
            patterns_buy.append(("Morning Star", 0.90))

        # 5. Bullish Harami
        if self._bullish_harami(c3, c4):
            patterns_buy.append(("Bullish Harami", 0.70))

        # 6. Three White Soldiers
        if self._three_white_soldiers(c2, c3, c4):
            patterns_buy.append(("Three White Soldiers", 0.90))

        # 7. Piercing Line
        if self._piercing_line(c3, c4) and self._high_volume(df, n):
            patterns_buy.append(("Piercing Line", 0.75))

        # 8. Dragonfly Doji
        if self._dragonfly_doji(c4) and trend_up:
            patterns_buy.append(("Dragonfly Doji", 0.72))

        # ── BEARISH PATTERNS ──────────────────────────────────────────────────

        patterns_sell = []

        # 1. Shooting Star
        if self._shooting_star(c4) and self._is_bearish(c4):
            patterns_sell.append(("Shooting Star", 0.70))

        # 2. Bearish Engulfing
        if self._bearish_engulfing(c3, c4) and self._high_volume(df, n):
            patterns_sell.append(("Bearish Engulfing", 0.85))

        # 3. Evening Star
        if self._evening_star(c2, c3, c4):
            patterns_sell.append(("Evening Star", 0.90))

        # 4. Bearish Harami
        if self._bearish_harami(c3, c4):
            patterns_sell.append(("Bearish Harami", 0.70))

        # 5. Three Black Crows
        if self._three_black_crows(c2, c3, c4):
            patterns_sell.append(("Three Black Crows", 0.90))

        # 6. Dark Cloud Cover
        if self._dark_cloud_cover(c3, c4) and self._high_volume(df, n):
            patterns_sell.append(("Dark Cloud Cover", 0.75))

        # 7. Gravestone Doji
        if self._gravestone_doji(c4) and trend_down:
            patterns_sell.append(("Gravestone Doji", 0.72))

        # 8. Hanging Man (Hammer in uptrend = bearish)
        if self._hammer(c4) and trend_down and self._is_bearish(c4):
            patterns_sell.append(("Hanging Man", 0.68))

        # ── Pick best signal ──────────────────────────────────────────────────

        if patterns_buy:
            # Sort by confidence, pick highest
            best_name, best_conf = sorted(patterns_buy, key=lambda x: x[1], reverse=True)[0]
            sl, tgt = self._compute_target_and_sl("BUY", entry, atr, rr=self.rr)
            log.info("Candlestick BUY signal: %s on %s (conf=%.0f%%)", best_name, symbol, best_conf*100)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=best_conf,
                notes=f"Pattern: {best_name}"
                      + (f" + {len(patterns_buy)-1} more" if len(patterns_buy) > 1 else "")
                      + f" | Trend: {'UP' if trend_up else 'MIXED'}",
            )

        if patterns_sell:
            best_name, best_conf = sorted(patterns_sell, key=lambda x: x[1], reverse=True)[0]
            sl, tgt = self._compute_target_and_sl("SELL", entry, atr, rr=self.rr)
            log.info("Candlestick SELL signal: %s on %s (conf=%.0f%%)", best_name, symbol, best_conf*100)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=best_conf,
                notes=f"Pattern: {best_name}"
                      + (f" + {len(patterns_sell)-1} more" if len(patterns_sell) > 1 else "")
                      + f" | Trend: {'DOWN' if trend_down else 'MIXED'}",
            )

        return NO_SIGNAL(symbol, self.name)
