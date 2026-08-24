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


from enum import Enum
import pandas as pd


class TradeState(Enum):
    INITIAL = "INITIAL"
    PROFIT_PROTECTION = "PROFIT_PROTECTION"
    TREND_RUN = "TREND_RUN"
    MAX_PROFIT_EXPANSION = "MAX_PROFIT_EXPANSION"
    MOMENTUM_WEAKENING = "MOMENTUM_WEAKENING"
    INVALIDATED = "INVALIDATED"
    CLOSED = "CLOSED"


class OpenPosition:
    """Tracks an active intraday position with dynamic state lifecycle."""

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
        self.partial_booked = False             # True once 50% of position is booked
        
        # ── State Machine & Thesis Metrics ──
        self.state         = TradeState.INITIAL
        self.thesis_score  = 100.0
        self.warning_bars  = 0
        self.initial_r     = abs(entry_price - stop_loss) if abs(entry_price - stop_loss) > 0 else (entry_price * 0.005)
        self.current_tp    = target

    @property
    def risk(self) -> float:
        return self.initial_r

    @property
    def unrealised_pnl(self) -> float:
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def current_r_multiple(self) -> float:
        if self.initial_r <= 0:
            return 0.0
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) / self.initial_r
        else:
            return (self.entry_price - self.current_price) / self.initial_r

    def to_dict(self) -> dict:
        return {
            "trade_id":       self.trade_id,
            "symbol":         self.symbol,
            "direction":      self.direction,
            "quantity":       self.quantity,
            "entry_price":    self.entry_price,
            "stop_loss":      self.trailing_sl,   # Show current (trailing) SL
            "target":         self.current_tp,
            "current_price":  self.current_price,
            "unrealised_pnl": round(self.unrealised_pnl, 2),
            "strategy":       self.strategy,
            "state":          self.state.value,
            "thesis_score":   round(self.thesis_score, 1),
            "r_multiple":     round(self.current_r_multiple, 2),
            "breakeven_set":  self.breakeven_set,
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

        log.info("Trade opened | id=%s | %s %s x%d @ %.2f | SL=%.2f | TGT=%.2f",
                 trade_id, signal.direction, signal.symbol, qty,
                 actual_entry, actual_sl, actual_tgt)
        return True

    # ── Position Monitoring & Active Lifecycle Management ────────────────────

    def update_position_price(
        self,
        symbol: str,
        ltp: float,
        df_m5: Optional[pd.DataFrame] = None,
        df_m15: Optional[pd.DataFrame] = None,
        df_h1: Optional[pd.DataFrame] = None,
    ):
        """
        Update current price, evaluate thesis score, apply Finite State Trailing & Asymmetric Expansion.
        """
        with self._lock:
            pos = self.open_positions.get(symbol)
        if not pos:
            return

        pos.current_price = ltp
        r_unit = pos.initial_r
        current_r = pos.current_r_multiple

        # Compute Thesis score if multi-timeframe candle data is provided
        from strategies.asymmetric_expansion import AsymmetricTrendExpansionStrategy
        if df_m5 is not None and len(df_m5) >= 20:
            if df_m15 is None:
                df_m15 = AsymmetricTrendExpansionStrategy.resample_ohlcv(df_m5, "15min")
            if df_h1 is None:
                df_h1 = AsymmetricTrendExpansionStrategy.resample_ohlcv(df_m5, "60min")

            m5_ind, m15_ind, h1_ind = AsymmetricTrendExpansionStrategy.compute_indicators(df_m5, df_m15, df_h1)
            row_m5 = m5_ind.iloc[-1]
            prev_m5 = m5_ind.iloc[-2]
            row_m15 = m15_ind.iloc[-1] if not m15_ind.empty else row_m5
            row_h1 = h1_ind.iloc[-1] if not h1_ind.empty else row_m5

            pos.thesis_score = AsymmetricTrendExpansionStrategy.evaluate_thesis_score(pos.direction, row_m5, row_m15, row_h1)

            # Check Structural Invalidation
            if pos.direction == "BUY":
                if row_m5["close"] < row_m5.get("ema20", row_m5["close"]):
                    pos.warning_bars += 1
                else:
                    pos.warning_bars = 0

                if row_h1.get("close", 0) < row_h1.get("ema200", 0) and row_m5.get("close", 0) < row_m5.get("ema50", 0):
                    log.warning("[INVALIDATION] MACRO H1 INVALIDATION on %s @ %.2f — closing trade.", symbol, ltp)
                    self._close_position(symbol, ltp, "MACRO_H1_INVALIDATION")
                    return

                if row_m15.get("close", 0) < row_m15.get("ema50", 0) and pos.warning_bars >= 2:
                    log.warning("[INVALIDATION] M15 STRUCTURE BREAK on %s @ %.2f — closing trade.", symbol, ltp)
                    self._close_position(symbol, ltp, "M15_STRUCTURE_BREAK")
                    return
            else: # SELL
                if row_m5["close"] > row_m5.get("ema20", row_m5["close"]):
                    pos.warning_bars += 1
                else:
                    pos.warning_bars = 0

                if row_h1.get("close", 0) > row_h1.get("ema200", 0) and row_m5.get("close", 0) > row_m5.get("ema50", 0):
                    log.warning("[INVALIDATION] MACRO H1 INVALIDATION on %s @ %.2f — closing trade.", symbol, ltp)
                    self._close_position(symbol, ltp, "MACRO_H1_INVALIDATION")
                    return

                if row_m15.get("close", 0) > row_m15.get("ema50", 0) and pos.warning_bars >= 2:
                    log.warning("[INVALIDATION] M15 STRUCTURE BREAK on %s @ %.2f — closing trade.", symbol, ltp)
                    self._close_position(symbol, ltp, "M15_STRUCTURE_BREAK")
                    return

        # ── FINITE STATE MACHINE ACTIVE TRAILING & ASYMMETRIC EXPANSION ──

        # 1. STAGE 1: PROFIT PROTECTION (+1.2R) -> Lock +0.3R green buffer
        if pos.state == TradeState.INITIAL and current_r >= 1.2:
            pos.state = TradeState.PROFIT_PROTECTION
            pos.breakeven_set = True
            if pos.direction == "BUY":
                new_sl = round(pos.entry_price + (0.3 * r_unit), 2)
                pos.trailing_sl = max(pos.trailing_sl, new_sl)
            else:
                new_sl = round(pos.entry_price - (0.3 * r_unit), 2)
                pos.trailing_sl = min(pos.trailing_sl, new_sl)
            log.info("[PROFIT PROTECTION] [%s] (R=+%.2f) -> SL locked at %.2f (+0.3R green buffer)",
                     symbol, current_r, pos.trailing_sl)

        # 2. STAGE 2: TREND RUN (+2.0R & Thesis >= 70) -> Dynamic ATR-Swing Trailing
        if pos.state in [TradeState.INITIAL, TradeState.PROFIT_PROTECTION] and current_r >= 2.0 and pos.thesis_score >= 70:
            pos.state = TradeState.TREND_RUN
            log.info("[TREND RUN] [%s] ACTIVE (R=+%.2f, Thesis=%.0f) -> Swing trailing enabled",
                     symbol, current_r, pos.thesis_score)

        # 3. STAGE 3: MAX ASYMMETRIC PROFIT EXPANSION (>= +3.0R & Thesis >= 80)
        # Expand TP to +6.0R / +8.0R & Tighten SL to (R - 0.5R) locking in 80-90% of accumulated profit!
        if pos.state in [TradeState.TREND_RUN, TradeState.PROFIT_PROTECTION] and current_r >= 3.0 and pos.thesis_score >= 80:
            pos.state = TradeState.MAX_PROFIT_EXPANSION
            if pos.direction == "BUY":
                pos.current_tp = round(pos.entry_price + (6.0 * r_unit), 2)
                tight_sl = round(pos.entry_price + ((current_r - 0.5) * r_unit), 2)
                pos.trailing_sl = max(pos.trailing_sl, tight_sl)
            else:
                pos.current_tp = round(pos.entry_price - (6.0 * r_unit), 2)
                tight_sl = round(pos.entry_price - ((current_r - 0.5) * r_unit), 2)
                pos.trailing_sl = min(pos.trailing_sl, tight_sl)
            log.info("[ASYMMETRIC EXPANSION] [%s] (R=+%.2f)! TP expanded to +6.0R (%.2f), SL tightened to %.2f",
                     symbol, current_r, pos.current_tp, pos.trailing_sl)

        # Continuous Dynamic Swing Trailing in TREND_RUN or MAX_PROFIT_EXPANSION
        if pos.state in [TradeState.TREND_RUN, TradeState.MAX_PROFIT_EXPANSION]:
            if df_m5 is not None and len(df_m5) >= 3:
                atr_val = df_m5["atr14"].iloc[-1] if "atr14" in df_m5.columns else (r_unit * 0.5)
                if pos.direction == "BUY":
                    swing_low = df_m5["low"].iloc[-3:].min()
                    swing_stop = round(swing_low - (0.2 * atr_val), 2)
                    if swing_stop > pos.trailing_sl:
                        pos.trailing_sl = swing_stop
                        log.info("[SWING TRAILING] Trailed SL behind M5 swing low to %.2f for %s", swing_stop, symbol)
                else:
                    swing_high = df_m5["high"].iloc[-3:].max()
                    swing_stop = round(swing_high + (0.2 * atr_val), 2)
                    if swing_stop < pos.trailing_sl:
                        pos.trailing_sl = swing_stop
                        log.info("[SWING TRAILING] Trailed SL behind M5 swing high to %.2f for %s", swing_stop, symbol)

        # ── Check Trailing Stop Hit ──
        sl_hit = False
        if pos.direction == "BUY" and ltp <= pos.trailing_sl:
            sl_hit = True
        elif pos.direction == "SELL" and ltp >= pos.trailing_sl:
            sl_hit = True

        if sl_hit:
            reason = f"TRAILING_STOP (R={current_r:+.2f})" if pos.breakeven_set else "SL_HIT"
            log.warning("STOP LOSS / TRAILING EXIT | %s @ %.2f | SL was %.2f | %s",
                        symbol, ltp, pos.trailing_sl, reason)
            self._close_position(symbol, ltp, reason)
            return

        # ── Check Target Hit ──
        tgt_hit = False
        if pos.direction == "BUY" and ltp >= pos.current_tp:
            tgt_hit = True
        elif pos.direction == "SELL" and ltp <= pos.current_tp:
            tgt_hit = True

        if tgt_hit:
            log.info("🎯 TARGET HIT (R=+%.2f) | %s @ %.2f | TGT was %.2f", current_r, symbol, ltp, pos.current_tp)
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
