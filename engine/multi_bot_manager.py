"""
engine/multi_bot_manager.py — Multi-Bot Manager

Spawns and manages all 8 trading bot threads:
  - 5 Equity bots (read from MarketDataHub equity cache)
  - 3 Options bots (read from MarketDataHub options cache)

All bots share ONE MarketDataHub (ONE Angel One API connection).
Each bot has its own StrategyRunner, RiskManager, OrderManager, AnalyticsLogger.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

import config
from engine.market_data_hub import MarketDataHub
from engine.options_runner import OptionsRunner
from utils.logger import get_logger

log = get_logger("MultiBotManager")

# Path to bot manifest JSON
MANIFEST_PATH = Path(__file__).parent.parent / "bots" / "bot_manifest.json"


class MultiBotManager:
    """
    Launches and supervises all 8 bots.
    ONE MarketDataHub owns the Angel One connection.
    Each bot thread reads from the shared hub.
    """

    def __init__(self, on_update_callback=None):
        self.hub = MarketDataHub()
        self.bot_configs: List[Dict[str, Any]] = self._load_manifest()
        self.on_update = on_update_callback
        self._threads: List[threading.Thread] = []
        self._equity_runners = []
        self._options_runners = []
        self._running = False
        log.info("MultiBotManager: Loaded %d bot configs from manifest.", len(self.bot_configs))

    def _load_manifest(self) -> List[Dict[str, Any]]:
        """Load bot configuration from bot_manifest.json."""
        try:
            with open(MANIFEST_PATH, "r") as f:
                configs = json.load(f)
            log.info("Loaded %d bot configs from %s", len(configs), MANIFEST_PATH)
            return configs
        except FileNotFoundError:
            log.error("bot_manifest.json not found at %s — using empty config.", MANIFEST_PATH)
            return []
        except json.JSONDecodeError as e:
            log.error("Invalid bot_manifest.json: %s", e)
            return []

    def start(self):
        """Start the hub refresh loop, wait for initial data, then launch all bots."""
        log.info("MultiBotManager: Starting shared MarketDataHub...")
        self._running = True

        # Start hub background refresh
        from engine.strategy_runner import INTERVAL_SECONDS
        interval = INTERVAL_SECONDS.get(config.CANDLE_INTERVAL, 300)
        self.hub.start_refresh_loop(equity_interval_sec=interval)

        # Wait for initial data before bots start
        if not self.hub.wait_for_initial_data(timeout_sec=180):
            log.error("MultiBotManager: Initial data timeout — bots may start with empty cache.")

        # Launch equity and options bots
        for bot_cfg in self.bot_configs:
            bot_type = bot_cfg.get("type", "equity")
            if bot_type == "equity":
                self._launch_equity_bot(bot_cfg)
            elif bot_type == "options":
                self._launch_options_bot(bot_cfg)

        log.info("MultiBotManager: All %d bots launched.", len(self._threads))

    def _launch_equity_bot(self, bot_cfg: Dict):
        """Create and launch an equity StrategyRunner thread."""
        from engine.equity_bot_runner import EquityBotRunner
        bot_id = bot_cfg["bot_id"]
        runner = EquityBotRunner(bot_cfg=bot_cfg, hub=self.hub, on_update=self.on_update)
        self._equity_runners.append(runner)

        t = threading.Thread(
            target=runner.run,
            name=f"Bot-{bot_id}",
            daemon=True,
        )
        self._threads.append(t)
        t.start()
        log.info("MultiBotManager: Launched equity bot [%s] thread.", bot_id)

    def _launch_options_bot(self, bot_cfg: Dict):
        """Create and launch an options bot thread."""
        bot_id = bot_cfg["bot_id"]
        strategy_name = bot_cfg.get("strategy", "")

        # Import appropriate options strategy
        try:
            if strategy_name == "theta_straddle":
                from strategies.options.theta_straddle import ThetaStraddleStrategy
                strat = ThetaStraddleStrategy(bot_cfg)
            elif strategy_name == "iron_condor":
                from strategies.options.iron_condor import IronCondorStrategy
                strat = IronCondorStrategy(bot_cfg)
            elif strategy_name == "options_momentum":
                from strategies.options.options_momentum import OptionsMomentumStrategy
                strat = OptionsMomentumStrategy(bot_cfg)
            else:
                log.error("Unknown options strategy: %s", strategy_name)
                return
        except ImportError as e:
            log.error("Failed to import options strategy %s: %s", strategy_name, e)
            return

        runner = OptionsRunner(bot_cfg=bot_cfg, strategy=strat, hub=self.hub, on_update=self.on_update)
        self._options_runners.append(runner)

        t = threading.Thread(
            target=runner.run,
            name=f"Bot-{bot_id}",
            daemon=True,
        )
        self._threads.append(t)
        t.start()
        log.info("MultiBotManager: Launched options bot [%s] with strategy [%s].", bot_id, strategy_name)

    def stop(self):
        """Stop all bots and the hub."""
        log.info("MultiBotManager: Stopping all bots...")
        self._running = False
        self.hub.stop()
        for runner in self._equity_runners:
            runner.stop()
        for runner in self._options_runners:
            runner.stop()
        log.info("MultiBotManager: All bots stopped.")

    def get_all_status(self) -> List[Dict]:
        """Return status of all bots for the dashboard /arena page."""
        statuses = []
        for runner in self._equity_runners:
            statuses.append(runner.get_status())
        for runner in self._options_runners:
            statuses.append(runner.get_status())
        return statuses

    def get_signal_log(self) -> List[Dict]:
        """Aggregate recent signal logs across all bot runners."""
        all_signals = []
        for runner in self._equity_runners:
            if hasattr(runner, "get_signal_log"):
                all_signals.extend(runner.get_signal_log())
        all_signals.sort(key=lambda s: s.get("time", ""), reverse=True)
        return all_signals[:50]
