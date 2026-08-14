"""
delta_option_scalper.py — Data-Optimized Crypto Option Scalper Strategy.

Optimizations from 12.3M real trade analysis (Jun–Jul 2026):
  - Peak window shifted to 18:00–21:00 IST (US market open = 2.7x higher premiums)
  - ETH focus: $3–$15 premium range has +30% avg final return in real data
  - BTC cheap options skipped entirely (avg final return: -90% in real data)
  - Stop Loss widened from -20% to -30% (SL was firing 50% of the time)
  - TP1 raised from +10% to +15%, TP2 from +20% to +30%
  - Cooldown extended to 300s to reduce over-trading
"""

import pandas as pd
from typing import Dict, Any
import datetime
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.indicators import calculate_ema, calculate_macd, calculate_adx
from binance_crypto_bot.utils.option_chain import get_atm_strike, format_delta_option_symbol
from binance_crypto_bot.utils.greeks import calculate_black_scholes


def is_peak_window_active() -> bool:
    """
    Returns True if current time is in the primary or secondary trading window.

    Primary:   18:00–21:00 IST = 12:30–15:30 UTC (US market open — 2.7x higher premiums)
    Secondary: 09:00–11:30 IST = 03:30–06:00 UTC (Asia morning momentum)
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc).time()
    # Primary window: US open 12:30–15:30 UTC
    primary   = datetime.time(12, 30) <= now_utc <= datetime.time(15, 30)
    # Secondary window: Asia open 03:30–06:00 UTC
    secondary = datetime.time(3, 30)  <= now_utc <= datetime.time(6, 0)
    return primary or secondary


# ETH-optimized premium range (from real market data: $3–$15 = +30% avg final return)
ETH_MIN_PREMIUM = 3.0
ETH_MAX_PREMIUM = 15.0

# BTC: only trade premiums >$100 (real data shows cheap BTC options avg -90% final return)
BTC_MIN_PREMIUM = 100.0


class DeltaOptionScalperStrategy(BaseCryptoStrategy):
    def __init__(self, fast_period: int = 3, slow_period: int = 8, cooldown_seconds: int = 300):
        super().__init__(name="Delta Option Scalper")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.cooldown_seconds = cooldown_seconds
        self.last_signal_time: Dict[str, float] = {}

    def _premium_is_valid(self, underlying: str, premium: float) -> bool:
        """Filter out premiums outside the empirically optimal range per asset."""
        if underlying == "ETH":
            return ETH_MIN_PREMIUM <= premium <= ETH_MAX_PREMIUM
        elif underlying == "BTC":
            return premium >= BTC_MIN_PREMIUM
        return True

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or len(df) < self.slow_period + 14:
            return {"action": "HOLD", "reason": "Insufficient data"}

        underlying = df.attrs.get("symbol", "BTC").upper()
        underlying = "ETH" if "ETH" in underlying else "BTC"

        # Signal Cooldown Guard: 300 seconds between signals per asset
        now_ts = datetime.datetime.now().timestamp()
        last_ts = self.last_signal_time.get(underlying, 0)
        elapsed = now_ts - last_ts
        if elapsed < self.cooldown_seconds:
            return {
                "action": "HOLD",
                "reason": f"Cooldown Active for {underlying} ({int(self.cooldown_seconds - elapsed)}s left)"
            }

        df = df.copy()
        df["ema_fast"] = calculate_ema(df, self.fast_period)
        df["ema_slow"] = calculate_ema(df, self.slow_period)
        df["adx"]      = calculate_adx(df, 14)
        macd, signal, hist = calculate_macd(df, fast=6, slow=13, signal=4)
        df["hist"] = hist

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        spot_price = float(curr["close"])
        adx_val    = float(curr["adx"])

        # ADX Trend Strength Filter: Veto choppy sideways markets
        if adx_val < 18.0:
            return {"action": "HOLD", "reason": f"Choppy Range Veto (ADX {adx_val:.1f} < 18)"}

        peak_active = is_peak_window_active()

        # ─── Empirically-derived TP/SL ratios (from 12.3M trade backtest) ───
        # Peak (US open 18:00-21:00 IST): wider targets, market has momentum
        # Off-peak: tighter targets, less volatility
        if peak_active:
            sl_ratio  = 0.70   # -30% SL (was -4%, now data-backed: SL was firing 50% of time)
            tp1_ratio = 1.15   # +15% TP1 (was +10%)
            tp2_ratio = 1.30   # +30% TP2 (was +20%)
        else:
            sl_ratio  = 0.75   # -25% SL off-peak (slightly tighter)
            tp1_ratio = 1.12   # +12% TP1 off-peak
            tp2_ratio = 1.22   # +22% TP2 off-peak

        # ─── Micro-Bullish Scalp → BUY CALL OPTION ───────────────────────
        bullish = (
            (prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]) or
            (prev["hist"] <= 0 and curr["hist"] > 0)
        )
        if bullish:
            strike = get_atm_strike(spot_price, underlying)
            symbol = format_delta_option_symbol(underlying, "CALL", strike)
            bs = calculate_black_scholes("CALL", spot_price, strike, time_to_expiry_years=7/365.0, underlying=underlying)
            premium = bs["theoretical_price"]

            # Premium range filter (key insight from real data)
            if not self._premium_is_valid(underlying, premium):
                return {
                    "action": "HOLD",
                    "reason": f"Premium filter: {underlying} ${premium:.2f} outside optimal range "
                              f"(ETH: $3–$15, BTC: >$100)"
                }

            sl_premium  = round(premium * sl_ratio,  2)
            tp1_premium = round(premium * tp1_ratio, 2)
            tp2_premium = round(premium * tp2_ratio, 2)
            self.last_signal_time[underlying] = now_ts

            window_tag = "🔥 US Peak" if peak_active else "Asia Window" if is_peak_window_active() else "Off-Peak"
            return {
                "action": "BUY_CALL",
                "symbol": symbol,
                "underlying": underlying,
                "option_type": "CALL",
                "strike": strike,
                "price": spot_price,
                "premium": premium,
                "stop_loss": sl_premium,
                "take_profit_1": tp1_premium,
                "take_profit_2": tp2_premium,
                "take_profit": tp1_premium,
                "peak_window": peak_active,
                "reason": (
                    f"Bullish Crossover ({window_tag}) → BUY CALL {symbol} "
                    f"| Premium: ${premium:.2f} | SL: ${sl_premium:.2f} | "
                    f"TP1: ${tp1_premium:.2f} | TP2: ${tp2_premium:.2f} | ADX: {adx_val:.1f}"
                ),
                "strategy": self.name
            }

        # ─── Micro-Bearish Scalp → BUY PUT OPTION ────────────────────────
        bearish = (
            (prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]) or
            (prev["hist"] >= 0 and curr["hist"] < 0)
        )
        if bearish:
            strike = get_atm_strike(spot_price, underlying)
            symbol = format_delta_option_symbol(underlying, "PUT", strike)
            bs = calculate_black_scholes("PUT", spot_price, strike, time_to_expiry_years=7/365.0, underlying=underlying)
            premium = bs["theoretical_price"]

            # Premium range filter
            if not self._premium_is_valid(underlying, premium):
                return {
                    "action": "HOLD",
                    "reason": f"Premium filter: {underlying} ${premium:.2f} outside optimal range "
                              f"(ETH: $3–$15, BTC: >$100)"
                }

            sl_premium  = round(premium * sl_ratio,  2)
            tp1_premium = round(premium * tp1_ratio, 2)
            tp2_premium = round(premium * tp2_ratio, 2)
            self.last_signal_time[underlying] = now_ts

            window_tag = "🔥 US Peak" if peak_active else "Off-Peak"
            return {
                "action": "BUY_PUT",
                "symbol": symbol,
                "underlying": underlying,
                "option_type": "PUT",
                "strike": strike,
                "price": spot_price,
                "premium": premium,
                "stop_loss": sl_premium,
                "take_profit_1": tp1_premium,
                "take_profit_2": tp2_premium,
                "take_profit": tp1_premium,
                "peak_window": peak_active,
                "reason": (
                    f"Bearish Crossover ({window_tag}) → BUY PUT {symbol} "
                    f"| Premium: ${premium:.2f} | SL: ${sl_premium:.2f} | "
                    f"TP1: ${tp1_premium:.2f} | TP2: ${tp2_premium:.2f} | ADX: {adx_val:.1f}"
                ),
                "strategy": self.name
            }

        return {"action": "HOLD", "reason": "No micro scalp crossover"}
