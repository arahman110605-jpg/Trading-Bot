"""
rsi_divergence.py — RSI Oversold/Overbought Momentum Strategy for Crypto.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_rsi, calculate_atr
from binance_crypto_bot.config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

class RSIDivergenceStrategy(BaseCryptoStrategy):
    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        super().__init__(name="RSI Divergence")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.rsi_period + 2:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        df["rsi"] = calculate_rsi(df, self.rsi_period)
        df["atr"] = calculate_atr(df, 14)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = curr["close"]
        atr = curr["atr"] if curr["atr"] > 0 else current_price * 0.01

        # RSI crossing above oversold (Buy Signal)
        if prev["rsi"] <= self.oversold and curr["rsi"] > self.oversold:
            sl = current_price - (atr * 2.0)
            tp = current_price + (atr * 3.5)
            return {
                "action": "BUY",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"RSI recovered from Oversold level ({curr['rsi']:.1f})",
                "strategy": self.name
            }

        # RSI crossing below overbought (Sell Signal)
        elif prev["rsi"] >= self.overbought and curr["rsi"] < self.overbought:
            sl = current_price + (atr * 2.0)
            tp = current_price - (atr * 3.5)
            return {
                "action": "SELL",
                "price": current_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"RSI dropped from Overbought level ({curr['rsi']:.1f})",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "RSI in neutral range"}
