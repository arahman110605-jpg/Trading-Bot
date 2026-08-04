"""
main.py — Main Entry Point for Futures & Options (F&O) Algorithmic Trading Bot.

Usage:
    python main.py --mode paper --symbol NIFTY --strategy all
    python main.py --mode live --broker angel --symbol BANKNIFTY
"""

import argparse
import sys
import threading
from futures_options_bot.config import (
    BROKER, TRADING_MODE, DEFAULT_UNDERLYING, DASHBOARD_PORT
)
from futures_options_bot.broker.paper_fo_broker import PaperFOBroker
from futures_options_bot.broker.angel_fo_client import AngelFOBroker
from futures_options_bot.broker.zerodha_fo_client import ZerodhaFOBroker
from futures_options_bot.strategies.option_buying import OptionBuyingStrategy
from futures_options_bot.strategies.short_straddle import ShortStraddleStrategy
from futures_options_bot.strategies.credit_spreads import CreditSpreadsStrategy
from futures_options_bot.strategies.futures_trend import FuturesTrendStrategy
from futures_options_bot.engine.strategy_runner import FOStrategyRunner
from futures_options_bot.dashboard.app import start_dashboard, set_runner_references
from futures_options_bot.utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(description="Futures & Options (F&O) Algorithmic Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default=TRADING_MODE, help="Trading mode (paper or live)")
    parser.add_argument("--broker", choices=["angel", "zerodha"], default=BROKER, help="Broker selection")
    parser.add_argument("--symbol", default=DEFAULT_UNDERLYING, help="Underlying index or stock (NIFTY, BANKNIFTY, FINNIFTY, RELIANCE)")
    parser.add_argument("--strategy", default="all", help="Strategy to run (option_buying, short_straddle, credit_spreads, futures_trend, all)")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Dashboard port (default 5001)")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    return parser.parse_args()


def initialize_broker(mode: str, broker_type: str):
    if mode == "paper":
        broker = PaperFOBroker()
    elif broker_type == "angel":
        broker = AngelFOBroker()
    elif broker_type == "zerodha":
        broker = ZerodhaFOBroker()
    else:
        broker = PaperFOBroker()

    success = broker.connect()
    if not success and mode == "live":
        logger.error(f"Failed to authenticate with {broker_type} in LIVE mode. Exiting.")
        sys.exit(1)

    return broker


def initialize_strategies(strategy_arg: str) -> list:
    available = {
        "option_buying": OptionBuyingStrategy(),
        "short_straddle": ShortStraddleStrategy(),
        "credit_spreads": CreditSpreadsStrategy(),
        "futures_trend": FuturesTrendStrategy(),
    }

    if strategy_arg == "all":
        return list(available.values())
    elif strategy_arg in available:
        return [available[strategy_arg]]
    else:
        logger.warning(f"Unknown strategy '{strategy_arg}'. Loading all strategies.")
        return list(available.values())


def main():
    args = parse_args()

    print("=" * 70)
    print(" ⚡ FUTURES & OPTIONS (F&O) ALGORITHMIC TRADING BOT ")
    print(f" Mode: {args.mode.upper()} | Broker: {args.broker.upper()} | Symbol: {args.symbol}")
    print("=" * 70)

    # 1. Initialize Broker
    broker = initialize_broker(args.mode, args.broker)

    # 2. Load Strategies
    active_strategies = initialize_strategies(args.strategy)
    logger.info(f"Loaded {len(active_strategies)} strategies: {[s.name for s in active_strategies]}")

    # 3. Initialize Strategy Runner
    runner = FOStrategyRunner(broker=broker, strategies=active_strategies)

    # 4. Connect Web Dashboard References
    set_runner_references(broker, runner)

    # 5. Launch Web Dashboard in background thread
    if not args.no_dashboard:
        dash_thread = threading.Thread(
            target=start_dashboard,
            kwargs={"port": args.port},
            daemon=True
        )
        dash_thread.start()

    # 6. Start Main Trading Engine Loop
    runner.start_loop(symbol=args.symbol, interval_seconds=3)


if __name__ == "__main__":
    main()
