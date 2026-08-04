"""
engine/order_manager.py — Manages the lifecycle of all trades.

Handles:
  - Placing entry orders
  - Placing stop-loss orders
  - Monitoring open positions against SL/Target
  - Square-off at end of day
"""

from __future__ import annotations

from typing import Dict, List, Optional
import threading
import time

import config
from broker.kite_client import KiteClient
from engine.risk_manager import RiskManager
from strategies.base_strategy import Signal
from utils.trade_journal import TradeJournal
from utils.logger import get_logger

log = get_logger("OrderManager")


class OpenPosition:
    """Tracks an open intraday position."""

    def __init__(
        self,
        trade_id: int,
        symbol: str,
        direction: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        order_id: str,
        strategy: str,
    ):
        self.trade_id    = trade_id
        self.symbol      = symbol
        self.direction   = direction
        self.quantity    = quantity
        self.entry_price = entry_price
        self.stop_loss   = stop_loss
        self.target      = target
        self.order_id    = order_id
        self.strategy    = strategy
        self.current_price = entry_price
        self.trailing_sl: Optional[float] = None

    @property
    def unrealised_pnl(self) -> float:
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    def to_dict(self) -> dict:
        return {
            "trade_id":    self.trade_id,
            "symbol":      self.symbol,
            "direction":   self.direction,
            "quantity":    self.quantity,
            "entry_price": self.entry_price,
            "stop_loss":   self.stop_loss,
            "target":      self.target,
            "current_price": self.current_price,
            "unrealised_pnl": round(self.unrealised_pnl, 2),
            "strategy":    self.strategy,
        }


class OrderManager:
    """Central order and position manager."""

    def __init__(self, kite: KiteClient, risk: RiskManager, journal: TradeJournal):
        self.kite    = kite
        self.risk    = risk
        self.journal = journal
        self.open_positions: Dict[str, OpenPosition] = {}  # symbol → position
        self._lock = threading.Lock()

    # ── Entry ────────────────────────────────────────────────────────────────

    def execute_signal(self, signal: Signal) -> bool:
        """
        Validate and execute a trading signal.
        Returns True if order was placed successfully.
        """
        # 1. Check risk manager
        allowed, reason = self.risk.is_new_entry_allowed()
        if not allowed:
            log.debug("Entry blocked (%s): %s", signal.symbol, reason)
            return False

        valid, reason = self.risk.validate_signal(signal)
        if not valid:
            log.debug("Signal rejected (%s): %s", signal.symbol, reason)
            return False

        # 2. Compute quantity
        qty = self.risk.compute_quantity(signal)
        if qty <= 0:
            log.warning("Zero quantity computed for %s — skipping", signal.symbol)
            return False

        # 3. Place entry order
        log.info("→ Placing %s order | %s x%d @ %.2f | SL=%.2f | TGT=%.2f",
                 signal.direction, signal.symbol, qty, signal.entry_price,
                 signal.stop_loss, signal.target)

        order_id = self.kite.place_market_order(
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=qty,
        )
        if not order_id:
            log.error("Order placement failed for %s", signal.symbol)
            return False

        # 4. Log to journal
        trade_id = self.journal.log_entry(
            symbol=signal.symbol,
            exchange=config.DEFAULT_EXCHANGE,
            direction=signal.direction,
            quantity=qty,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            strategy=signal.strategy,
            order_id=order_id,
        )

        # 5. Track position
        pos = OpenPosition(
            trade_id=trade_id,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=qty,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            order_id=order_id,
            strategy=signal.strategy,
        )
        with self._lock:
            self.open_positions[signal.symbol] = pos

        log.info("✓ Trade opened | id=%d | %s %s x%d", trade_id, signal.direction, signal.symbol, qty)
        return True

    # ── Position Monitoring ──────────────────────────────────────────────────

    def update_position_price(self, symbol: str, ltp: float):
        """Update the current price for a position and check SL/Target."""
        with self._lock:
            pos = self.open_positions.get(symbol)
        if not pos:
            return

        pos.current_price = ltp

        # Check stop-loss
        sl_hit = False
        if pos.direction == "BUY"  and ltp <= pos.stop_loss:
            sl_hit = True
        if pos.direction == "SELL" and ltp >= pos.stop_loss:
            sl_hit = True

        if sl_hit:
            log.warning("⚠ STOP LOSS HIT | %s @ %.2f | SL was %.2f", symbol, ltp, pos.stop_loss)
            self._close_position(symbol, ltp, "SL_HIT")
            return

        # Check target
        tgt_hit = False
        if pos.direction == "BUY"  and ltp >= pos.target:
            tgt_hit = True
        if pos.direction == "SELL" and ltp <= pos.target:
            tgt_hit = True

        if tgt_hit:
            log.info("🎯 TARGET HIT | %s @ %.2f | TGT was %.2f", symbol, ltp, pos.target)
            self._close_position(symbol, ltp, "TARGET_HIT")
            return

    def _close_position(self, symbol: str, exit_price: float, status: str):
        """Close a position and log the exit."""
        with self._lock:
            pos = self.open_positions.pop(symbol, None)
        if not pos:
            return

        # Place exit order
        exit_dir = "SELL" if pos.direction == "BUY" else "BUY"
        exit_id  = self.kite.place_market_order(
            symbol=symbol,
            direction=exit_dir,
            quantity=pos.quantity,
        )

        # Log exit
        self.journal.log_exit(
            trade_id=pos.trade_id,
            exit_price=exit_price,
            status=status,
            exit_order_id=exit_id or "",
        )
        pnl = pos.unrealised_pnl
        log.info("✓ Position closed | %s | status=%s | P&L=₹%.2f", symbol, status, pnl)

    # ── Square-Off ───────────────────────────────────────────────────────────

    def square_off_all(self):
        """Close all open positions (end of day)."""
        with self._lock:
            symbols = list(self.open_positions.keys())

        if not symbols:
            log.info("No open positions to square off.")
            return

        log.info("🔔 Square-off initiated for %d positions", len(symbols))
        for symbol in symbols:
            pos = self.open_positions.get(symbol)
            if pos:
                ltp = self.kite.get_ltp(symbol) or pos.current_price
                self._close_position(symbol, ltp, "SQUARED_OFF")

    # ── State ────────────────────────────────────────────────────────────────

    def get_open_positions(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self.open_positions.values()]

    def get_position(self, symbol: str) -> Optional[OpenPosition]:
        with self._lock:
            return self.open_positions.get(symbol)
