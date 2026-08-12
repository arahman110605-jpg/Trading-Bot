"""
delta_option_buying.py — Directional Crypto Option Buying Strategy (Call & Put Options).
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_ema, calculate_rsi, calculate_atr
from binance_crypto_bot.utils.option_chain import get_atm_strike, format_delta_option_symbol
from binance_crypto_bot.utils.greeks import calculate_black_scholes
from binance_crypto_bot.config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

class DeltaOptionBuyingStrategy(BaseCryptoStrategy):
    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        super().__init__(name="Delta Option Buying")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.slow_period + 2:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        df["ema_fast"] = calculate_ema(df, self.fast_period)
        df["ema_slow"] = calculate_ema(df, self.slow_period)
        df["rsi"] = calculate_rsi(df, 14)
        df["atr"] = calculate_atr(df, 14)

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        spot_price = curr["close"]

        # Bullish Signal -> BUY CALL OPTION
        if prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"] and curr["rsi"] > 45:
            strike = get_atm_strike(spot_price, "BTC")
            symbol = format_delta_option_symbol("BTC", "CALL", strike)
            
            # Theoretical premium & Greeks
            bs = calculate_black_scholes("CALL", spot_price, strike, time_to_expiry_years=7/365.0)
            premium = max(bs["theoretical_price"], 10.0)

            sl_premium = round(premium * (1 - STOP_LOSS_PCT), 2)
            tp_premium = round(premium * (1 + TAKE_PROFIT_PCT), 2)

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
                "reason": f"Bullish Momentum -> BUY CALL {symbol} @ Strike ${strike:.0f}",
                "strategy": self.name
            }

        # Bearish Signal -> BUY PUT OPTION
        elif prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"] and curr["rsi"] < 55:
            strike = get_atm_strike(spot_price, "BTC")
            symbol = format_delta_option_symbol("BTC", "PUT", strike)

            bs = calculate_black_scholes("PUT", spot_price, strike, time_to_expiry_years=7/365.0)
            premium = max(bs["theoretical_price"], 10.0)

            sl_premium = round(premium * (1 - STOP_LOSS_PCT), 2)
            tp_premium = round(premium * (1 + TAKE_PROFIT_PCT), 2)

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
                "reason": f"Bearish Momentum -> BUY PUT {symbol} @ Strike ${strike:.0f}",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No directional option setup"}
