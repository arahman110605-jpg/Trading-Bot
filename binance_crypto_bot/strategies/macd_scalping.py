"""
macd_scalping.py — MACD + Bollinger Bands High-Frequency Crypto Scalper.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_macd, calculate_bollinger_bands, calculate_atr

class MACDScalpingStrategy(BaseCryptoStrategy):
    def __init__(self):
        super().__init__(name="MACD Scalping")

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < 30:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        macd, signal, hist = calculate_macd(df, fast=12, slow=26, signal=9)
        upper, middle, lower = calculate_bollinger_bands(df, period=20, std_dev=2.0)
        atr = calculate_atr(df, 14)

        df["macd"] = macd
        df["signal"] = signal
        df["hist"] = hist
        df["upper"] = upper
        df["lower"] = lower
        df["atr"] = atr

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = curr["close"]
        curr_atr = curr["atr"] if curr["atr"] > 0 else current_price * 0.005

        # MACD bullish crossover below lower band (Scalp BUY)
        if prev["macd"] <= prev["signal"] and curr["macd"] > curr["signal"] and curr["close"] <= curr["lower"] * 1.01:
            sl = current_price - (curr_atr * 1.2)
            tp = current_price + (curr_atr * 2.5)
            return {
                "action": "BUY",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": "MACD Bullish Crossover near Lower Bollinger Band",
                "strategy": self.name
            }

        # MACD bearish crossover above upper band (Scalp SELL)
        elif prev["macd"] >= prev["signal"] and curr["macd"] < curr["signal"] and curr["close"] >= curr["upper"] * 0.99:
            sl = current_price + (curr_atr * 1.2)
            tp = current_price - (curr_atr * 2.5)
            return {
                "action": "SELL",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": "MACD Bearish Crossover near Upper Bollinger Band",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No MACD scalp signal"}
