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

log = get_logger("OptionsMomentumStrategy")


class OptionsMomentumStrategy(BaseOptionsStrategy):
    """Buy ATM CE/PE based on equity consensus signal."""

    def generate_signal(self, hub_snapshot: Dict) -> Optional[OptionsSignal]:
        # Read the consensus signal from the hub snapshot
        # The hub will include the latest equity consensus direction
        consensus_direction = hub_snapshot.get("consensus_signal")  # 'BUY' or 'SELL' or None
        consensus_symbol    = hub_snapshot.get("consensus_symbol", "")

        if not consensus_direction or consensus_direction == "NONE":
            log.debug("%s: No consensus equity signal — skipping options entry.", self.bot_id)
            return None

        # Time filter: only buy options before 1:30 PM (heavy time decay after that)
        now = datetime.now()
        entry_window_end = self.bot_config.get("entry_window_end", "13:30")
        end_h, end_m = map(int, entry_window_end.split(":"))
        if now.hour > end_h or (now.hour == end_h and now.minute > end_m):
            log.debug("%s: Past entry window for options buying.", self.bot_id)
            return None

        # Use NIFTY as proxy for directional index options
        index = "NIFTY"
        opt_type = "CE" if consensus_direction == "BUY" else "PE"

        atm = hub_snapshot.get("atm_strikes", {}).get(index)
        if not atm:
            log.warning("%s: ATM strike unavailable for %s", self.bot_id, index)
            return None

        options = hub_snapshot.get("options", {})
        entry_data = options.get(f"{index}_{atm}_{opt_type}", {})
        ltp   = entry_data.get("ltp")
        token = entry_data.get("token", "")

        if not ltp:
            log.warning("%s: LTP unavailable for %s %d %s", self.bot_id, index, atm, opt_type)
            return None

        sl_pct     = self.bot_config.get("sl_pct_of_premium", 30) / 100
        target_pct = self.bot_config.get("target_pct_of_premium", 100) / 100

        # BUY options: SL = entry * (1 - sl_pct), Target = entry * (1 + target_pct)
        sl_price     = ltp * (1 - sl_pct)
        target_price = ltp * (1 + target_pct)

        lot_size = self.get_lot_size(index)
        direction_label = f"BUY_{opt_type}"

        log.info("%s: OPTIONS MOMENTUM %s %s ATM=%d | LTP=%.1f | SL=%.1f Target=%.1f | Trigger=%s %s",
                 self.bot_id, direction_label, index, atm, ltp, sl_price, target_price,
                 consensus_direction, consensus_symbol)

        return OptionsSignal(
            bot_id=self.bot_id,
            strategy=self.name,
            signal_type=direction_label.lower(),
            index=index,
            atm_strike=atm,
            ce_strike=atm if opt_type == "CE" else 0,
            pe_strike=atm if opt_type == "PE" else 0,
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
            notes=f"Triggered by {consensus_direction} signal on {consensus_symbol}",
        )
