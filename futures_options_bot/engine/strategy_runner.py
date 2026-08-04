"""
strategy_runner.py — Main Execution Loop and Signal Orchestrator for F&O Bot.
"""

import time
from futures_options_bot.broker.base_broker import BaseFOBroker
from futures_options_bot.engine.order_manager import FOOrderManager
from futures_options_bot.engine.risk_manager import FORiskManager
from futures_options_bot.engine.strike_selector import StrikeSelector
from futures_options_bot.utils.logger import logger
from futures_options_bot.config import STRIKE_SELECTION_OFFSET


class FOStrategyRunner:

    def __init__(self, broker: BaseFOBroker, strategies: list):
        self.broker = broker
        self.strategies = strategies
        self.risk_manager = FORiskManager()
        self.order_manager = FOOrderManager(self.broker, self.risk_manager)
        self.running = False

    def run_iteration(self, symbol: str):
        """Executes a single market scan & position management cycle."""
        # 1. Fetch underlying spot price
        spot_price = self.broker.get_underlying_ltp(symbol)
        if spot_price <= 0:
            logger.warning(f"Unable to fetch valid spot price for {symbol}")
            return

        # 2. Manage open positions (SL/Target check, 3:15 PM square-off)
        self.order_manager.monitor_and_manage_positions()

        # 3. Scan strategies for signals
        for strategy in self.strategies:
            signal = strategy.generate_signal(symbol, spot_price)
            if signal and signal.get("action") in ["BUY", "SELL"]:
                opt_type = signal["option_type"]
                offset = signal.get("offset", STRIKE_SELECTION_OFFSET)

                # Select exact strike (ATM/ITM/OTM)
                strike_info = StrikeSelector.select_strike(symbol, spot_price, opt_type, offset)
                
                # Calculate lot sizing
                option_price = self.broker.get_option_ltp(symbol, opt_type, strike_info["selected_strike"])
                lots = self.risk_manager.calculate_lot_size(symbol, option_price)

                signal["strike"] = strike_info["selected_strike"]
                signal["lots"] = lots

                logger.info(
                    f"🎯 Signal Detected from strategy '{strategy.name}': "
                    f"{signal['action']} {signal['option_type']} Strike {signal['strike']} "
                    f"({lots} Lots) on {symbol} (Spot: ₹{spot_price:.2f})"
                )

                self.order_manager.execute_signal(signal)

    def start_loop(self, symbol: str = "NIFTY", interval_seconds: int = 5):
        """Starts continuous loop scanning market."""
        self.running = True
        logger.info(f"🚀 F&O Trading Engine started loop for {symbol} (Interval: {interval_seconds}s)")
        try:
            while self.running:
                self.run_iteration(symbol)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("🛑 Stopping F&O Trading Engine...")
            self.running = False
