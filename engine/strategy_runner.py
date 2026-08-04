"""
engine/strategy_runner.py — Runs all enabled strategies on each tick cycle.

The main loop:
  1. Every N minutes (matching candle interval), fetch fresh OHLCV data
  2. Run each enabled strategy for each symbol in the watchlist
  3. If a valid signal is generated, pass it to OrderManager
  4. Update open positions with latest prices
  5. Check square-off time
"""

from __future__ import annotations

import time
import threading
from typing import List, Dict, Optional, Callable
from datetime import datetime

import config
from broker.kite_client import KiteClient
from engine.order_manager import OrderManager
from engine.risk_manager import RiskManager
from utils.analytics_logger import AnalyticsLogger
from strategies.base_strategy import BaseStrategy, Signal
from strategies import (
    EMACrossoverStrategy,
    RSIStrategy,
    VWAPStrategy,
    SupertrendStrategy,
    CandlestickStrategy,
)
from utils.logger import get_logger

log = get_logger("StrategyRunner")

# Interval string → seconds mapping
INTERVAL_SECONDS = {
    "minute":   60,
    "3minute":  180,
    "5minute":  300,
    "10minute": 600,
    "15minute": 900,
    "30minute": 1800,
    "60minute": 3600,
    "demo":     30,    # Demo mode: new candle every 30 seconds
}


class StrategyRunner:
    """
    Orchestrates the main trading loop.
    Runs in a background thread, checking for signals every candle interval.
    """

    def __init__(self, kite: KiteClient, order_mgr: OrderManager, risk_mgr: RiskManager):
        self.kite      = kite
        self.order_mgr = order_mgr
        self.risk_mgr  = risk_mgr
        self.analytics = AnalyticsLogger()
        self.watchlist = config.WATCHLIST
        self.interval  = config.CANDLE_INTERVAL
        self.tick_secs = INTERVAL_SECONDS.get(self.interval, 300)

        self.strategies: List[BaseStrategy] = self._load_strategies()
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._signal_log: List[Dict] = []     # Recent signals for dashboard
        self._status: str = "STOPPED"
        self._on_update: Optional[Callable] = None  # Callback for dashboard

        log.info(
            "StrategyRunner ready | %d strategies | %d symbols | interval=%s",
            len(self.strategies), len(self.watchlist), self.interval
        )

    def _load_strategies(self) -> List[BaseStrategy]:
        active = []
        if config.STRATEGIES.get("ema_crossover"):
            active.append(EMACrossoverStrategy())
        if config.STRATEGIES.get("rsi"):
            active.append(RSIStrategy())
        if config.STRATEGIES.get("vwap"):
            active.append(VWAPStrategy())
        if config.STRATEGIES.get("supertrend"):
            active.append(SupertrendStrategy())
        if config.STRATEGIES.get("candlestick"):
            active.append(CandlestickStrategy())
        log.info("Loaded strategies: %s", [s.name for s in active])
        return active

    def set_update_callback(self, cb: Callable):
        """Register a callback to be called after each scan cycle (for dashboard push)."""
        self._on_update = cb

    # ── Control ──────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            log.warning("Runner already running.")
            return
        self._running = True
        self._status  = "RUNNING"
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info("▶ Strategy runner started (mode=%s)", config.TRADING_MODE)

    def stop(self):
        self._running = False
        self._status  = "STOPPED"
        log.info("⏹ Strategy runner stopped.")

    def pause(self):
        self._running = False
        self._status  = "PAUSED"
        log.info("⏸ Strategy runner paused.")

    def resume(self):
        if self._status == "PAUSED":
            self.start()

    @property
    def status(self) -> str:
        return self._status

    # ── Main Loop ─────────────────────────────────────────────────────────────

    def _run_loop(self):
        log.info("Main trading loop started. Tick every %ds.", self.tick_secs)
        while self._running:
            try:
                self._tick()
            except Exception as e:
                log.error("Error in trading loop: %s", e, exc_info=True)

            # Sleep until next candle, but check for stop every 5s
            elapsed = 0
            while elapsed < self.tick_secs and self._running:
                time.sleep(5)
                elapsed += 5

        log.info("Trading loop exited.")

    def _tick(self):
        """One full scan cycle."""
        now = datetime.now()
        log.info("── Scan cycle | %s | mode=%s ──", now.strftime("%H:%M:%S"), config.TRADING_MODE)

        # 1. Check if we should square off all
        if self.risk_mgr.should_square_off_all():
            log.info("⏰ Square-off time reached. Closing all positions.")
            self.order_mgr.square_off_all()
            self.stop()
            return

        # 2. Update prices for open positions
        open_pos = self.order_mgr.get_open_positions()
        for pos in open_pos:
            symbol = pos["symbol"]
            ltp = self.kite.get_ltp(symbol)
            if ltp:
                self.order_mgr.update_position_price(symbol, ltp)

        # 3. Check if new entries are allowed
        allowed, reason = self.risk_mgr.is_new_entry_allowed()
        if not allowed:
            log.info("New entry blocked for live orders (%s), but scanning signals for telemetry...", reason)

        # 4. Scan watchlist for signals
        for symbol in self.watchlist:
            if symbol in {p["symbol"] for p in self.order_mgr.get_open_positions()}:
                continue  # Already in this trade

            df = self.kite.get_historical_data(symbol, interval=self.interval, days=5)
            if df is None or df.empty:
                log.debug("No data for %s", symbol)
                continue

            for strategy in self.strategies:
                signal = strategy.generate_signal(symbol, df)
                if signal.is_actionable:
                    log.info("📶 Signal: %s", signal)
                    self._record_signal(signal)

                    # Validate signal & execute
                    valid_risk, risk_reason = self.risk_mgr.validate_signal(signal)
                    executed = False

                    if allowed and valid_risk:
                        executed = self.order_mgr.execute_signal(signal)

                    rejection = "" if executed else (reason if not allowed else risk_reason)

                    # Log full telemetry for strategy optimization analysis
                    self.analytics.log_signal_telemetry(
                        symbol=signal.symbol,
                        strategy=signal.strategy,
                        direction=signal.direction,
                        confidence=signal.confidence,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        target=signal.target,
                        rr_ratio=signal.rr_ratio,
                        was_executed=executed,
                        rejection_reason=rejection,
                        notes=signal.notes,
                    )

                    if executed:
                        break  # One trade per symbol per cycle

        if self._on_update:
            self._on_update()

    def _record_signal(self, signal: Signal):
        """Keep last 50 signals for dashboard display."""
        self._signal_log.insert(0, {
            "time":      datetime.now().strftime("%H:%M:%S"),
            "symbol":    signal.symbol,
            "direction": signal.direction,
            "strategy":  signal.strategy,
            "entry":     signal.entry_price,
            "sl":        signal.stop_loss,
            "target":    signal.target,
            "rr":        signal.rr_ratio,
            "notes":     signal.notes,
        })
        self._signal_log = self._signal_log[:50]

    def get_signal_log(self) -> List[Dict]:
        return self._signal_log
