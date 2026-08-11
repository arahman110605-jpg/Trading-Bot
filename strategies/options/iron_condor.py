"""
strategies/options/iron_condor.py — Weekly NIFTY Iron Condor Strategy

Strategy:
  Sell OTM Call (ATM+100) + Buy further OTM Call (ATM+200)
  Sell OTM Put  (ATM-100) + Buy further OTM Put  (ATM-200)

Profit from range-bound market. Max profit = net premium collected.
Max loss = spread width - net premium (fully defined).

Market stats:
  - Win rate: ~60-65% on normal weeks
  - Best on: VIX < 15, Monday/Tuesday entry for maximum theta
  - Risk: Defined max loss — ideal for risk-managed systems
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from strategies.options.base_options_strategy import BaseOptionsStrategy, OptionsSignal
from utils.logger import get_logger

import pytz

IST = pytz.timezone("Asia/Kolkata")

log = get_logger("IronCondorStrategy")


class IronCondorStrategy(BaseOptionsStrategy):
    """Weekly NIFTY Iron Condor — enter Mon/Tue, profit from range-bound week."""

    def generate_signal(self, hub_snapshot: Dict) -> Optional[OptionsSignal]:
        index = self.bot_config.get("instruments", ["NIFTY"])[0]
        vix   = hub_snapshot.get("vix")
        max_vix = self.bot_config.get("vix_max", 15.0)

        # VIX safety check
        if not self.is_vix_safe(vix, max_vix):
            return None

        # Day filter: only enter on Monday or Tuesday (IST)
        now = datetime.now(IST)
        allowed_days = self.bot_config.get("entry_days", ["Monday", "Tuesday"])
        current_day = now.strftime("%A")
        if current_day not in allowed_days:
            log.debug("%s: Not an entry day (%s). Iron Condor skipped.", self.bot_id, current_day)
            return None

        # Only enter once per day (morning session before 11:30 AM IST)
        if now.hour > 11 or (now.hour == 11 and now.minute > 30):
            log.debug("%s: Past entry window for Iron Condor.", self.bot_id)
            return None

        # Get ATM
        atm = hub_snapshot.get("atm_strikes", {}).get(index)
        if not atm:
            return None

        interval = 100  # NIFTY spread width
        options  = hub_snapshot.get("options", {})

        # Strikes
        call_sell_strike = atm + interval
        call_buy_strike  = atm + (interval * 2)
        put_sell_strike  = atm - interval
        put_buy_strike   = atm - (interval * 2)

        def get_ltp_and_token(strike, otype):
            entry = options.get(f"{index}_{strike}_{otype}", {})
            return entry.get("ltp"), entry.get("token", "")

        cs_ltp, cs_tok = get_ltp_and_token(call_sell_strike, "CE")
        cb_ltp, cb_tok = get_ltp_and_token(call_buy_strike,  "CE")
        ps_ltp, ps_tok = get_ltp_and_token(put_sell_strike,  "PE")
        pb_ltp, pb_tok = get_ltp_and_token(put_buy_strike,   "PE")

        if not all([cs_ltp, cb_ltp, ps_ltp, pb_ltp]):
            log.warning("%s: Some Iron Condor legs have no LTP — skipping.", self.bot_id)
            return None

        net_premium = (cs_ltp - cb_ltp) + (ps_ltp - pb_ltp)
        max_loss    = (interval - net_premium) * self.get_lot_size(index) * self.lots

        if net_premium <= 0:
            log.warning("%s: Net premium <= 0 (%.1f) — skipping condor.", self.bot_id, net_premium)
            return None

        target_premium = net_premium * (1 - self.bot_config.get("target_pct_of_max_profit", 50) / 100)
        sl_premium     = net_premium * (1 + self.bot_config.get("sl_pct_of_max_loss", 100) / 100)

        log.info("%s: IRON CONDOR %s | ATM=%d | Net Premium=%.1f | MaxLoss=%.0f",
                 self.bot_id, index, atm, net_premium, max_loss)

        return OptionsSignal(
            bot_id=self.bot_id,
            strategy=self.name,
            signal_type="iron_condor",
            index=index,
            atm_strike=atm,
            ce_strike=call_sell_strike,
            pe_strike=put_sell_strike,
            ce_token=cs_tok,
            pe_token=ps_tok,
            ce_entry_price=cs_ltp,
            pe_entry_price=ps_ltp,
            total_premium=net_premium,
            sl_premium=sl_premium,
            target_premium=target_premium,
            lot_size=self.get_lot_size(index),
            lots=self.lots,
            direction="SELL",
            confidence=0.75,
            notes=f"VIX={vix} CallSpread={call_sell_strike}/{call_buy_strike} PutSpread={put_sell_strike}/{put_buy_strike}",
        )
