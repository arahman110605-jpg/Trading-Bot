"""
engine/risk_manager.py — Position sizing, daily loss limits, and trade validation.
"""

from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime, timedelta

import pytz

import config
from utils.logger import get_logger
from utils.trade_journal import TradeJournal
from strategies.base_strategy import Signal

log = get_logger("RiskManager")

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> datetime:
    """Return current time in IST (works correctly on Render/UTC servers)."""
    return datetime.now(IST)


class RiskManager:
    """
    Validates trades against risk rules and computes position sizes.
    Also enforces daily loss limits and auto square-off time.
    """

    def __init__(self, journal: TradeJournal, capital: float = None):
        self.journal   = journal
        self.initial_capital = capital if capital is not None else config.CAPITAL
        self.max_risk_per_trade = config.RISK_PER_TRADE_PCT / 100
        self.max_daily_loss     = getattr(config, "MAX_DAILY_LOSS_PCT", 2.0) / 100
        self.max_open_positions = config.MAX_OPEN_POSITIONS
        self.max_trades_per_day = getattr(config, "MAX_TRADES_PER_DAY", 5)
        self.min_rr             = config.REWARD_TO_RISK_RATIO
        self._daily_loss_hit    = False
        self._last_reset_date: Optional[str] = None   # tracks which date we last reset
        log.info(
            "RiskManager | initial_capital=INR %s | risk/trade=%.1f%% | max_daily_loss=%.1f%%",
            f"{self.initial_capital:,}", config.RISK_PER_TRADE_PCT, config.MAX_DAILY_LOSS_PCT
        )

    def get_current_capital(self) -> float:
        """Returns dynamically compounding capital from all historical trades."""
        return self.initial_capital + self.journal.get_total_pnl()

    # ── Auto Daily Reset ─────────────────────────────────────────────────────

    def _auto_reset_if_new_day(self):
        """Automatically reset daily counters at the start of each new trading day."""
        today = _now_ist().strftime("%Y-%m-%d")
        if self._last_reset_date != today:
            self.reset_daily()
            self._last_reset_date = today

    # ── Checks ───────────────────────────────────────────────────────────────

    def is_market_open(self) -> bool:
        """Check if within trading hours (9:15 AM – 3:15 PM IST)."""
        now = _now_ist()
        # Skip weekends
        if now.weekday() >= 5:
            return False
        open_time  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
        close_time = now.replace(
            hour=config.SQUARE_OFF_HOUR,
            minute=config.SQUARE_OFF_MINUTE,
            second=0,
            microsecond=0,
        )
        return open_time <= now <= close_time

    def is_new_entry_allowed(self) -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Checks:
          1. Market is open
          2. Daily loss limit not hit
          3. Max open positions not exceeded
          4. Max daily trades not exceeded
          5. Not within 30 min of square-off
          6. Not in the midday no-trade window (11:30–13:30)
        """
        # Auto-reset daily counters if it's a new day
        self._auto_reset_if_new_day()

        if not self.is_market_open():
            return False, "Market is closed"

        if self._daily_loss_hit:
            return False, "Daily loss limit hit — bot paused"

        # Check daily P&L
        daily_pnl = self.journal.get_todays_pnl()
        current_capital = self.get_current_capital()
        max_loss  = -current_capital * self.max_daily_loss
        if daily_pnl <= max_loss:
            self._daily_loss_hit = True
            log.warning("Daily loss limit reached! P&L=INR %.2f | Limit=INR %.2f", daily_pnl, max_loss)
            return False, f"Daily loss INR {abs(daily_pnl):.2f} exceeded limit INR {abs(max_loss):.2f}"

        # Check open positions
        open_trades = self.journal.get_open_trades()
        if len(open_trades) >= self.max_open_positions:
            return False, f"Max open positions ({self.max_open_positions}) reached"

        # Check total trades for the day
        todays_trades = self.journal.get_todays_trades()
        if len(todays_trades) >= self.max_trades_per_day:
            return False, f"Max trades per day ({self.max_trades_per_day}) reached"

        now = _now_ist()

        # Time-of-day filter: block midday lull window (11:30 AM – 1:30 PM)
        no_trade_start = now.replace(
            hour=config.NO_TRADE_START_HOUR, minute=config.NO_TRADE_START_MIN,
            second=0, microsecond=0
        )
        no_trade_end = now.replace(
            hour=config.NO_TRADE_END_HOUR, minute=config.NO_TRADE_END_MIN,
            second=0, microsecond=0
        )
        if no_trade_start <= now <= no_trade_end:
            return False, "Midday lull window (11:30–13:30) — no new entries"

        # No new entries within 30 min of square-off
        sq_off = now.replace(
            hour=config.SQUARE_OFF_HOUR,
            minute=config.SQUARE_OFF_MINUTE,
            second=0,
            microsecond=0,
        )
        cutoff = sq_off - timedelta(minutes=30)
        if now >= cutoff:
            return False, f"Too close to square-off time ({cutoff.strftime('%H:%M')} IST cutoff)"

        return True, "OK"

    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate a trading signal before acting on it.
        Returns (valid: bool, reason: str).
        """
        if not signal.is_actionable:
            return False, "No signal"

        # Check minimum confidence threshold
        if signal.confidence < config.MIN_SIGNAL_CONFIDENCE:
            return False, f"Confidence {signal.confidence:.0%} below minimum {config.MIN_SIGNAL_CONFIDENCE:.0%}"

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
        current_capital = self.get_current_capital()
        risk_amount = current_capital * self.max_risk_per_trade
        risk_per_share = abs(signal.entry_price - signal.stop_loss)

        if risk_per_share <= 0:
            log.warning("Risk per share is 0 for %s — skipping", signal.symbol)
            return 0

        qty = int(risk_amount / risk_per_share)
        qty = max(1, qty)

        # Safety: don't put more than 20% of capital in one trade
        max_qty = int((current_capital * 0.20) / signal.entry_price)
        qty = min(qty, max(1, max_qty))

        log.info(
            "Position size | %s | qty=%d | risk=INR %.2f | risk/share=%.2f",
            signal.symbol, qty, risk_amount, risk_per_share
        )
        return qty

    def should_square_off_all(self) -> bool:
        """Return True if it's time to force close all positions."""
        now = _now_ist()
        sq_off = now.replace(
            hour=config.SQUARE_OFF_HOUR,
            minute=config.SQUARE_OFF_MINUTE,
            second=0,
            microsecond=0,
        )
        return now >= sq_off

    def reset_daily(self):
        """Reset daily loss flag at market open."""
        self._daily_loss_hit = False
        log.info("Daily risk counters reset for new trading day.")
