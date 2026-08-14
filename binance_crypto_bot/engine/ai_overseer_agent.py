"""
ai_overseer_agent.py — AI Trading Overseer Agent Layer.

v2.0 — Updated with Call/Put Volume Ratio signal from 12.3M trade analysis:
  - BTC: 42.3% of hours are bullish (C/P > 55%). Market skews bullish.
  - ETH: 36.0% bullish, 25.2% bearish.
  - New: Directional Alignment Score added as 4th factor.
  - New: Explicit CALL bias when C/P ratio > 55%, PUT bias when P/C > 55%.
"""

import time
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from binance_crypto_bot.utils.logger import logger


class AIStrategyOverseer:
    """
    AI Overseer evaluates candidate trade signals across 4 weighted factors:

    Factor 1 — 5-Min Candle Impulse       (35%): Price expanding in trade direction?
    Factor 2 — EMA Trend Confluence        (25%): Fast EMA aligned with trade direction?
    Factor 3 — MACD Histogram Momentum     (20%): MACD expanding in trade direction?
    Factor 4 — Call/Put Volume Alignment   (20%): Real market volume biasing same direction?

    Multiply by Risk Health Multiplier (0.3–1.0) based on account margin.
    Confidence >= 70% → CONFIRM. Below → VETO.
    """

    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold
        self.decision_logs: List[Dict[str, Any]] = []

        # Call/Put volume ratio — updated externally by strategy runner each tick
        # Keyed by underlying: {"BTC": 0.58, "ETH": 0.51, ...}
        self.cp_ratios: Dict[str, float] = {}

    def update_cp_ratio(self, underlying: str, cp_ratio: float):
        """Called by the strategy runner to feed live C/P volume ratio."""
        self.cp_ratios[underlying] = cp_ratio

    def evaluate_signal(
        self,
        signal: Dict[str, Any],
        df: pd.DataFrame,
        account_balance: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate trade signal. Returns decision CONFIRM or VETO
        with confidence score and full reasoning chain.
        """
        if not signal or signal.get("action") not in ["BUY_CALL", "BUY_PUT", "BUY", "SELL"]:
            return {"decision": "VETO", "confidence_score": 0.0, "reasoning": "Invalid signal action"}

        underlying = signal.get("underlying", "BTC")
        action     = signal.get("action")
        premium    = signal.get("premium", 0.0)

        momentum_score = 0.0
        reasons        = []

        if not df.empty and len(df) >= 10:
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            ret_5m = ((curr["close"] - prev["close"]) / prev["close"]) * 100.0

            # ── Factor 1: 5-Min Candle Impulse (weight: 35%) ─────────────
            if action == "BUY_CALL":
                if ret_5m > 0.05:
                    momentum_score += 0.35
                    reasons.append(f"Positive 5m momentum (+{ret_5m:.2f}%)")
                else:
                    reasons.append(f"Weak 5m momentum ({ret_5m:.2f}%)")
            elif action == "BUY_PUT":
                if ret_5m < -0.05:
                    momentum_score += 0.35
                    reasons.append(f"Negative 5m momentum ({ret_5m:.2f}%)")
                else:
                    reasons.append(f"Weak 5m momentum ({ret_5m:.2f}%)")

            # ── Factor 2: EMA Trend Confluence (weight: 25%) ──────────────
            ema_fast = curr.get("ema_fast", 0)
            ema_slow = curr.get("ema_slow", 0)
            if action == "BUY_CALL" and ema_fast > ema_slow:
                momentum_score += 0.25
                reasons.append("Fast EMA above Slow EMA (uptrend)")
            elif action == "BUY_PUT" and ema_fast < ema_slow:
                momentum_score += 0.25
                reasons.append("Fast EMA below Slow EMA (downtrend)")
            else:
                reasons.append("EMA not aligned with trade direction")

            # ── Factor 3: MACD Histogram (weight: 20%) ────────────────────
            hist = curr.get("hist", 0)
            if action == "BUY_CALL" and hist > 0:
                momentum_score += 0.20
                reasons.append(f"MACD Histogram positive ({hist:.3f})")
            elif action == "BUY_PUT" and hist < 0:
                momentum_score += 0.20
                reasons.append(f"MACD Histogram negative ({hist:.3f})")
            else:
                reasons.append(f"MACD Histogram against trade direction ({hist:.3f})")

        # ── Factor 4: Call/Put Volume Alignment (weight: 20%) ────────────
        # From real data: BTC 42% bullish hours, ETH 36% bullish hours
        cp_ratio = self.cp_ratios.get(underlying, 0.50)
        if action == "BUY_CALL" and cp_ratio > 0.55:
            momentum_score += 0.20
            reasons.append(f"Bullish C/P ratio ({cp_ratio:.2f} > 0.55) confirms call entry")
        elif action == "BUY_PUT" and cp_ratio < 0.45:
            momentum_score += 0.20
            reasons.append(f"Bearish C/P ratio ({cp_ratio:.2f} < 0.45) confirms put entry")
        elif cp_ratio == 0.50:
            # No C/P data yet — partial credit (don't penalise cold start)
            momentum_score += 0.10
            reasons.append("C/P ratio not yet available (neutral)")
        else:
            reasons.append(f"C/P ratio ({cp_ratio:.2f}) does not confirm direction")

        # ── Risk & Account Health Multiplier ─────────────────────────────
        avail_bal = account_balance.get("available", 0.0)
        total_eq  = account_balance.get("total_equity", 60.0)
        risk_score = 1.0
        if avail_bal < total_eq * 0.15:
            risk_score = 0.3
            reasons.append(f"Low margin (${avail_bal:.2f} available)")

        # ── Final Composite Score ─────────────────────────────────────────
        confidence = float(round(momentum_score * risk_score, 2))

        if confidence >= self.confidence_threshold:
            decision  = "CONFIRM"
            reasoning = f"AI Approved ({int(confidence*100)}% Confidence) → " + "; ".join(reasons)
        else:
            decision  = "VETO"
            reasoning = (
                f"AI Vetoed ({int(confidence*100)}% Confidence < "
                f"{int(self.confidence_threshold*100)}% Threshold) → " + "; ".join(reasons)
            )

        log_entry = {
            "timestamp":        time.strftime("%H:%M:%S"),
            "symbol":           signal.get("symbol"),
            "underlying":       underlying,
            "action":           action,
            "premium":          round(float(premium), 2),
            "cp_ratio":         round(float(cp_ratio), 2),
            "decision":         decision,
            "confidence_score": confidence,
            "reasoning":        reasoning
        }

        self.decision_logs.insert(0, log_entry)
        self.decision_logs = self.decision_logs[:30]

        logger.info(f"[AI OVERSEER] {decision} {action} {signal.get('symbol')} | Score: {confidence:.2f} | {reasoning}")
        return {
            "decision":         decision,
            "confidence_score": confidence,
            "reasoning":        reasoning,
            "log":              log_entry
        }
