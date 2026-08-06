"""
engine/strategy_runner.py — Runs all enabled strategies on each tick cycle.

The main loop:
  1. Every N minutes (matching candle interval), fetch fresh OHLCV data
  2. Compute ADX for market regime detection per symbol
  3. Run ALL applicable strategies for each symbol
  4. Collect all signals, rank by confidence — execute ONLY the highest-confidence one
  5. Update open positions with latest prices
  6. Check square-off time
"""

from __future__ import annotations

import time
import threading
from typing import List, Dict, Optional, Callable
from datetime import datetime

import pandas as pd

import config
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
    ORBStrategy,
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

# Strategies that only work in trending markets (ADX > threshold)
TREND_ONLY_STRATEGIES = {"ema_crossover", "supertrend", "orb"}

# Strategies that work in any/sideways market
ALL_MARKET_STRATEGIES = {"rsi", "vwap", "candlestick"}


def _compute_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Compute ADX (Average Directional Index) to detect market regime."""
    try:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        plus_dm  = high.diff()
        minus_dm = -low.diff()
        plus_dm  = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr      = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
        adx      = dx.ewm(alpha=1/period, adjust=False).mean()
        return round(float(adx.iloc[-1]), 2)
    except Exception:
        return 20.0  # Default: mixed market


class StrategyRunner:
    """
    Orchestrates the main trading loop.
    Runs in a background thread, checking for signals every candle interval.
    """

    def __init__(self, kite, order_mgr: OrderManager, risk_mgr: RiskManager):
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
        self._signal_log: List[Dict] = []
        self._signal_lock = threading.Lock()
        self._status: str = "STOPPED"
        self._on_update: Optional[Callable] = None

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
        if config.STRATEGIES.get("orb"):
            active.append(ORBStrategy())
        log.info("Loaded strategies: %s", [s.name for s in active])
        return active

    def set_update_callback(self, cb: Callable):
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
        log.info("Strategy runner started (mode=%s)", config.TRADING_MODE)

    def stop(self):
        self._running = False
        self._status  = "STOPPED"
        log.info("Strategy runner stopped.")

    def pause(self):
        self._running = False
        self._status  = "PAUSED"
        log.info("Strategy runner paused.")

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
            log.info("Square-off time reached. Closing all positions.")
            self.order_mgr.square_off_all()
            self.stop()
            return

        # 2. Update prices for open positions
        open_pos = self.order_mgr.get_open_positions()
        for pos in open_pos:
            ltp = self.kite.get_ltp(pos["symbol"])
            if ltp:
                self.order_mgr.update_position_price(pos["symbol"], ltp)

        # 3. Check if new entries are allowed
        allowed, reason = self.risk_mgr.is_new_entry_allowed()
        if not allowed:
            log.info("New entry blocked (%s) — scanning for telemetry only", reason)

        # 4. Scan watchlist for signals
        open_symbols = {p["symbol"] for p in self.order_mgr.get_open_positions()}

        for symbol in self.watchlist:
            if symbol in open_symbols:
                continue

            time.sleep(0.6)  # Respect Angel One SmartAPI rate limit (max 1.5 req/sec)

            df = self.kite.get_historical_data(symbol, interval=self.interval, days=5)
            if df is None or df.empty or len(df) < 30:
                log.debug("No data for %s", symbol)
                continue

            # 5. Compute ADX — determine market regime for this symbol
            adx = _compute_adx(df, config.ADX_PERIOD)
            if adx < config.ADX_CHOPPY_THRESHOLD:
                log.debug("%s: ADX=%.1f very choppy — skipping all strategies", symbol, adx)
                continue

            trending = adx >= config.ADX_TREND_THRESHOLD
            log.debug("%s: ADX=%.1f | regime=%s", symbol, adx, "TRENDING" if trending else "MIXED")

            # 6. Collect ALL signals from applicable strategies
            candidate_signals: List[Signal] = []

            for strategy in self.strategies:
                # Skip trend-only strategies in sideways/mixed markets
                if strategy.name in TREND_ONLY_STRATEGIES and not trending:
                    continue

                signal = strategy.generate_signal(symbol, df)
                
                if signal.is_actionable:
                    candidate_signals.append(signal)
                    self._record_signal(signal)
                    log.info("Signal [%s] %s %s conf=%.0f%% | ADX=%.1f",
                             strategy.name, signal.direction, symbol,
                             signal.confidence * 100, adx)

            if not candidate_signals:
                continue

            # 7. Pick the HIGHEST-CONFIDENCE signal (not just the first one)
            best_signal = max(candidate_signals, key=lambda s: s.confidence)
            log.info("Best signal: [%s] %s %s @ %.2f (conf=%.0f%%)",
                     best_signal.strategy, best_signal.direction, symbol,
                     best_signal.entry_price, best_signal.confidence * 100)

            # 8. Execute (or record rejection) for the best signal
            valid_risk, risk_reason = self.risk_mgr.validate_signal(best_signal)
            executed = False

            if allowed and valid_risk:
                executed = self.order_mgr.execute_signal(best_signal)

            rejection = "" if executed else (reason if not allowed else risk_reason)

            # 9. Log telemetry for all candidates (for post-run analysis)
            for sig in candidate_signals:
                self.analytics.log_signal_telemetry(
                    symbol=sig.symbol,
                    strategy=sig.strategy,
                    direction=sig.direction,
                    confidence=sig.confidence,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    target=sig.target,
                    rr_ratio=sig.rr_ratio,
                    was_executed=(executed and sig is best_signal),
                    rejection_reason=rejection if sig is best_signal else "Not best signal",
                    notes=sig.notes,
                )

        if self._on_update:
            self._on_update()

    def _record_signal(self, signal: Signal):
        """Keep last 50 signals for dashboard display (thread-safe)."""
        entry = {
            "time":      datetime.now().strftime("%H:%M:%S"),
            "symbol":    signal.symbol,
            "direction": signal.direction,
            "strategy":  signal.strategy,
            "entry":     signal.entry_price,
            "sl":        signal.stop_loss,
            "target":    signal.target,
            "rr":        signal.rr_ratio,
            "conf":      f"{signal.confidence:.0%}",
            "notes":     signal.notes,
        }
        with self._signal_lock:
            self._signal_log.insert(0, entry)
            self._signal_log = self._signal_log[:50]

    def get_signal_log(self) -> List[Dict]:
        with self._signal_lock:
            return list(self._signal_log)
