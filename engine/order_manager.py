"""
engine/order_manager.py — Manages the lifecycle of all trades.

Handles:
  - Placing entry orders
  - Monitoring open positions against SL/Target
  - Trailing Stop-Loss (moves SL to breakeven at 50% of target)
  - Partial profit booking (books 50% at 1:1 R:R)
  - Square-off at end of day
"""

from __future__ import annotations

from typing import Dict, List, Optional
import threading
import time

import config
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
        self.trade_id      = trade_id
        self.symbol        = symbol
        self.direction     = direction
        self.quantity      = quantity
        self.entry_price   = entry_price
        self.stop_loss     = stop_loss
        self.initial_sl    = stop_loss          # Original SL — never changes
        self.target        = target
        self.order_id      = order_id
        self.strategy      = strategy
        self.current_price = entry_price
        self.trailing_sl   = stop_loss          # Starts at original SL; updated as trade profits
        self.breakeven_set = False              # True once SL has been moved to breakeven
        self.partial_booked = False             # True once 50% of position is booked at 1:1

    @property
    def risk(self) -> float:
        return abs(self.entry_price - self.initial_sl)

    @property
    def unrealised_pnl(self) -> float:
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    def to_dict(self) -> dict:
        return {
            "trade_id":     self.trade_id,
            "symbol":       self.symbol,
            "direction":    self.direction,
            "quantity":     self.quantity,
            "entry_price":  self.entry_price,
            "stop_loss":    self.trailing_sl,   # Show current (trailing) SL
            "target":       self.target,
            "current_price": self.current_price,
            "unrealised_pnl": round(self.unrealised_pnl, 2),
            "strategy":     self.strategy,
            "breakeven_set": self.breakeven_set,
        }


class OrderManager:
    """Central order and position manager."""

    def __init__(self, kite, risk: RiskManager, journal: TradeJournal, bot_id: str = ""):
        self.kite    = kite
        self.risk    = risk
        self.journal = journal
        self.bot_id  = bot_id
        self.open_positions: Dict[str, OpenPosition] = {}  # symbol → position
        self._lock = threading.Lock()

        # Hydrate open positions from journal (for state recovery after restarts)
        open_trades = self.journal.get_open_trades(bot_id=self.bot_id)
        for t in open_trades:
            self.open_positions[t["symbol"]] = OpenPosition(
                trade_id=t.get("id") or t.get("trade_id"), # Handle SQLite and Firebase
                symbol=t["symbol"],
                direction=t["direction"],
                quantity=t["quantity"],
                entry_price=t["entry_price"],
                stop_loss=t["stop_loss"],
                target=t["target"],
                order_id=t.get("order_id", ""),
                strategy=t.get("strategy", ""),
            )
        if self.open_positions:
            log.info("Recovered %d open positions from trade journal.", len(self.open_positions))

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
        log.info("-> Placing %s order | %s x%d @ %.2f | SL=%.2f | TGT=%.2f",
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

        # 4. Use LTP at fill time as actual entry price (avoids market order slippage)
        actual_entry = self.kite.get_ltp(signal.symbol) or signal.entry_price
        # Recalculate SL and target relative to actual fill price
        sl_dist  = abs(signal.entry_price - signal.stop_loss)
        tgt_dist = abs(signal.target - signal.entry_price)
        if signal.direction == "BUY":
            actual_sl  = actual_entry - sl_dist
            actual_tgt = actual_entry + tgt_dist
        else:
            actual_sl  = actual_entry + sl_dist
            actual_tgt = actual_entry - tgt_dist

        # 5. Log to journal
        trade_id = self.journal.log_entry(
            symbol=signal.symbol,
            exchange=config.DEFAULT_EXCHANGE,
            direction=signal.direction,
            quantity=qty,
            entry_price=actual_entry,
            stop_loss=actual_sl,
            target=actual_tgt,
            strategy=signal.strategy,
            order_id=order_id,
            bot_id=self.bot_id,
        )

        # 6. Track position
        pos = OpenPosition(
            trade_id=trade_id,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=qty,
            entry_price=actual_entry,
            stop_loss=actual_sl,
            target=actual_tgt,
            order_id=order_id,
            strategy=signal.strategy,
        )
        with self._lock:
            self.open_positions[signal.symbol] = pos

        log.info("Trade opened | id=%d | %s %s x%d @ %.2f | SL=%.2f | TGT=%.2f",
                 trade_id, signal.direction, signal.symbol, qty,
                 actual_entry, actual_sl, actual_tgt)
        return True

    # ── Position Monitoring ──────────────────────────────────────────────────

    def update_position_price(self, symbol: str, ltp: float):
        """Update current price, apply trailing SL logic, and check SL/Target."""
        with self._lock:
            pos = self.open_positions.get(symbol)
        if not pos:
            return

        pos.current_price = ltp
        risk = pos.risk  # Original risk distance

        # ── Trailing SL Logic ─────────────────────────────────────────────────
        # +1.0R profit -> Move SL to Breakeven (+0.0R)
        # +1.5R profit -> Move SL to Lock Profit (+0.75R)
        # +1.8R profit -> Move SL to Lock Profit (+1.2R)
        if pos.direction == "BUY":
            one_r_level   = pos.entry_price + (risk * 1.0)
            one_half_r    = pos.entry_price + (risk * 1.5)
            one_eight_r   = pos.entry_price + (risk * 1.8)

            if not pos.breakeven_set and ltp >= one_r_level:
                pos.trailing_sl = pos.entry_price  # Move SL to breakeven
                pos.breakeven_set = True
                log.info("Trailing SL: Moved to BREAKEVEN for %s @ %.2f (LTP=%.2f)", symbol, pos.entry_price, ltp)
            elif pos.breakeven_set and ltp >= one_eight_r:
                new_tsl = round(pos.entry_price + (risk * 1.2), 2)
                if new_tsl > pos.trailing_sl:
                    pos.trailing_sl = new_tsl
                    log.info("Trailing SL: Locked +1.2R Profit @ %.2f for %s", new_tsl, symbol)
            elif pos.breakeven_set and ltp >= one_half_r:
                new_tsl = round(pos.entry_price + (risk * 0.75), 2)
                if new_tsl > pos.trailing_sl:
                    pos.trailing_sl = new_tsl
                    log.info("Trailing SL: Locked +0.75R Profit @ %.2f for %s", new_tsl, symbol)

        else:  # SELL position
            one_r_level   = pos.entry_price - (risk * 1.0)
            one_half_r    = pos.entry_price - (risk * 1.5)
            one_eight_r   = pos.entry_price - (risk * 1.8)

            if not pos.breakeven_set and ltp <= one_r_level:
                pos.trailing_sl = pos.entry_price
                pos.breakeven_set = True
                log.info("Trailing SL: Moved to BREAKEVEN for %s @ %.2f (LTP=%.2f)", symbol, pos.entry_price, ltp)
            elif pos.breakeven_set and ltp <= one_eight_r:
                new_tsl = round(pos.entry_price - (risk * 1.2), 2)
                if new_tsl < pos.trailing_sl:
                    pos.trailing_sl = new_tsl
                    log.info("Trailing SL: Locked +1.2R Profit @ %.2f for %s", new_tsl, symbol)
            elif pos.breakeven_set and ltp <= one_half_r:
                new_tsl = round(pos.entry_price - (risk * 0.75), 2)
                if new_tsl < pos.trailing_sl:
                    pos.trailing_sl = new_tsl
                    log.info("Trailing SL: Locked +0.75R Profit @ %.2f for %s", new_tsl, symbol)

        # ── Check Trailing SL Hit ─────────────────────────────────────────────
        sl_hit = False
        if pos.direction == "BUY"  and ltp <= pos.trailing_sl:
            sl_hit = True
        if pos.direction == "SELL" and ltp >= pos.trailing_sl:
            sl_hit = True

        if sl_hit:
            reason = "BREAKEVEN_EXIT" if pos.breakeven_set else "SL_HIT"
            log.warning("STOP LOSS HIT | %s @ %.2f | SL was %.2f | %s",
                        symbol, ltp, pos.trailing_sl, reason)
            self._close_position(symbol, ltp, reason)
            return

        # ── Check Target Hit ──────────────────────────────────────────────────
        tgt_hit = False
        if pos.direction == "BUY"  and ltp >= pos.target:
            tgt_hit = True
        if pos.direction == "SELL" and ltp <= pos.target:
            tgt_hit = True

        if tgt_hit:
            log.info("TARGET HIT | %s @ %.2f | TGT was %.2f", symbol, ltp, pos.target)
            self._close_position(symbol, ltp, "TARGET_HIT")

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

        # Calculate actual realised P&L
        if pos.direction == "BUY":
            pnl = (exit_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - exit_price) * pos.quantity

        # Log exit
        self.journal.log_exit(
            trade_id=pos.trade_id,
            exit_price=exit_price,
            status=status,
            exit_order_id=exit_id or "",
        )
        log.info("Position closed | %s | status=%s | P&L=INR %.2f", symbol, status, pnl)

    # ── Square-Off ───────────────────────────────────────────────────────────

    def square_off_all(self):
        """Close all open positions (end of day)."""
        with self._lock:
            symbols = list(self.open_positions.keys())

        if not symbols:
            log.info("No open positions to square off.")
            return

        log.info("Square-off initiated for %d positions", len(symbols))
        for symbol in symbols:
            with self._lock:
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
