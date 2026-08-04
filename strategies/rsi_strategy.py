"""
strategies/rsi_strategy.py — RSI Mean Reversion Strategy.

BUY  signal: RSI crosses above oversold (30) from below + price above 20-EMA trend
SELL signal: RSI crosses below overbought (70) from above + price below 20-EMA trend

Ensures we trade WITH the bigger trend using a 50-EMA filter.
"""

import pandas as pd

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL


class RSIStrategy(BaseStrategy):
    name = "rsi"

    def __init__(
        self,
        rsi_period:  int   = config.RSI_PERIOD,
        oversold:    int   = config.RSI_OVERSOLD,
        overbought:  int   = config.RSI_OVERBOUGHT,
        rr:          float = config.REWARD_TO_RISK_RATIO,
    ):
        self.rsi_period  = rsi_period
        self.oversold    = oversold
        self.overbought  = overbought
        self.rr          = rr

    def _compute_rsi(self, close: pd.Series) -> pd.Series:
        """Wilder-smoothed RSI matching TradingView reference."""
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/self.rsi_period, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs    = gain / loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if len(df) < 60:   # Need 60 bars for reliable EMA50
            return NO_SIGNAL(symbol, self.name)

        close = df["close"]

        rsi  = self._compute_rsi(close)
        ema50 = close.ewm(span=50, adjust=False).mean()

        # Volume filter
        vol_avg = df["volume"].rolling(20).mean()
        vol_ok  = df["volume"].iloc[-1] >= vol_avg.iloc[-1] * config.VOLUME_FILTER_MULT

        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]
        entry    = close.iloc[-1]
        e50      = ema50.iloc[-1]
        atr      = self._atr(df).iloc[-1]

        # ── BUY: RSI exits oversold with a buffer, price above EMA50 (uptrend), volume spike ──
        if (prev_rsi < self.oversold) and (curr_rsi >= self.oversold + 2) and (entry > e50) and vol_ok:
            sl, tgt = self._compute_target_and_sl("BUY", entry, atr, rr=self.rr)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.80,
                notes=f"RSI bounced from oversold ({prev_rsi:.1f}>{curr_rsi:.1f}) | Uptrend (price > EMA50)",
            )

        # ── SELL: RSI exits overbought with a buffer, price below EMA50 (downtrend), volume spike ──
        if (prev_rsi > self.overbought) and (curr_rsi <= self.overbought - 2) and (entry < e50) and vol_ok:
            sl, tgt = self._compute_target_and_sl("SELL", entry, atr, rr=self.rr)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                confidence=0.80,
                notes=f"RSI dropped from overbought ({prev_rsi:.1f}<{curr_rsi:.1f}) | Downtrend (price < EMA50)",
            )

        return NO_SIGNAL(symbol, self.name)
