"""
strategy_runner.py — Multi-symbol strategy runner loop for Crypto Trading Bot.
"""

import time
import threading
from typing import List, Dict, Any
import pandas as pd
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.engine.risk_manager import CryptoRiskManager
from binance_crypto_bot.engine.order_executor import CryptoOrderExecutor
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.logger import logger

class CryptoStrategyRunner:
    def __init__(self, broker: Any, strategies: List[BaseCryptoStrategy], symbols: List[str], interval: str = "5m"):
        self.broker = broker
        self.strategies = strategies
        self.symbols = symbols
        self.interval = interval
        self.running = False
        self.paused = False
        self._thread: threading.Thread = None
        
        self.risk_manager = CryptoRiskManager()
        self.executor = CryptoOrderExecutor(broker)
        self.binance_feeder = BinanceClient(is_futures=False, testnet=False)  # For live data fetching

        # State tracking for Dashboard
        self.latest_signals: List[Dict[str, Any]] = []
        self.market_prices: Dict[str, float] = {}

    def start(self):
        """Start the trading bot loop thread."""
        if self.running:
            return
        self.running = True
        self.paused = False

        # Set risk manager initial balance
        acc = self.broker.get_account_balance()
        self.risk_manager.set_starting_equity(acc.get("wallet_balance", 1000.0))

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Crypto Strategy Runner started for symbols: {self.symbols}")

    def stop(self):
        """Stop the loop thread."""
        self.running = False
        logger.info("Crypto Strategy Runner stopped.")

    def pause(self):
        self.paused = True
        logger.info("Crypto Strategy Runner paused.")

    def resume(self):
        self.paused = False
        logger.info("Crypto Strategy Runner resumed.")

    def _fetch_klines_fallback(self, symbol: str) -> pd.DataFrame:
        """Fetch real kline candles or generate fallback candle data for paper mode."""
        df = self.binance_feeder.get_klines(symbol, interval=self.interval, limit=100)
        if not df.empty:
            return df

        # Generate synthetic candles if offline / no internet connection
        import numpy as np
        logger.warning(f"Generating synthetic candle feed for {symbol} paper test")
        now = pd.Timestamp.now()
        times = [now - pd.Timedelta(minutes=5*i) for i in range(100)][::-1]
        
        base_price = 60000.0 if "BTC" in symbol else 3000.0
        prices = base_price + np.cumsum(np.random.normal(0, base_price*0.001, 100))
        
        df = pd.DataFrame({
            "open_time": times,
            "open": prices * 0.999,
            "high": prices * 1.002,
            "low": prices * 0.998,
            "close": prices,
            "volume": np.random.uniform(10, 100, 100)
        })
        return df

    def _run_loop(self):
        while self.running:
            if not self.paused:
                try:
                    for symbol in self.symbols:
                        # 1. Fetch current Kline data
                        df = self._fetch_klines_fallback(symbol)
                        if df.empty:
                            continue

                        current_price = float(df.iloc[-1]["close"])
                        self.market_prices[symbol] = current_price

                        # 2. Update paper broker positions with current price
                        if isinstance(self.broker, PaperCryptoBroker):
                            self.broker.update_prices({symbol: current_price})

                        # 3. Evaluate strategies for signal generation
                        for strategy in self.strategies:
                            signal = strategy.generate_signal(df)
                            signal["symbol"] = symbol

                            if signal.get("action") in ["BUY", "SELL"]:
                                logger.info(f"Signal Generated: {symbol} [{signal['action']}] by {strategy.name} | Price: ${current_price:.2f}")

                                # Add to latest signals log
                                self.latest_signals.insert(0, {
                                    "symbol": symbol,
                                    "action": signal["action"],
                                    "strategy": strategy.name,
                                    "price": current_price,
                                    "reason": signal.get("reason", ""),
                                    "timestamp": time.strftime("%H:%M:%S")
                                })
                                self.latest_signals = self.latest_signals[:20]

                                # Validate with Risk Manager
                                acc = self.broker.get_account_balance()
                                current_equity = acc.get("total_equity", acc.get("wallet_balance", 1000.0))
                                
                                if self.risk_manager.validate_signal(signal, current_equity):
                                    qty = self.risk_manager.calculate_position_size(current_price, acc.get("available", 1000.0))
                                    if qty > 0:
                                        self.executor.execute_trade(symbol, signal, qty)
                except Exception as e:
                    logger.error(f"Error in strategy runner loop: {e}")

            time.sleep(5)  # 5-second tick interval
