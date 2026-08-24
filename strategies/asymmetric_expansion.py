"""
strategies/asymmetric_expansion.py — Multi-Timeframe Asymmetric Trend-Expansion Strategy.

Implements the institutional confluence and trend-expansion engine:
1. Macro Regime (H1): 200 EMA & 50 EMA Slope direction
2. Market Structure (M15): 20 EMA & 50 EMA dynamic support/resistance
3. Execution Flow (M5): 20 EMA momentum crossover + 200 EMA trend filter + Volume expansion
4. Dynamic Thesis Score (0–100 Rating) for active lifecycle management.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional

import config
from strategies.base_strategy import BaseStrategy, Signal, NO_SIGNAL
from utils.logger import get_logger

log = get_logger("AsymmetricExpansion")


class AsymmetricTrendExpansionStrategy(BaseStrategy):
    """
    Multi-timeframe trend-expansion strategy with dynamic thesis scoring.
    """
    name = "asymmetric_expansion"

    def __init__(self, rr: float = getattr(config, "REWARD_TO_RISK_RATIO", 2.0)):
        self.rr = rr

    # ── Multi-Timeframe Resampling ──────────────────────────────────────────

    @staticmethod
    def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        Resample a 5-minute OHLCV DataFrame into higher timeframes (e.g. '15min', '60min').
        """
        if df.empty:
            return pd.DataFrame()

        df_copy = df.copy()
        if not isinstance(df_copy.index, pd.DatetimeIndex):
            if "date" in df_copy.columns:
                df_copy["date"] = pd.to_datetime(df_copy["date"])
                df_copy.set_index("date", inplace=True)
            elif "time" in df_copy.columns:
                df_copy["time"] = pd.to_datetime(df_copy["time"])
                df_copy.set_index("time", inplace=True)
            else:
                # If no timestamp column, create synthetic datetime index
                df_copy.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df_copy), freq="5min")

        resampled = df_copy.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        return resampled

    @staticmethod
    def compute_indicators(df_m5: pd.DataFrame, df_m15: pd.DataFrame, df_h1: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Compute indicators across M5, M15, and H1 timeframes.
        """
        # M5 Indicators
        m5 = df_m5.copy()
        m5["ema20"] = m5["close"].ewm(span=20, adjust=False).mean()
        m5["ema50"] = m5["close"].ewm(span=50, adjust=False).mean()
        m5["ema200"] = m5["close"].ewm(span=200, adjust=False).mean()
        m5["ema20_slope"] = m5["ema20"].diff(2) / 2.0
        
        # ATR14
        high = m5["high"]
        low = m5["low"]
        close_prev = m5["close"].shift(1)
        tr = pd.concat([high - low, (high - close_prev).abs(), (low - close_prev).abs()], axis=1).max(axis=1)
        m5["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()

        # RSI14
        delta = m5["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, float("nan"))
        m5["rsi14"] = 100 - (100 / (1 + rs))

        # Volume Ratio
        m5["vol_sma"] = m5["volume"].rolling(20).mean()
        m5["vol_ratio"] = m5["volume"] / m5["vol_sma"].replace(0, 1)

        # 3-bar Swing Extremes
        m5["swing_low"] = m5["low"].rolling(3).min()
        m5["swing_high"] = m5["high"].rolling(3).max()

        # M15 Indicators
        m15 = df_m15.copy()
        m15["ema20"] = m15["close"].ewm(span=20, adjust=False).mean()
        m15["ema50"] = m15["close"].ewm(span=50, adjust=False).mean()

        # H1 Indicators
        h1 = df_h1.copy()
        h1["ema50"] = h1["close"].ewm(span=50, adjust=False).mean()
        h1["ema200"] = h1["close"].ewm(span=200, adjust=False).mean()
        h1["ema50_slope"] = h1["ema50"].diff(3) / 3.0

        return m5, m15, h1

    @classmethod
    def evaluate_thesis_score(cls, direction: str, row_m5: pd.Series, row_m15: pd.Series, row_h1: pd.Series) -> float:
        """
        Evaluate real-time composite Thesis Score (0–100) on closed bars:
        - H1 Macro Regime: 40 pts
        - M15 Structural Support: 20 pts
        - M5 Momentum & Slope: 20 pts
        - RSI & Volume: 20 pts
        """
        score = 0.0
        if direction == "BUY":
            # H1 Macro (40 pts)
            if row_h1.get("close", 0) > row_h1.get("ema200", 0): score += 15.0
            if row_h1.get("close", 0) > row_h1.get("ema50", 0): score += 10.0
            if row_h1.get("ema50_slope", 0) > 0: score += 15.0

            # M15 Structure (20 pts)
            if row_m15.get("close", 0) > row_m15.get("ema20", 0): score += 10.0
            if row_m15.get("close", 0) > row_m15.get("ema50", 0): score += 10.0

            # M5 Momentum (20 pts)
            if row_m5.get("close", 0) > row_m5.get("ema20", 0): score += 10.0
            if row_m5.get("ema20_slope", 0) > 0: score += 10.0

            # RSI & Vol (20 pts)
            rsi = row_m5.get("rsi14", 50)
            if 45 <= rsi <= 75: score += 10.0
            if row_m5.get("vol_ratio", 1.0) >= 1.0: score += 10.0

        else: # SELL
            # H1 Macro (40 pts)
            if row_h1.get("close", 0) < row_h1.get("ema200", 0): score += 15.0
            if row_h1.get("close", 0) < row_h1.get("ema50", 0): score += 10.0
            if row_h1.get("ema50_slope", 0) < 0: score += 15.0

            # M15 Structure (20 pts)
            if row_m15.get("close", 0) < row_m15.get("ema20", 0): score += 10.0
            if row_m15.get("close", 0) < row_m15.get("ema50", 0): score += 10.0

            # M5 Momentum (20 pts)
            if row_m5.get("close", 0) < row_m5.get("ema20", 0): score += 10.0
            if row_m5.get("ema20_slope", 0) < 0: score += 10.0

            # RSI & Vol (20 pts)
            rsi = row_m5.get("rsi14", 50)
            if 25 <= rsi <= 55: score += 10.0
            if row_m5.get("vol_ratio", 1.0) >= 1.0: score += 10.0

        return max(0.0, min(100.0, score))

    def _compute(self, symbol: str, df: pd.DataFrame) -> Signal:
        if len(df) < 50:
            return NO_SIGNAL(symbol, self.name)

        # Generate M15 and H1 resampled data
        df_m15 = self.resample_ohlcv(df, "15min")
        df_h1 = self.resample_ohlcv(df, "60min")

        if len(df_m15) < 10 or len(df_h1) < 5:
            # Fallback when dataset is short: use EMA approximations on M5
            df_m15 = df.copy()
            df_h1 = df.copy()

        m5, m15, h1 = self.compute_indicators(df, df_m15, df_h1)

        row_m5 = m5.iloc[-1]
        prev_m5 = m5.iloc[-2]
        row_m15 = m15.iloc[-1]
        row_h1 = h1.iloc[-1]

        entry = row_m5["close"]
        atr = row_m5["atr14"] if not np.isnan(row_m5["atr14"]) and row_m5["atr14"] > 0 else (entry * 0.01)

        # Minimum R distance: 1.5 * ATR (minimum 0.4% of price)
        r_distance = max(atr * 1.5, entry * 0.004)
        target_distance = r_distance * 3.0  # Initial 1:3 R:R

        # ── 1. BUY TRIPLE-CONFLUENCE ──
        # M5 Momentum Cross + M5 Above 200 EMA + M15 Bullish + H1 Bullish
        buy_m5 = (row_m5["close"] > row_m5["ema200"]) and (row_m5["close"] > row_m5["ema20"]) and (prev_m5["close"] <= prev_m5["ema20"])
        buy_m15 = row_m15["close"] > row_m15["ema20"]
        buy_h1 = (row_h1["close"] > row_h1["ema200"]) and (row_h1.get("ema50_slope", 1) >= 0)

        if buy_m5 and buy_m15 and buy_h1:
            thesis = self.evaluate_thesis_score("BUY", row_m5, row_m15, row_h1)
            sl = round(entry - r_distance, 2)
            tgt = round(entry + target_distance, 2)
            log.info("[CONFLUENCE BUY] %s @ %.2f | SL=%.2f | TGT=%.2f | Thesis=%.0f",
                     symbol, entry, sl, tgt, thesis)
            return Signal(
                symbol=symbol,
                direction="BUY",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=min(1.0, thesis / 100.0),
                notes=f"Asymmetric Trend-Expansion BUY | Thesis={thesis:.0f} | Triple-Confluence (M5+M15+H1)",
            )

        # ── 2. SELL TRIPLE-CONFLUENCE ──
        sell_m5 = (row_m5["close"] < row_m5["ema200"]) and (row_m5["close"] < row_m5["ema20"]) and (prev_m5["close"] >= prev_m5["ema20"])
        sell_m15 = row_m15["close"] < row_m15["ema20"]
        sell_h1 = (row_h1["close"] < row_h1["ema200"]) and (row_h1.get("ema50_slope", -1) <= 0)

        if sell_m5 and sell_m15 and sell_h1:
            thesis = self.evaluate_thesis_score("SELL", row_m5, row_m15, row_h1)
            sl = round(entry + r_distance, 2)
            tgt = round(entry - target_distance, 2)
            log.info("[CONFLUENCE SELL] %s @ %.2f | SL=%.2f | TGT=%.2f | Thesis=%.0f",
                     symbol, entry, sl, tgt, thesis)
            return Signal(
                symbol=symbol,
                direction="SELL",
                strategy=self.name,
                entry_price=round(entry, 2),
                stop_loss=sl,
                target=tgt,
                confidence=min(1.0, thesis / 100.0),
                notes=f"Asymmetric Trend-Expansion SELL | Thesis={thesis:.0f} | Triple-Confluence (M5+M15+H1)",
            )

        return NO_SIGNAL(symbol, self.name)
