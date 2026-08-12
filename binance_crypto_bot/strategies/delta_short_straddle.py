"""
delta_short_straddle.py — Delta-Neutral Theta Decay Short Straddle/Strangle Strategy.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_bollinger_bands, calculate_atr
from binance_crypto_bot.utils.option_chain import get_atm_strike, format_delta_option_symbol
from binance_crypto_bot.utils.greeks import calculate_black_scholes

class DeltaShortStraddleStrategy(BaseCryptoStrategy):
    def __init__(self):
        super().__init__(name="Delta Short Straddle")

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < 25:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        upper, middle, lower = calculate_bollinger_bands(df, period=20, std_dev=2.0)
        atr = calculate_atr(df, 14)

        df["upper"] = upper
        df["middle"] = middle
        df["lower"] = lower
        df["band_width"] = (df["upper"] - df["lower"]) / df["middle"]

        curr = df.iloc[-1]
        spot_price = curr["close"]

        # Low Volatility Squeeze -> Harvest Theta Decay
        if curr["band_width"] < 0.03:
            atm_strike = get_atm_strike(spot_price, "BTC")
            call_sym = format_delta_option_symbol("BTC", "CALL", atm_strike)
            put_sym = format_delta_option_symbol("BTC", "PUT", atm_strike)

            call_bs = calculate_black_scholes("CALL", spot_price, atm_strike, time_to_expiry_years=7/365.0)
            put_bs = calculate_black_scholes("PUT", spot_price, atm_strike, time_to_expiry_years=7/365.0)

            total_premium = call_bs["theoretical_price"] + put_bs["theoretical_price"]

            return {
                "action": "SHORT_STRADDLE",
                "underlying": "BTC",
                "strike": atm_strike,
                "call_symbol": call_sym,
                "put_symbol": put_sym,
                "price": spot_price,
                "total_premium": round(total_premium, 2),
                "theta_decay": round(call_bs["theta"] + put_bs["theta"], 2),
                "reason": f"Volatility Squeeze (BW < 3%) -> Harvest ${total_premium:.2f} Theta Premium",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "Volatility too high for Short Straddle"}
