"""
engine/options_runner.py — Per-bot options strategy runner.

Runs an options strategy every scan cycle.
Reads market data from the shared MarketDataHub.
All trades are paper trades (mode='paper') by default.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable

import config
from engine.market_data_hub import MarketDataHub
from strategies.options.base_options_strategy import BaseOptionsStrategy, OptionsSignal
from utils.analytics_logger import AnalyticsLogger
from utils.logger import get_logger

log = get_logger("OptionsRunner")


import pytz

IST = pytz.timezone("Asia/Kolkata")


class OptionsRunner:
    """Executes a single options strategy using the shared hub's data."""

    def __init__(
        self,
        bot_cfg: Dict[str, Any],
        strategy: BaseOptionsStrategy,
        hub: MarketDataHub,
        on_update: Optional[Callable] = None,
    ):
        self.bot_id   = bot_cfg["bot_id"]
        self.cfg      = bot_cfg
        self.strategy = strategy
        self.hub      = hub
        self.on_update = on_update
        self._running = False

        os.environ["BOT_ID"] = self.bot_id
        self.analytics = AnalyticsLogger()

        self._active_signal: Optional[OptionsSignal] = None
        self._trades_today = 0
        self._daily_pnl = 0.0

        log.info("%s: OptionsRunner ready | strategy=%s", self.bot_id, strategy.name)

    def run(self):
        """Main options bot loop."""
        self._running = True
        log.info("%s: Options bot loop started.", self.bot_id)

        from engine.strategy_runner import INTERVAL_SECONDS
        interval_sec = INTERVAL_SECONDS.get(config.CANDLE_INTERVAL, 300)

        while self._running:
            try:
                now = datetime.now(IST)

                # Skip weekends
                if now.weekday() >= 5:
                    time.sleep(30)
                    continue

                # Market hours (9:15 AM - 3:30 PM IST)
                if not (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30)):
                    time.sleep(30)
                    continue

                # Build hub snapshot for options strategies
                hub_snapshot = {
                    "atm_strikes":      {k: self.hub.get_atm_strike(k) for k in ["NIFTY", "BANKNIFTY"]},
                    "index_ltp":        {k: self.hub.get_index_ltp(k) for k in ["NIFTY", "BANKNIFTY"]},
                    "options":          self.hub.get_options_snapshot(),
                    "vix":              self.hub.get_vix(),
                    "consensus_signal": self._get_consensus_direction(),
                    "consensus_symbol": "NIFTY",
                    "market_trend":     self.hub.get_market_trend(),
                }

                # Check exit conditions for active position
                if self._active_signal:
                    self._check_exit(hub_snapshot)

                # Try to enter a new position if none active
                if not self._active_signal:
                    try:
                        sig = self.strategy.generate_signal(hub_snapshot)
                        if sig:
                            self._active_signal = sig
                            self._trades_today += 1
                            log.info("%s: OPTIONS SIGNAL | %s %s | Premium=%.1f | SL=%.1f | Target=%.1f",
                                     self.bot_id, sig.direction, sig.index, sig.total_premium,
                                     sig.sl_premium, sig.target_premium)
                            # Log to Analytics & Journal
                            self._log_signal(sig)
                    except Exception as e:
                        log.error("%s: Strategy error: %s", self.bot_id, e)

                if self.on_update:
                    self.on_update()

            except Exception as e:
                log.error("%s: Error in options loop: %s", self.bot_id, e, exc_info=True)

            time.sleep(interval_sec)

    def _check_exit(self, hub_snapshot: Dict):
        """Check if active options position should be exited."""
        sig = self._active_signal
        if not sig:
            return

        # Get current combined premium
        options = hub_snapshot.get("options", {})
        ce_ltp = options.get(f"{sig.index}_{sig.ce_strike}_CE", {}).get("ltp", sig.ce_entry_price)
        pe_ltp = options.get(f"{sig.index}_{sig.pe_strike}_PE", {}).get("ltp", sig.pe_entry_price)

        if sig.direction == "SELL":
            current_premium = ce_ltp + pe_ltp
            # Exit if SL hit (premium rose too much) or target hit (decayed enough)
            if current_premium >= sig.sl_premium:
                pnl = (sig.total_premium - current_premium) * sig.lot_size * sig.lots
                log.warning("%s: SL HIT | Premium %.1f >= SL %.1f | PnL=%.0f",
                            self.bot_id, current_premium, sig.sl_premium, pnl)
                self._close_position(pnl, "SL_HIT", exit_price=current_premium)
            elif current_premium <= sig.target_premium:
                pnl = (sig.total_premium - current_premium) * sig.lot_size * sig.lots
                log.info("%s: TARGET HIT | Premium %.1f <= Target %.1f | PnL=%.0f",
                         self.bot_id, current_premium, sig.target_premium, pnl)
                self._close_position(pnl, "TARGET_HIT", exit_price=current_premium)

        elif "buy" in sig.direction.lower():
            # For bought options: apply active multi-stage profit protection & asymmetric expansion
            current_ltp = ce_ltp if "ce" in sig.direction.lower() else pe_ltp
            entry_p = sig.total_premium
            gain_pct = ((current_ltp - entry_p) / entry_p) if entry_p > 0 else 0.0

            # 1. Profit Protection: at +40% gain -> Lock entry + 10% green buffer
            if gain_pct >= 0.40:
                locked_sl = round(entry_p * 1.10, 2)
                if locked_sl > sig.sl_premium:
                    sig.sl_premium = locked_sl
                    log.info("[%s] Options Profit Protection: SL locked at %.2f (+10%% green buffer)", self.bot_id, locked_sl)

            # 2. Asymmetric Expansion: at +100% gain -> Expand TP to +200% & Tighten SL to +60%
            if gain_pct >= 1.00:
                expanded_tp = round(entry_p * 3.00, 2)
                tightened_sl = round(entry_p * 1.60, 2)
                if expanded_tp > sig.target_premium:
                    sig.target_premium = expanded_tp
                    sig.sl_premium = max(sig.sl_premium, tightened_sl)
                    log.info("[%s] Options Asymmetric Expansion! Target expanded to %.2f (+200%%), SL tightened to %.2f",
                             self.bot_id, expanded_tp, tightened_sl)

            if current_ltp <= sig.sl_premium:
                pnl = (current_ltp - sig.total_premium) * sig.lot_size * sig.lots
                log.warning("%s: SL / TRAILING HIT | LTP %.1f <= SL %.1f | PnL=%.0f",
                            self.bot_id, current_ltp, sig.sl_premium, pnl)
                self._close_position(pnl, "SL_HIT", exit_price=current_ltp)
            elif current_ltp >= sig.target_premium:
                pnl = (current_ltp - sig.total_premium) * sig.lot_size * sig.lots
                log.info("%s: TARGET HIT | LTP %.1f >= Target %.1f | PnL=%.0f",
                         self.bot_id, current_ltp, sig.target_premium, pnl)
                self._close_position(pnl, "TARGET_HIT", exit_price=current_ltp)

        # Force exit at 3:00 PM IST
        now = datetime.now(IST)
        exit_time = self.cfg.get("exit_time", "15:00")
        exit_h, exit_m = map(int, exit_time.split(":"))
        if now.hour > exit_h or (now.hour == exit_h and now.minute >= exit_m):
            log.info("%s: EOD EXIT — squaring off options position.", self.bot_id)
            current_ltp = ce_ltp if "ce" in sig.direction.lower() else pe_ltp
            pnl = (current_ltp - sig.total_premium) * sig.lot_size * sig.lots if "buy" in sig.direction.lower() else 0.0
            self._close_position(pnl, "EOD_SQUAREOFF", exit_price=current_ltp)

    def _close_position(self, pnl: float, reason: str, exit_price: float = 0.0):
        self._daily_pnl += pnl
        log.info("%s: Position closed | reason=%s | pnl=%.0f | daily_pnl=%.0f",
                 self.bot_id, reason, pnl, self._daily_pnl)
        if self._active_signal and hasattr(self, "_active_trade_id") and self._active_trade_id:
            try:
                from utils.trade_journal import TradeJournal
                journal = TradeJournal()
                journal.log_exit(
                    trade_id=self._active_trade_id,
                    exit_price=exit_price or self._active_signal.total_premium,
                    status=reason,
                )
            except Exception as e:
                log.debug("Options trade exit journal logging: %s", e)
        self._active_signal = None
        self._active_trade_id = None

    def _get_consensus_direction(self) -> Optional[str]:
        """Read the latest direction from Bot 01 via shared MarketDataHub."""
        direction, _ = self.hub.get_consensus_signal()
        return direction

    def _log_signal(self, sig: OptionsSignal):
        try:
            self.analytics.log_signal_telemetry(
                symbol=f"{sig.index}_OPT",
                strategy=sig.strategy,
                direction=sig.direction,
                confidence=sig.confidence,
                entry_price=sig.total_premium,
                stop_loss=sig.sl_premium,
                target=sig.target_premium,
                rr_ratio=0.0,
                was_executed=True,
                rejection_reason="",
                notes=sig.notes,
            )
            from utils.trade_journal import TradeJournal
            journal = TradeJournal()
            strike = sig.ce_strike if "ce" in sig.direction.lower() else sig.pe_strike
            opt_type = "CE" if "ce" in sig.direction.lower() else "PE"
            trade_id = journal.log_entry(
                symbol=f"{sig.index}_{strike}_{opt_type}",
                exchange="NFO",
                direction=sig.direction,
                quantity=sig.lot_size * sig.lots,
                entry_price=sig.total_premium,
                stop_loss=sig.sl_premium,
                target=sig.target_premium,
                strategy=sig.strategy,
                bot_id=self.bot_id,
            )
            self._active_trade_id = trade_id
        except Exception as e:
            log.error("%s: Failed to log options signal: %s", self.bot_id, e)

    def get_open_positions(self) -> List[Dict]:
        sig = self._active_signal
        if not sig:
            return []
        options = self.hub.get_options_snapshot()
        strike = sig.ce_strike if "ce" in sig.direction.lower() else sig.pe_strike
        opt_type = "CE" if "ce" in sig.direction.lower() else "PE"
        cur_ltp = options.get(f"{sig.index}_{strike}_{opt_type}", {}).get("ltp", sig.total_premium)
        if "buy" in sig.direction.lower():
            unrealised = (cur_ltp - sig.total_premium) * sig.lot_size * sig.lots
        else:
            unrealised = (sig.total_premium - cur_ltp) * sig.lot_size * sig.lots
        return [{
            "trade_id": getattr(self, "_active_trade_id", None) or f"{self.bot_id}_opt",
            "symbol": f"{sig.index} {strike} {opt_type}",
            "direction": sig.direction,
            "quantity": sig.lot_size * sig.lots,
            "entry_price": sig.total_premium,
            "current_price": cur_ltp,
            "stop_loss": sig.sl_premium,
            "target": sig.target_premium,
            "unrealised_pnl": round(unrealised, 2),
            "strategy": sig.strategy,
            "state": "ACTIVE",
        }]

    def stop(self):
        self._running = False

    def get_status(self) -> Dict:
        return {
            "bot_id":       self.bot_id,
            "name":         self.cfg.get("name", self.bot_id),
            "type":         "options",
            "total_trades": self._trades_today,
            "open_positions_count": 1 if self._active_signal else 0,
            "pnl":          self._daily_pnl,
            "strategy":     self.strategy.name,
            "capital":      self.cfg.get("capital", 100000),
            "active":       self._active_signal is not None,
        }
