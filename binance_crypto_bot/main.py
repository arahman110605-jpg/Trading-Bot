"""
main.py — Main Entry Point for Delta Exchange Options & Binance Algorithmic Trading Bot.

v3.0 — Multi-Strategy Engine:
  Strategy A: ETH Spot Scalper     → $600 allocated  (primary, no theta)
  Strategy D: Option Seller        → $300 allocated  (passive, ADX < 18)
  Strategy B: Option Buyer (spike) → $100 reserve    (opportunistic only)

Usage:
    python main.py --mode paper --broker multi --capital 1000 --symbols BTC,ETH
    python main.py --mode paper --broker delta_options --symbols BTC,ETH  (legacy)
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
from binance_crypto_bot.broker.paper_spot_broker import PaperSpotBroker
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
from binance_crypto_bot.strategies.eth_spot_scalper import EthSpotScalperStrategy
from binance_crypto_bot.strategies.delta_option_seller import DeltaOptionSellerStrategy

from binance_crypto_bot.engine.strategy_runner import CryptoStrategyRunner
from binance_crypto_bot.engine.multi_strategy_runner import MultiStrategyRunner
from binance_crypto_bot.dashboard.app import start_dashboard, set_runner_reference
from binance_crypto_bot.utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(description="Delta Exchange Options & Binance Trading Bot")
    parser.add_argument("--mode",     choices=["paper", "live"],
                        default=TRADING_MODE)
    parser.add_argument("--broker",   choices=["multi", "delta_options", "binance_spot",
                                                "binance_futures", "web3_dex"],
                        default="multi")
    parser.add_argument("--symbols",  default="BTC,ETH")
    parser.add_argument("--strategy", default="all")
    parser.add_argument("--leverage", type=int,   default=LEVERAGE)
    parser.add_argument("--capital",  type=float, default=1000.0)
    parser.add_argument("--port",     type=int,   default=DASHBOARD_PORT)
    parser.add_argument("--no-dashboard", action="store_true")
    return parser.parse_args()


def main():
    args    = parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    logger.info("=" * 60)
    logger.info("[BOT] Starting Delta Exchange & Binance Crypto Bot")
    logger.info(f"Mode: {args.mode.upper()} | Broker: {args.broker.upper()} | Capital: ${args.capital}")
    logger.info("=" * 60)

    # ─── Multi-Strategy Mode (new default) ───────────────────────────────────
    if args.broker == "multi":
        logger.info("[MULTI-STRATEGY] Initializing 3-strategy engine with $1,000 paper capital")
        logger.info("  Strategy A: ETH Spot Scalper  — $600 | TP +1.5% | SL -0.8%")
        logger.info("  Strategy D: Option Seller     — $300 | Sell far-OTM on ADX < 18")
        logger.info("  Strategy B: Option Buyer      — $100 reserve | High-conviction spikes only")

        total = args.capital
        spot_capital    = round(total * 0.70, 2)   # 70% → spot scalping ($700)
        options_capital = round(total * 0.30, 2)   # 30% → option selling + buying ($300)
        # Remaining 10% stays as buffer in option broker

        spot_broker    = PaperSpotBroker(initial_capital=spot_capital,    max_positions=4)
        options_broker = PaperDeltaBroker(initial_capital=options_capital, max_positions=5)
        spot_broker.connect()
        options_broker.connect()

        spot_strategies    = [EthSpotScalperStrategy()]
        options_strategies = [
            DeltaOptionSellerStrategy(),           # Primary: sell OTM options
            DeltaOptionScalperStrategy(),          # Secondary: buy on strong spikes
        ]

        runner = MultiStrategyRunner(
            spot_broker       = spot_broker,
            options_broker    = options_broker,
            spot_strategies   = spot_strategies,
            options_strategies= options_strategies,
            symbols           = symbols,
        )
        set_runner_reference(runner)
        runner.start()

    # ─── Legacy single-broker modes ──────────────────────────────────────────
    elif args.broker == "delta_options":
        broker = PaperDeltaBroker(initial_capital=args.capital) if args.mode == "paper" else DeltaOptionClient()
        broker.connect()
        strategies = [DeltaOptionScalperStrategy()]
        runner = CryptoStrategyRunner(broker=broker, strategies=strategies, symbols=symbols)
        set_runner_reference(runner)
        runner.start()

    else:
        if args.mode == "paper":
            broker = PaperCryptoBroker(initial_capital=args.capital, default_leverage=args.leverage)
        elif args.broker == "binance_futures":
            broker = BinanceClient(is_futures=True)
        elif args.broker == "web3_dex":
            broker = Web3DexClient()
        else:
            broker = BinanceClient(is_futures=False)
        broker.connect() if hasattr(broker, 'connect') else None

        available_strategies = {
            "ema_crossover":         EMACrossoverStrategy(),
            "rsi_divergence":        RSIDivergenceStrategy(),
            "grid_trading":          GridTradingStrategy(),
            "macd_scalping":         MACDScalpingStrategy(),
            "delta_option_scalper":  DeltaOptionScalperStrategy(),
            "delta_option_buying":   DeltaOptionBuyingStrategy(),
            "delta_short_straddle":  DeltaShortStraddleStrategy(),
            "delta_credit_spreads":  DeltaCreditSpreadsStrategy(),
        }
        if args.strategy.lower() == "all":
            strategies = list(available_strategies.values())
        else:
            strategies = [available_strategies.get(args.strategy.lower(),
                          DeltaOptionScalperStrategy())]
        runner = CryptoStrategyRunner(broker=broker, strategies=strategies, symbols=symbols)
        set_runner_reference(runner)
        runner.start()

    if not args.no_dashboard:
        logger.info(f"🌐 Launching Dashboard at http://localhost:{args.port}")
        start_dashboard(port=args.port)


if __name__ == "__main__":
    main()
