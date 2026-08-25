"""
strategies/options/options_momentum.py — Directional Momentum via Options Buying

Strategy: Buy ATM Call (if BUY signal) or ATM Put (if SELL signal) from
          the Multi-Consensus equity bot (Bot 05).

Risk profile: Pay premium, max loss = 30% of premium paid.
Profit: 100% of premium (2x on strong moves).

Market stats:
  - Win rate: ~45-55% but asymmetric R:R of 1:3
  - Best on: strong trending/volatile days
  - Risk: Limited (premium paid)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from strategies.options.base_options_strategy import BaseOptionsStrategy, OptionsSignal
from utils.logger import get_logger

import pytz

IST = pytz.timezone("Asia/Kolkata")

log = get_logger("OptionsMomentumStrategy")


class OptionsMomentumStrategy(BaseOptionsStrategy):
    """Buy ATM CE/PE based on equity consensus signal."""

    def generate_signal(self, hub_snapshot: Dict) -> Optional[OptionsSignal]:
        # Read the consensus signal or fallback to broader market breadth trend
        direction = hub_snapshot.get("consensus_signal")
        trigger_src = hub_snapshot.get("consensus_symbol", "EQUITY")
        if not direction or direction == "NONE":
            mkt_trend = hub_snapshot.get("market_trend")
            if mkt_trend == "BULLISH":
                direction = "BUY"
                trigger_src = "MARKET_BREADTH_BULLISH"
            elif mkt_trend == "BEARISH":
                direction = "SELL"
                trigger_src = "MARKET_BREADTH_BEARISH"

        if not direction or direction == "NONE":
            log.debug("%s: No directional trigger available — skipping options entry.", self.bot_id)
            return None

        # Time filter: only buy options before 2:00 PM IST (heavy time decay after that)
        now = datetime.now(IST)
        entry_window_end = self.bot_config.get("entry_window_end", "14:00")
        end_h, end_m = map(int, entry_window_end.split(":"))
        if now.hour > end_h or (now.hour == end_h and now.minute > end_m):
            log.debug("%s: Past entry window for options buying.", self.bot_id)
            return None

        # Use NIFTY as proxy for directional index options
        index = "NIFTY"
        interval = 50 if index == "NIFTY" else 100
        opt_type = "CE" if direction == "BUY" else "PE"

        atm = hub_snapshot.get("atm_strikes", {}).get(index)
        if not atm:
            log.warning("%s: ATM strike unavailable for %s", self.bot_id, index)
            return None

        # Select ITM Delta >= 0.60 strike (ATM-1 interval for CE, ATM+1 interval for PE)
        itm_strike = (atm - interval) if opt_type == "CE" else (atm + interval)
        options = hub_snapshot.get("options", {})
        
        # Try ITM strike first; fallback to ATM if ITM not cached
        entry_data = options.get(f"{index}_{itm_strike}_{opt_type}", {})
        chosen_strike = itm_strike
        if not entry_data.get("ltp"):
            entry_data = options.get(f"{index}_{atm}_{opt_type}", {})
            chosen_strike = atm

        ltp   = entry_data.get("ltp")
        token = entry_data.get("token", "")

        if not ltp:
            log.warning("%s: LTP unavailable for %s %d %s", self.bot_id, index, chosen_strike, opt_type)
            return None

        sl_pct     = self.bot_config.get("sl_pct_of_premium", 25) / 100
        target_pct = self.bot_config.get("target_pct_of_premium", 100) / 100

        # BUY options: SL = entry * (1 - sl_pct), Target = entry * (1 + target_pct)
        sl_price     = round(ltp * (1 - sl_pct), 2)
        target_price = round(ltp * (1 + target_pct), 2)

        lot_size = self.get_lot_size(index)
        direction_label = f"BUY_{opt_type}"

        log.info("%s: [OPTIONS MOMENTUM] %s %s Strike=%d (ATM=%d) | LTP=%.1f | SL=%.1f Target=%.1f | Trigger=%s %s",
                 self.bot_id, direction_label, index, chosen_strike, atm, ltp, sl_price, target_price,
                 consensus_direction, consensus_symbol)

        return OptionsSignal(
            bot_id=self.bot_id,
            strategy=self.name,
            signal_type=direction_label.lower(),
            index=index,
            atm_strike=atm,
            ce_strike=chosen_strike if opt_type == "CE" else 0,
            pe_strike=chosen_strike if opt_type == "PE" else 0,
            ce_token=token if opt_type == "CE" else "",
            pe_token=token if opt_type == "PE" else "",
            ce_entry_price=ltp if opt_type == "CE" else 0.0,
            pe_entry_price=ltp if opt_type == "PE" else 0.0,
            total_premium=ltp,
            sl_premium=sl_price,
            target_premium=target_price,
            lot_size=lot_size,
            lots=self.lots,
            direction=direction_label,
            confidence=0.85,
            notes=f"Asymmetric ITM Momentum ({direction_label} {chosen_strike}) triggered by {consensus_direction} on {consensus_symbol}",
        )
