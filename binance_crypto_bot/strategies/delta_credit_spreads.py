"""
delta_credit_spreads.py — Defined-Risk Bull Put & Bear Call Credit Spreads for Crypto Options.
"""

import pandas as pd
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_rsi, calculate_sma
from binance_crypto_bot.utils.option_chain import get_otm_strikes, format_delta_option_symbol
from binance_crypto_bot.utils.greeks import calculate_black_scholes

class DeltaCreditSpreadsStrategy(BaseCryptoStrategy):
    def __init__(self):
        super().__init__(name="Delta Credit Spreads")

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < 30:
            return {"action": "HOLD", "reason": "Insufficient data"}

        df = df.copy()
        df["rsi"] = calculate_rsi(df, 14)
        df["sma_50"] = calculate_sma(df, 30)

        curr = df.iloc[-1]
        spot_price = curr["close"]

        # Bullish Trend Above SMA -> Bull Put Credit Spread (Sell OTM Put, Buy Lower OTM Put)
        if spot_price > curr["sma_50"] and curr["rsi"] > 50:
            strikes = get_otm_strikes(spot_price, "BTC", offset_steps=1)
            sell_put_strike = strikes["put_otm"]
            buy_put_strike = sell_put_strike - 500

            sell_bs = calculate_black_scholes("PUT", spot_price, sell_put_strike, time_to_expiry_years=7/365.0)
            buy_bs = calculate_black_scholes("PUT", spot_price, buy_put_strike, time_to_expiry_years=7/365.0)

            net_credit = sell_bs["theoretical_price"] - buy_bs["theoretical_price"]

            return {
                "action": "BULL_PUT_SPREAD",
                "underlying": "BTC",
                "sell_strike": sell_put_strike,
                "buy_strike": buy_put_strike,
                "price": spot_price,
                "net_credit": round(max(net_credit, 5.0), 2),
                "reason": f"Bullish Trend -> Sell ${sell_put_strike:.0f} Put / Buy ${buy_put_strike:.0f} Put Spread",
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No credit spread setup"}
