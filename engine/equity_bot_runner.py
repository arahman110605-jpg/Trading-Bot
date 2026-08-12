"""
engine/equity_bot_runner.py — Per-bot equity strategy runner.

Each equity bot gets its own instance of this runner.
Instead of calling Angel One directly, it reads from the shared MarketDataHub.
"""

from __future__ import annotations

import threading
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

import config
from engine.market_data_hub import MarketDataHub
from engine.risk_manager import RiskManager
from engine.order_manager import OrderManager
from utils.analytics_logger import AnalyticsLogger
from utils.logger import get_logger
from strategies import (
    EMACrossoverStrategy, RSIStrategy, VWAPStrategy,
    SupertrendStrategy, CandlestickStrategy, ORBStrategy,
)
from strategies.base_strategy import Signal

log = get_logger("EquityBotRunner")

STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "rsi":           RSIStrategy,
    "vwap":          VWAPStrategy,
    "supertrend":    SupertrendStrategy,
    "candlestick":   CandlestickStrategy,
    "orb":           ORBStrategy,
}

TREND_ONLY = {"ema_crossover", "supertrend", "orb"}


class EquityBotRunner:
    """Runs equity strategies for a single bot using shared hub data."""

    def __init__(self, bot_cfg: Dict[str, Any], hub: MarketDataHub, broker_client=None, journal=None, on_update: Optional[Callable] = None):
        self.bot_id  = bot_cfg["bot_id"]
        self.cfg     = bot_cfg
        self.hub     = hub
        self.on_update = on_update
        self._running = False

        # Inject bot_id into environment so AnalyticsLogger picks it up
        os.environ["BOT_ID"] = self.bot_id

        from utils.trade_journal import TradeJournal
        self.journal   = journal or TradeJournal()
        self.analytics = AnalyticsLogger()
        self.risk_mgr  = RiskManager(journal=self.journal, capital=bot_cfg.get("capital", config.CAPITAL))
        
        client = broker_client or getattr(hub, "_client", None)
        self.order_mgr = OrderManager(kite=client, risk=self.risk_mgr, journal=self.journal, bot_id=self.bot_id)

        # Instantiate only the enabled strategies
        enabled = bot_cfg.get("strategies", [])
        self.strategies = []
        for name in enabled:
            cls = STRATEGY_MAP.get(name)
            if cls:
                self.strategies.append(cls())
                log.debug("%s: Loaded strategy [%s]", self.bot_id, name)
            else:
                log.warning("%s: Unknown strategy name [%s]", self.bot_id, name)

        self._trades_today = 0
        self._daily_pnl    = 0.0
        self._open_positions: List[Dict] = []
        self._consensus_signals: List[Signal] = []   # shared across scan cycles
        self._signal_log: List[Dict] = []
        self._signal_lock = threading.Lock()

        log.info("%s: EquityBotRunner ready | strategies=%s | capital=%d",
                 self.bot_id, enabled, bot_cfg.get("capital", config.CAPITAL))

    def _record_signal(self, signal: Signal):
        """Keep last 50 signals for dashboard display (thread-safe)."""
        entry = {
            "time":      datetime.now().strftime("%H:%M:%S"),
            "bot_id":    self.bot_id,
            "symbol":    signal.symbol,
            "direction": signal.direction,
            "strategy":  signal.strategy,
            "entry":     signal.entry_price,
            "sl":        signal.stop_loss,
            "target":    signal.target,
            "rr":        getattr(signal, 'rr_ratio', 1.5),
            "conf":      f"{signal.confidence:.0%}",
            "notes":     signal.notes,
        }
        with self._signal_lock:
            self._signal_log.insert(0, entry)
            self._signal_log = self._signal_log[:50]

    def get_signal_log(self) -> List[Dict]:
        with self._signal_lock:
            return list(self._signal_log)

    def run(self):
        """Main bot loop — waits for hub to refresh then evaluates signals."""
        self._running = True
        log.info("%s: Starting equity bot loop...", self.bot_id)

        from engine.strategy_runner import INTERVAL_SECONDS, _compute_adx
        interval_sec = INTERVAL_SECONDS.get(config.CANDLE_INTERVAL, 300)

        while self._running:
            try:
                # Market hours check (IST 9:15 AM - 3:15 PM)
                if not self.risk_mgr.is_market_open():
                    time.sleep(30)
                    continue

                # Wait until hub has fresh data
                last_refresh = self.hub.last_refresh_time()
                if last_refresh is None:
                    time.sleep(5)
                    continue

                equity_data = self.hub.get_all_equity()
                if not equity_data:
                    time.sleep(10)
                    continue

                # Update trailing SL and Target for open positions
                for pos in self.order_mgr.get_open_positions():
                    sym = pos["symbol"]
                    df = equity_data.get(sym)
                    if df is not None and not df.empty:
                        ltp = df.iloc[-1]['close']
                        self.order_mgr.update_position_price(sym, ltp)

                # Per-symbol evaluation
                candidate_signals: List[Signal] = []
                consensus_min = self.cfg.get("consensus_min_signals", 1)
                adx_threshold = self.cfg.get("adx_threshold", config.ADX_TREND_THRESHOLD)

                for symbol, df in equity_data.items():
                    if df.empty or len(df) < 20:
                        continue

                    adx = _compute_adx(df)
                    trending = adx >= adx_threshold

                    sym_signals: List[Signal] = []
                    for strat in self.strategies:
                        if strat.name in TREND_ONLY and not trending:
                            continue
                        try:
                            sig = strat.generate_signal(symbol, df)
                            if sig and sig.is_actionable:
                                sym_signals.append(sig)
                                self._record_signal(sig)
                        except Exception as e:
                            log.error("%s: Strategy %s error on %s: %s", self.bot_id, strat.name, symbol, e)

                    # Consensus filter
                    buy_sigs  = [s for s in sym_signals if s.direction == "BUY"]
                    sell_sigs = [s for s in sym_signals if s.direction == "SELL"]

                    if len(buy_sigs) >= consensus_min:
                        best = max(buy_sigs, key=lambda s: s.confidence)
                        candidate_signals.append(best)
                    elif len(sell_sigs) >= consensus_min:
                        best = max(sell_sigs, key=lambda s: s.confidence)
                        candidate_signals.append(best)

                # Execute best signal
                if candidate_signals:
                    best = max(candidate_signals, key=lambda s: s.confidence)
                    if "consensus" in self.bot_id:
                        self.hub.set_consensus_signal(best.direction, best.symbol)
                    max_trades = self.cfg.get("max_trades_per_day", config.MAX_TRADES_PER_DAY)
                    if self._trades_today < max_trades:
                        valid, reason = self.risk_mgr.validate_signal(best)
                        if valid:
                            executed = self.order_mgr.execute_signal(best)
                            if executed:
                                self._trades_today += 1
                                log.info("%s: TRADE EXECUTED | %s %s @ %.2f",
                                         self.bot_id, best.direction, best.symbol, best.entry_price)
                        self.analytics.log_signal_telemetry(
                            symbol=best.symbol, strategy=best.strategy,
                            direction=best.direction, confidence=best.confidence,
                            entry_price=best.entry_price, stop_loss=best.stop_loss,
                            target=best.target, rr_ratio=getattr(best, 'rr_ratio', 0),
                            was_executed=valid, rejection_reason="" if valid else reason,
                            notes=getattr(best, 'notes', ''),
                        )

                if self.on_update:
                    self.on_update()

            except Exception as e:
                log.error("%s: Error in bot loop: %s", self.bot_id, e, exc_info=True)

            time.sleep(interval_sec)

    def stop(self):
        self._running = False

    def get_status(self) -> Dict:
        return {
            "bot_id":       self.bot_id,
            "name":         self.cfg.get("name", self.bot_id),
            "type":         "equity",
            "total_trades": self._trades_today,
            "open_positions_count": len(self.order_mgr.get_open_positions()),
            "pnl":          self._daily_pnl,
            "strategies":   self.cfg.get("strategies", []),
            "capital":      self.cfg.get("capital", 100000),
        }
