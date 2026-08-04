"""
engine/risk_manager.py — Position sizing, daily loss limits, and trade validation.
"""

from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime

import config
from utils.logger import get_logger
from utils.trade_journal import TradeJournal
from strategies.base_strategy import Signal

log = get_logger("RiskManager")


class RiskManager:
    """
    Validates trades against risk rules and computes position sizes.
    Also enforces daily loss limits and auto square-off time.
    """

    def __init__(self, journal: TradeJournal):
        self.journal   = journal
        self.capital   = config.CAPITAL
        self.max_risk_per_trade = config.RISK_PER_TRADE_PCT / 100
        self.max_daily_loss     = config.MAX_DAILY_LOSS_PCT / 100
        self.max_open_positions = config.MAX_OPEN_POSITIONS
        self.min_rr             = config.REWARD_TO_RISK_RATIO
        self._daily_loss_hit    = False
        log.info(
            "RiskManager | capital=INR %s | risk/trade=%.1f%% | max_daily_loss=%.1f%%",
            f"{self.capital:,}", config.RISK_PER_TRADE_PCT, config.MAX_DAILY_LOSS_PCT
        )

    # ── Checks ───────────────────────────────────────────────────────────────

    def is_market_open(self) -> bool:
        """Check if within trading hours (9:15 AM – 3:15 PM IST)."""
        now = datetime.now()
        # Skip weekends
        if now.weekday() >= 5:
            return False
        open_time  = now.replace(hour=9,  minute=15, second=0)
        close_time = now.replace(
            hour=config.SQUARE_OFF_HOUR,
            minute=config.SQUARE_OFF_MINUTE,
            second=0,
        )
        return open_time <= now <= close_time

    def is_new_entry_allowed(self) -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Checks:
          1. Market is open
          2. Daily loss limit not hit
          3. Max open positions not exceeded
          4. Not too close to square-off time
        """
        if not self.is_market_open():
            return False, "Market is closed"

        if self._daily_loss_hit:
            return False, "Daily loss limit hit — bot paused"

        # Check daily P&L
        daily_pnl = self.journal.get_todays_pnl()
        max_loss  = -self.capital * self.max_daily_loss
        if daily_pnl <= max_loss:
            self._daily_loss_hit = True
            log.warning("‼ Daily loss limit reached! P&L=₹%.2f | Limit=₹%.2f", daily_pnl, max_loss)
            return False, f"Daily loss ₹{abs(daily_pnl):.2f} exceeded limit ₹{abs(max_loss):.2f}"

        # Check open positions
        open_trades = self.journal.get_open_trades()
        if len(open_trades) >= self.max_open_positions:
            return False, f"Max open positions ({self.max_open_positions}) reached"

        # Don't open new trades within 30 min of square-off
        now = datetime.now()
        no_new_entry_after = now.replace(
            hour=config.SQUARE_OFF_HOUR - 1 if config.SQUARE_OFF_MINUTE < 30 else config.SQUARE_OFF_HOUR,
            minute=(config.SQUARE_OFF_MINUTE + 30) % 60 if config.SQUARE_OFF_MINUTE < 30 else (config.SQUARE_OFF_MINUTE - 30),
            second=0,
        )
        # Simple approach: no new entries after 2:45 PM
        cutoff = now.replace(hour=14, minute=45, second=0)
        if now >= cutoff:
            return False, "Too close to square-off time (2:45 PM cutoff)"

        return True, "OK"

    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate a trading signal before acting on it.
        Returns (valid: bool, reason: str).
        """
        if not signal.is_actionable:
            return False, "No signal"

        # Check R:R ratio
        if signal.rr_ratio < self.min_rr:
            return False, f"R:R {signal.rr_ratio} below minimum {self.min_rr}"

        # Check if already in a position for this symbol
        open_trades = self.journal.get_open_trades()
        symbols_in  = {t["symbol"] for t in open_trades}
        if signal.symbol in symbols_in:
            return False, f"Already have open position in {signal.symbol}"

        return True, "OK"

    # ── Position Sizing ──────────────────────────────────────────────────────

    def compute_quantity(self, signal: Signal) -> int:
        """
        Compute share quantity based on fixed risk %.
        Risk amount = capital × risk_per_trade%
        Quantity    = risk_amount / (entry - stop_loss)
        """
        risk_amount = self.capital * self.max_risk_per_trade
        risk_per_share = abs(signal.entry_price - signal.stop_loss)

        if risk_per_share <= 0:
            log.warning("Risk per share is 0 for %s — skipping", signal.symbol)
            return 0

        qty = int(risk_amount / risk_per_share)

        # Minimum 1 share
        qty = max(1, qty)

        # Safety: don't put more than 20% of capital in one trade
        max_qty = int((self.capital * 0.20) / signal.entry_price)
        qty = min(qty, max_qty)

        log.info(
            "Position size | %s | qty=%d | risk=₹%.2f | risk/share=%.2f",
            signal.symbol, qty, risk_amount, risk_per_share
        )
        return qty

    def should_square_off_all(self) -> bool:
        """Return True if it's time to force close all positions."""
        now = datetime.now()
        sq_off = now.replace(
            hour=config.SQUARE_OFF_HOUR,
            minute=config.SQUARE_OFF_MINUTE,
            second=0,
        )
        return now >= sq_off

    def reset_daily(self):
        """Reset daily loss flag at market open."""
        self._daily_loss_hit = False
        log.info("Daily risk counters reset.")
