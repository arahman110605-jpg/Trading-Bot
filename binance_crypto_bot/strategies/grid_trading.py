"""
grid_trading.py — Quantitative Grid Trading Strategy for Ranging Crypto Markets.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_bollinger_bands, calculate_grid_levels

class GridTradingStrategy(BaseCryptoStrategy):
    def __init__(self, num_grids: int = 6):
        super().__init__(name="Grid Trading")
        self.num_grids = num_grids

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < 20:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        upper, middle, lower = calculate_bollinger_bands(df, period=20, std_dev=2.0)
        
        curr_price = df.iloc[-1]["close"]
        lower_bound = lower.iloc[-1]
        upper_bound = upper.iloc[-1]

        grid_levels = calculate_grid_levels(curr_price, lower_bound, upper_bound, self.num_grids)

        # Check proximity to grid levels
        min_distance = float('inf')
        closest_level = grid_levels[0]

        for level in grid_levels:
            dist = abs(curr_price - level)
            if dist < min_distance:
                min_distance = dist
                closest_level = level

        # If near bottom grid levels, BUY signal
        if curr_price <= grid_levels[1]:
            sl = curr_price * 0.97
            tp = grid_levels[len(grid_levels) // 2]
            return {
                "action": "BUY",
                "price": curr_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"Price near lower grid level (${closest_level:.2f})",
                "strategy": self.name
            }

        # If near top grid levels, SELL signal
        elif curr_price >= grid_levels[-2]:
            sl = curr_price * 1.03
            tp = grid_levels[len(grid_levels) // 2]
            return {
                "action": "SELL",
                "price": curr_price,
                "stop_loss": round(sl, 4),
                "take_profit": round(tp, 4),
                "reason": f"Price near upper grid level (${closest_level:.2f})",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "Price inside mid-grid range"}
