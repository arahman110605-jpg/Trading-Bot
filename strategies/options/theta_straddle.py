"""
strategies/options/theta_straddle.py — ATM Short Straddle (Theta Harvester)

Strategy: Sell ATM Call + Sell ATM Put at 9:20 AM.
Profit from time decay (theta). Exit at 50% profit or 40% loss of premium.

Market stats:
  - Win rate: ~65-70% on non-trending days
  - Best on: low VIX, sideways/range-bound market days
  - Risk: Unlimited if market gaps/trends hard (managed by 40% SL)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from strategies.options.base_options_strategy import BaseOptionsStrategy, OptionsSignal
from utils.logger import get_logger

import pytz

IST = pytz.timezone("Asia/Kolkata")

log = get_logger("ThetaStraddleStrategy")


class ThetaStraddleStrategy(BaseOptionsStrategy):
    """9:20 ATM Short Straddle on NIFTY weekly options."""

    def generate_signal(self, hub_snapshot: Dict) -> Optional[OptionsSignal]:
        index = self.bot_config.get("instruments", ["NIFTY"])[0]
        vix   = hub_snapshot.get("vix")
        max_vix = self.bot_config.get("vix_max", 18.0)

        # VIX safety check
        if not self.is_vix_safe(vix, max_vix):
            return None

        # Time filter: only enter around 9:20 AM IST
        now = datetime.now(IST)
        entry_time = self.bot_config.get("entry_time", "09:20")
        entry_h, entry_m = map(int, entry_time.split(":"))
        if not (now.hour == entry_h and abs(now.minute - entry_m) <= 10):
            log.debug("%s: Outside entry window (entry=%s, now=%02d:%02d)",
                      self.bot_id, entry_time, now.hour, now.minute)
            return None

        # Get ATM strike
        atm = hub_snapshot.get("atm_strikes", {}).get(index)
        if not atm:
            log.warning("%s: ATM strike not available for %s", self.bot_id, index)
            return None

        # Get CE and PE LTPs
        options = hub_snapshot.get("options", {})
        ce_entry = options.get(f"{index}_{atm}_CE", {}).get("ltp")
        pe_entry = options.get(f"{index}_{atm}_PE", {}).get("ltp")
        ce_token = options.get(f"{index}_{atm}_CE", {}).get("token", "")
        pe_token = options.get(f"{index}_{atm}_PE", {}).get("token", "")

        if not ce_entry or not pe_entry:
            log.warning("%s: CE or PE LTP unavailable for %s ATM=%d", self.bot_id, index, atm)
            return None

        total_premium = ce_entry + pe_entry
        sl_pct = self.bot_config.get("sl_pct_of_premium", 40) / 100
        tp_pct = self.bot_config.get("target_pct_of_premium", 50) / 100

        # For a SELL straddle:
        #   SL   = total_premium * (1 + sl_pct)  → exit if premium RISES 40%
        #   Target = total_premium * (1 - tp_pct) → exit if premium FALLS 50%
        sl_premium     = total_premium * (1 + sl_pct)
        target_premium = total_premium * (1 - tp_pct)

        lot_size = self.get_lot_size(index)

        log.info("%s: STRADDLE SIGNAL %s ATM=%d | CE=%.1f PE=%.1f | Total=%.1f | SL=%.1f Target=%.1f",
                 self.bot_id, index, atm, ce_entry, pe_entry, total_premium, sl_premium, target_premium)

        return OptionsSignal(
            bot_id=self.bot_id,
            strategy=self.name,
            signal_type="straddle_sell",
            index=index,
            atm_strike=atm,
            ce_strike=atm,
            pe_strike=atm,
            ce_token=ce_token,
            pe_token=pe_token,
            ce_entry_price=ce_entry,
            pe_entry_price=pe_entry,
            total_premium=total_premium,
            sl_premium=sl_premium,
            target_premium=target_premium,
            lot_size=lot_size,
            lots=self.lots,
            direction="SELL",
            confidence=0.80,
            notes=f"VIX={vix:.1f} ATM={atm}",
        )
