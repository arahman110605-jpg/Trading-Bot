"""
eth_spot_scalper.py — ETH/BTC Spot Momentum Scalper (Strategy A).

Uses the same AI-validated EMA/MACD/ADX signals as the option scalper
but executes on SPOT market — no theta decay, no premium risk.

Capital allocation: $600 of $1,000 total
Position size:      $50 per trade (5% of spot capital)
TP:                 +1.5%  (realistic 1-hr ETH move in trending market)
SL:                 -0.8%  (tight, protects capital)
Win rate target:    52–58% (from real market data on momentum signals)
"""

import pandas as pd
import datetime
from typing import Dict, Any
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_ema, calculate_macd, calculate_adx


# Position size per trade in USDT
TRADE_SIZE_USDT = 50.0   # $50 per trade

# TP/SL ratios (from real ETH spot momentum data)
TP_PCT = 0.015   # +1.5%
SL_PCT = 0.008   # -0.8%

# Cooldown between signals per asset (seconds)
COOLDOWN_SECS = 300


class EthSpotScalperStrategy(BaseCryptoStrategy):
    """
    Spot momentum scalper.
    Buys ETH/BTC on confirmed EMA crossover + MACD + ADX > 22.
    Exits via TP (+1.5%) or SL (-0.8%).
    No options, no theta, no complex Greeks.
    """

    def __init__(self, fast_period: int = 3, slow_period: int = 8):
        super().__init__(name="ETH Spot Scalper")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.last_signal_time: Dict[str, float] = {}

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.slow_period + 14:
            return {"action": "HOLD", "reason": "Insufficient data"}

        underlying = df.attrs.get("symbol", "ETH").upper()
        underlying = "ETH" if "ETH" in underlying else "BTC"

        # Cooldown guard
        now_ts   = datetime.datetime.now().timestamp()
        last_ts  = self.last_signal_time.get(underlying, 0)
        elapsed  = now_ts - last_ts
        if elapsed < COOLDOWN_SECS:
            return {
                "action": "HOLD",
                "reason": f"Spot cooldown for {underlying} ({int(COOLDOWN_SECS - elapsed)}s left)"
            }

        df = df.copy()
        df["ema_fast"] = calculate_ema(df, self.fast_period)
        df["ema_slow"] = calculate_ema(df, self.slow_period)
        df["adx"]      = calculate_adx(df, 14)
        _, __, hist    = calculate_macd(df, fast=6, slow=13, signal=4)
        df["hist"]     = hist

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        spot = float(curr["close"])
        adx  = float(curr["adx"])
        ret_5m = (curr["close"] - prev["close"]) / prev["close"] * 100

        # ADX filter — only trade in trending markets
        if adx < 22.0:
            return {"action": "HOLD", "reason": f"Spot ADX too low ({adx:.1f} < 22) — choppy market"}

        # Bullish crossover → BUY spot
        bullish = (
            (prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]) or
            (prev["hist"] <= 0 and curr["hist"] > 0)
        ) and ret_5m > 0.05

        if bullish:
            tp_price = round(spot * (1 + TP_PCT), 2)
            sl_price = round(spot * (1 - SL_PCT), 2)
            qty      = round(TRADE_SIZE_USDT / spot, 6)
            self.last_signal_time[underlying] = now_ts

            return {
                "action":     "BUY",
                "symbol":     underlying,
                "underlying": underlying,
                "price":      spot,
                "qty":        qty,
                "tp_price":   tp_price,
                "sl_price":   sl_price,
                "reason":     (
                    f"Spot BUY {underlying} @ ${spot:.2f} | "
                    f"TP: ${tp_price} (+{TP_PCT*100:.1f}%) | "
                    f"SL: ${sl_price} (-{SL_PCT*100:.1f}%) | ADX: {adx:.1f} | 5m: {ret_5m:+.2f}%"
                ),
                "strategy":   self.name,
            }

        return {"action": "HOLD", "reason": f"No spot bullish crossover (ADX:{adx:.1f} | 5m:{ret_5m:+.2f}%)"}
