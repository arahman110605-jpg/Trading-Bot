"""
data/demo_feed.py — Simulated live market data for demo/testing mode.

Generates realistic OHLCV candles for NSE stocks using:
- Real approximate prices for each stock
- Realistic intraday price movements (random walk with drift)
- Occasional strong trends to trigger strategy signals
- Candles delivered every 30 seconds (sped up from real 5-min candles)
"""

from __future__ import annotations

import random
import math
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from utils.logger import get_logger

log = get_logger("DemoFeed")

# ── Realistic NSE stock base prices (approximate) ─────────────────────────────
DEMO_BASE_PRICES: Dict[str, float] = {
    "RELIANCE":   2950.0,
    "TCS":        3900.0,
    "HDFCBANK":   1720.0,
    "INFY":       1580.0,
    "ICICIBANK":   920.0,
    "SBIN":        820.0,
    "AXISBANK":   1180.0,
    "WIPRO":       560.0,
    "TATAMOTORS":  970.0,
    "BAJFINANCE": 7200.0,
    # Fallback
    "DEFAULT":    1000.0,
}

# Volatility (% per candle) for each stock
VOLATILITY: Dict[str, float] = {
    "RELIANCE":   0.003,
    "TCS":        0.0025,
    "HDFCBANK":   0.003,
    "INFY":       0.003,
    "ICICIBANK":  0.004,
    "SBIN":       0.005,
    "AXISBANK":   0.004,
    "WIPRO":      0.004,
    "TATAMOTORS": 0.006,
    "BAJFINANCE": 0.005,
    "DEFAULT":    0.004,
}


class DemoMarket:
    """
    Simulates a live intraday market for demo purposes.
    Generates OHLCV DataFrames on demand, advancing price on each call.
    """

    def __init__(self, symbols: List[str], candle_interval_sec: int = 30):
        self.symbols           = symbols
        self.candle_secs       = candle_interval_sec
        self._prices: Dict[str, float] = {}
        self._histories: Dict[str, List[dict]] = {}
        self._trends: Dict[str, float] = {}   # drift per candle
        self._trend_countdown: Dict[str, int] = {}
        self._lock = threading.Lock()

        self._init_histories()
        log.info("DemoMarket initialised | %d symbols | candle every %ds",
                 len(symbols), candle_interval_sec)

    def _init_histories(self):
        """Generate 100 historical candles per symbol to seed indicators."""
        base_time = datetime.now() - timedelta(minutes=100 * 5)  # 5-min candles

        for symbol in self.symbols:
            base  = DEMO_BASE_PRICES.get(symbol, DEMO_BASE_PRICES["DEFAULT"])
            vol   = VOLATILITY.get(symbol, VOLATILITY["DEFAULT"])
            price = base * random.uniform(0.97, 1.03)  # slight randomness

            candles = []
            for i in range(100):
                candle_time = base_time + timedelta(minutes=i * 5)

                # Random drift that occasionally forms trends
                drift = random.gauss(0, vol)
                open_p = price
                close_p = open_p * (1 + drift)
                high_p  = max(open_p, close_p) * (1 + abs(random.gauss(0, vol * 0.5)))
                low_p   = min(open_p, close_p) * (1 - abs(random.gauss(0, vol * 0.5)))
                volume  = int(random.uniform(50_000, 5_00_000))

                candles.append({
                    "date":   candle_time,
                    "open":   round(open_p, 2),
                    "high":   round(high_p, 2),
                    "low":    round(low_p, 2),
                    "close":  round(close_p, 2),
                    "volume": volume,
                })
                price = close_p

            self._prices[symbol]          = price
            self._histories[symbol]       = candles
            self._trends[symbol]          = 0.0
            self._trend_countdown[symbol] = 0

    def _next_candle(self, symbol: str) -> dict:
        """Generate the next live candle for a symbol."""
        price = self._prices[symbol]
        vol   = VOLATILITY.get(symbol, VOLATILITY["DEFAULT"])

        # Manage trend: occasionally start a strong uptrend or downtrend
        if self._trend_countdown[symbol] <= 0:
            # Start new trend or go flat
            r = random.random()
            if r < 0.15:    # 15% chance of strong uptrend
                self._trends[symbol]          = vol * 1.5
                self._trend_countdown[symbol] = random.randint(5, 12)
                log.debug("Demo: %s starting UPTREND", symbol)
            elif r < 0.30:  # 15% chance of downtrend
                self._trends[symbol]          = -vol * 1.5
                self._trend_countdown[symbol] = random.randint(5, 12)
                log.debug("Demo: %s starting DOWNTREND", symbol)
            else:
                self._trends[symbol]          = 0.0
                self._trend_countdown[symbol] = random.randint(3, 8)
        else:
            self._trend_countdown[symbol] -= 1

        drift   = self._trends[symbol] + random.gauss(0, vol * 0.6)
        open_p  = price
        close_p = open_p * (1 + drift)
        high_p  = max(open_p, close_p) * (1 + abs(random.gauss(0, vol * 0.3)))
        low_p   = min(open_p, close_p) * (1 - abs(random.gauss(0, vol * 0.3)))

        # Don't let price go below 10% of base
        base  = DEMO_BASE_PRICES.get(symbol, DEMO_BASE_PRICES["DEFAULT"])
        close_p = max(close_p, base * 0.7)

        volume = int(random.uniform(80_000, 8_00_000))

        self._prices[symbol] = close_p

        return {
            "date":   datetime.now(),
            "open":   round(open_p, 2),
            "high":   round(high_p, 2),
            "low":    round(low_p, 2),
            "close":  round(close_p, 2),
            "volume": volume,
        }

    def get_historical_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """Return current OHLCV history for a symbol (adds a new candle each call)."""
        with self._lock:
            # Add a new live candle
            new_candle = self._next_candle(symbol)
            self._histories[symbol].append(new_candle)
            # Keep last 120 candles
            history = self._histories[symbol][-120:]

        df = pd.DataFrame(history)
        df.set_index("date", inplace=True)
        df.index = pd.to_datetime(df.index)
        return df

    def get_ltp(self, symbol: str, **kwargs) -> float:
        """Return the latest simulated price."""
        with self._lock:
            return round(self._prices.get(symbol, 1000.0), 2)

    def get_quote(self, symbol: str, **kwargs) -> dict:
        ltp = self.get_ltp(symbol)
        base = DEMO_BASE_PRICES.get(symbol, 1000.0)
        return {
            "last_price": ltp,
            "change": round(ltp - base, 2),
            "change_percent": round((ltp - base) / base * 100, 2),
        }
