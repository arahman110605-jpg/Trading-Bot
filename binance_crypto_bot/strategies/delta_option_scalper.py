"""
delta_option_scalper.py — High-Frequency Quick-Profit Crypto Option Scalper Strategy.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_ema, calculate_macd
from binance_crypto_bot.utils.option_chain import get_atm_strike, format_delta_option_symbol
from binance_crypto_bot.utils.greeks import calculate_black_scholes

class DeltaOptionScalperStrategy(BaseCryptoStrategy):
    def __init__(self, fast_period: int = 3, slow_period: int = 8):
        super().__init__(name="Delta Option Scalper")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.slow_period + 2:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        df["ema_fast"] = calculate_ema(df, self.fast_period)
        df["ema_slow"] = calculate_ema(df, self.slow_period)
        macd, signal, hist = calculate_macd(df, fast=6, slow=13, signal=4)
        df["hist"] = hist

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        spot_price = float(curr["close"])

        # Micro-Bullish Scalp -> BUY CALL OPTION (Target +8% TP / -4% SL)
        if (prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]) or (prev["hist"] <= 0 and curr["hist"] > 0):
            strike = get_atm_strike(spot_price, "BTC")
            symbol = format_delta_option_symbol("BTC", "CALL", strike)
            
            bs = calculate_black_scholes("CALL", spot_price, strike, time_to_expiry_years=7/365.0)
            premium = max(bs["theoretical_price"], 1.50)

            sl_premium = round(premium * 0.96, 2)
            tp_premium = round(premium * 1.08, 2)

            return {
                "action": "BUY_CALL",
                "symbol": symbol,
                "underlying": "BTC",
                "option_type": "CALL",
                "strike": strike,
                "price": spot_price,
                "premium": premium,
                "stop_loss": sl_premium,
                "take_profit": tp_premium,
                "reason": f"Bullish Crossover -> BUY CALL {symbol} (TP: ${tp_premium:.2f}, SL: ${sl_premium:.2f})",
                "strategy": self.name
            }

        # Micro-Bearish Scalp -> BUY PUT OPTION (Target +8% TP / -4% SL)
        elif (prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]) or (prev["hist"] >= 0 and curr["hist"] < 0):
            strike = get_atm_strike(spot_price, "BTC")
            symbol = format_delta_option_symbol("BTC", "PUT", strike)

            bs = calculate_black_scholes("PUT", spot_price, strike, time_to_expiry_years=7/365.0)
            premium = max(bs["theoretical_price"], 1.50)

            sl_premium = round(premium * 0.96, 2)
            tp_premium = round(premium * 1.08, 2)

            return {
                "action": "BUY_PUT",
                "symbol": symbol,
                "underlying": "BTC",
                "option_type": "PUT",
                "strike": strike,
                "price": spot_price,
                "premium": premium,
                "stop_loss": sl_premium,
                "take_profit": tp_premium,
                "reason": f"Bearish Crossover -> BUY PUT {symbol} (TP: ${tp_premium:.2f}, SL: ${sl_premium:.2f})",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No micro scalp crossover"}
