"""
main.py — Main Entry Point for Binance Crypto & Web3 Algorithmic Trading Bot.

Usage:
    python main.py --mode paper --broker binance_spot --symbols BTCUSDT,ETHUSDT
    python main.py --mode live --broker binance_futures --symbols BTCUSDT --leverage 5
    python main.py --mode live --broker web3_dex --port 5002
"""

import argparse
import sys
import os

# Ensure package path is accessible when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from binance_crypto_bot.config import (
    TRADING_MODE, BROKER_TYPE, CRYPTO_WATCHLIST, DASHBOARD_PORT, CAPITAL, LEVERAGE
)
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.broker.web3_dex_client import Web3DexClient
from binance_crypto_bot.strategies.ema_crossover import EMACrossoverStrategy
from binance_crypto_bot.strategies.rsi_divergence import RSIDivergenceStrategy
from binance_crypto_bot.strategies.grid_trading import GridTradingStrategy
from binance_crypto_bot.strategies.macd_scalping import MACDScalpingStrategy
from binance_crypto_bot.engine.strategy_runner import CryptoStrategyRunner
from binance_crypto_bot.dashboard.app import start_dashboard, set_runner_reference
from binance_crypto_bot.utils.logger import logger

def parse_args():
    parser = argparse.ArgumentParser(description="Binance Crypto & Web3 Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default=TRADING_MODE, help="Trading mode (paper or live)")
    parser.add_argument("--broker", choices=["binance_spot", "binance_futures", "web3_dex"], default=BROKER_TYPE, help="Broker type")
    parser.add_argument("--symbols", default=",".join(CRYPTO_WATCHLIST[:2]), help="Comma-separated list of symbols (e.g. BTCUSDT,ETHUSDT)")
    parser.add_argument("--strategy", default="all", help="Strategy to run (ema_crossover, rsi_divergence, grid_trading, macd_scalping, all)")
    parser.add_argument("--leverage", type=int, default=LEVERAGE, help="Leverage for Futures trading (1 to 20)")
    parser.add_argument("--capital", type=float, default=CAPITAL, help="Starting capital in USDT")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Dashboard web port (default 5002)")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    return parser.parse_args()

def initialize_broker(mode: str, broker_type: str, capital: float, leverage: int):
    if mode == "paper":
        broker = PaperCryptoBroker(initial_capital=capital, default_leverage=leverage)
        broker.connect()
        return broker

    if broker_type == "binance_futures":
        broker = BinanceClient(is_futures=True)
    elif broker_type == "web3_dex":
        broker = Web3DexClient()
    else:  # binance_spot
        broker = BinanceClient(is_futures=False)

    if not broker.ping() if hasattr(broker, 'ping') else not broker.is_connected():
        logger.error(f"Failed to connect to {broker_type} in LIVE mode.")
    return broker

def initialize_strategies(strategy_arg: str) -> list:
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
        logger.warning(f"Unknown strategy '{strategy_arg}', defaulting to all.")
        return list(available.values())

def main():
    args = parse_args()
    logger.info("=" * 60)
    logger.info("[BOT] Starting Binance Crypto & Web3 Trading Bot")
    logger.info(f"Mode: {args.mode.upper()} | Broker: {args.broker.upper()} | Capital: ${args.capital}")
    logger.info("=" * 60)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    broker = initialize_broker(args.mode, args.broker, args.capital, args.leverage)
    strategies = initialize_strategies(args.strategy)

    runner = CryptoStrategyRunner(broker=broker, strategies=strategies, symbols=symbols)
    set_runner_reference(runner)
    runner.start()

    if not args.no_dashboard:
        logger.info(f"🌐 Launching Dashboard at http://localhost:{args.port}")
        start_dashboard(port=args.port)

if __name__ == "__main__":
    main()
