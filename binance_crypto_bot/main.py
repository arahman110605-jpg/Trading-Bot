"""
main.py — Main Entry Point for Delta Exchange Options & Binance Algorithmic Trading Bot.

Usage:
    python main.py --mode paper --broker delta_options --symbols BTC
    python main.py --mode live --broker delta_options --symbols BTC,ETH
    python main.py --mode paper --broker binance_spot --symbols BTCUSDT
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from binance_crypto_bot.config import (
    TRADING_MODE, BROKER_TYPE, CRYPTO_WATCHLIST, DASHBOARD_PORT, CAPITAL, LEVERAGE
)
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.paper_delta_broker import PaperDeltaBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.broker.delta_option_client import DeltaOptionClient
from binance_crypto_bot.broker.web3_dex_client import Web3DexClient
from binance_crypto_bot.strategies.ema_crossover import EMACrossoverStrategy
from binance_crypto_bot.strategies.rsi_divergence import RSIDivergenceStrategy
from binance_crypto_bot.strategies.grid_trading import GridTradingStrategy
from binance_crypto_bot.strategies.macd_scalping import MACDScalpingStrategy
from binance_crypto_bot.strategies.delta_option_buying import DeltaOptionBuyingStrategy
from binance_crypto_bot.strategies.delta_option_scalper import DeltaOptionScalperStrategy
from binance_crypto_bot.strategies.delta_short_straddle import DeltaShortStraddleStrategy
from binance_crypto_bot.strategies.delta_credit_spreads import DeltaCreditSpreadsStrategy
from binance_crypto_bot.engine.strategy_runner import CryptoStrategyRunner
from binance_crypto_bot.dashboard.app import start_dashboard, set_runner_reference
from binance_crypto_bot.utils.logger import logger

def parse_args():
    parser = argparse.ArgumentParser(description="Delta Exchange Options & Binance Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default=TRADING_MODE, help="Trading mode (paper or live)")
    parser.add_argument("--broker", choices=["delta_options", "binance_spot", "binance_futures", "web3_dex"], default=BROKER_TYPE, help="Broker type")
    parser.add_argument("--symbols", default="BTC", help="Comma-separated list of symbols (e.g. BTC,ETH)")
    parser.add_argument("--strategy", default="all", help="Strategy to run")
    parser.add_argument("--leverage", type=int, default=LEVERAGE, help="Leverage for Futures")
    parser.add_argument("--capital", type=float, default=CAPITAL, help="Starting capital in USDT")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Dashboard web port")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    return parser.parse_args()

def initialize_broker(mode: str, broker_type: str, capital: float, leverage: int):
    if mode == "paper":
        if broker_type == "delta_options":
            broker = PaperDeltaBroker(initial_capital=capital)
        else:
            broker = PaperCryptoBroker(initial_capital=capital, default_leverage=leverage)
        broker.connect()
        return broker

    if broker_type == "delta_options":
        broker = DeltaOptionClient()
    elif broker_type == "binance_futures":
        broker = BinanceClient(is_futures=True)
    elif broker_type == "web3_dex":
        broker = Web3DexClient()
    else:
        broker = BinanceClient(is_futures=False)

    if hasattr(broker, 'ping') and not broker.ping():
        logger.error(f"Failed to connect to {broker_type} in LIVE mode.")
    return broker

def initialize_strategies(strategy_arg: str, broker_type: str) -> list:
    if broker_type == "delta_options":
        available = {
            "delta_option_scalper": DeltaOptionScalperStrategy(),
            "delta_option_buying": DeltaOptionBuyingStrategy(),
            "delta_short_straddle": DeltaShortStraddleStrategy(),
            "delta_credit_spreads": DeltaCreditSpreadsStrategy()
        }
    else:
        available = {
            "ema_crossover": EMACrossoverStrategy(),
            "rsi_divergence": RSIDivergenceStrategy(),
            "grid_trading": GridTradingStrategy(),
            "macd_scalping": MACDScalpingStrategy()
        }

    if strategy_arg.lower() == "all":
        return list(available.values())
    elif strategy_arg.lower() in available:
        return [available[strategy_arg.lower()]]
    else:
        logger.warning(f"Unknown strategy '{strategy_arg}', defaulting to all available.")
        return list(available.values())

def main():
    args = parse_args()
    logger.info("=" * 60)
    logger.info("[BOT] Starting Delta Exchange & Binance Crypto Bot")
    logger.info(f"Mode: {args.mode.upper()} | Broker: {args.broker.upper()} | Capital: ${args.capital}")
    logger.info("=" * 60)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    broker = initialize_broker(args.mode, args.broker, args.capital, args.leverage)
    strategies = initialize_strategies(args.strategy, args.broker)

    runner = CryptoStrategyRunner(broker=broker, strategies=strategies, symbols=symbols)
    set_runner_reference(runner)
    runner.start()

    if not args.no_dashboard:
        logger.info(f"🌐 Launching Dashboard at http://localhost:{args.port}")
        start_dashboard(port=args.port)

if __name__ == "__main__":
    main()
