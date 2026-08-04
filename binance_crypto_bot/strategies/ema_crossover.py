"""
ema_crossover.py — EMA Crossover Trend-Following Crypto Strategy.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_ema, calculate_atr
from binance_crypto_bot.config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

class EMACrossoverStrategy(BaseCryptoStrategy):
    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        super().__init__(name="EMA Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.slow_period + 2:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        df["ema_fast"] = calculate_ema(df, self.fast_period)
        df["ema_slow"] = calculate_ema(df, self.slow_period)
        df["atr"] = calculate_atr(df, 14)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = curr["close"]
        atr = curr["atr"] if curr["atr"] > 0 else current_price * 0.01

        # Bullish Crossover (Fast EMA crosses above Slow EMA)
        if prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]:
            sl = current_price - (atr * 1.5)
            tp = current_price + (atr * 3.0)
            return {
                "action": "BUY",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"Bullish EMA Crossover ({self.fast_period}/{self.slow_period})",
                "strategy": self.name
            }

        # Bearish Crossover (Fast EMA crosses below Slow EMA)
        elif prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]:
            sl = current_price + (atr * 1.5)
            tp = current_price - (atr * 3.0)
            return {
                "action": "SELL",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"Bearish EMA Crossover ({self.fast_period}/{self.slow_period})",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No EMA Crossover detected"}
