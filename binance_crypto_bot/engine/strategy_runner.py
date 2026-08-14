"""
strategy_runner.py — Multi-symbol strategy runner loop for Binance & Delta Crypto Options Bot.
"""

import time
import threading
from typing import List, Dict, Any
import pandas as pd
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.paper_delta_broker import PaperDeltaBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.engine.risk_manager import CryptoRiskManager
from binance_crypto_bot.engine.order_executor import CryptoOrderExecutor
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.utils.logger import logger
from binance_crypto_bot.engine.ai_overseer_agent import AIStrategyOverseer

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
        self.ai_overseer = AIStrategyOverseer()
        self.binance_feeder = BinanceClient(is_futures=False, testnet=False)

        # State tracking for Dashboard
        self.latest_signals: List[Dict[str, Any]] = []
        self.market_prices: Dict[str, float] = {}

    def start(self):
        """Start the trading bot loop thread."""
        if self.running:
            return
        self.running = True
        self.paused = False

        acc = self.broker.get_account_balance()
        self.risk_manager.set_starting_equity(acc.get("wallet_balance", 60.0))

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Crypto Strategy Runner started for symbols: {self.symbols} with AI Overseer Agent active")

    def stop(self):
        self.running = False
        logger.info("Crypto Strategy Runner stopped.")

    def pause(self):
        self.paused = True
        logger.info("Crypto Strategy Runner paused.")

    def resume(self):
        self.paused = False
        logger.info("Crypto Strategy Runner resumed.")

    def _fetch_klines_fallback(self, symbol: str) -> pd.DataFrame:
        """Fetch kline candles or generate fallback data."""
        # Convert BTC to BTCUSDT if needed for feeder
        feed_sym = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol
        df = self.binance_feeder.get_klines(feed_sym, interval=self.interval, limit=100)
        if not df.empty:
            return df

        import numpy as np
        logger.warning(f"Generating synthetic candle feed for {symbol} test")
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

    @staticmethod
    def _estimate_cp_ratio(df: pd.DataFrame) -> float:
        """
        Estimate the Call/Put volume ratio from OHLCV candle data.
        Up-volume candles (close > open) proxy Call activity.
        Down-volume candles (close < open) proxy Put activity.
        From real data: BTC bullish 42% of hours, ETH 36%.
        """
        if df.empty or len(df) < 10:
            return 0.50
        recent = df.tail(20).copy()
        up_vol   = recent[recent["close"] > recent["open"]]["volume"].sum()
        down_vol = recent[recent["close"] < recent["open"]]["volume"].sum()
        total = up_vol + down_vol
        if total == 0:
            return 0.50
        return float(round(up_vol / total, 3))

    def _run_loop(self):
        while self.running:
            if not self.paused:
                try:
                    for symbol in self.symbols:
                        df = self._fetch_klines_fallback(symbol)
                        df.attrs["symbol"] = symbol
                        current_price = float(df.iloc[-1]["close"])
                        self.market_prices[symbol] = current_price

                        # Compute & feed C/P ratio to AI Overseer
                        cp_ratio = self._estimate_cp_ratio(df)
                        self.ai_overseer.update_cp_ratio(symbol, cp_ratio)

                        # Update Paper Brokers
                        if hasattr(self.broker, "update_prices"):
                            self.broker.update_prices({symbol: current_price})

                        # Evaluate strategies
                        for strategy in self.strategies:
                            signal = strategy.generate_signal(df)
                            signal["underlying"] = symbol

                            action = signal.get("action", "HOLD")
                            if action in ["BUY", "SELL", "BUY_CALL", "BUY_PUT", "SHORT_STRADDLE", "BULL_PUT_SPREAD"]:
                                acc = self.broker.get_account_balance()
                                
                                # AI OVERSEER EVALUATION STEP
                                ai_eval = self.ai_overseer.evaluate_signal(signal, df, acc)
                                decision = ai_eval.get("decision", "CONFIRM")

                                self.latest_signals.insert(0, {
                                    "symbol": signal.get("symbol", symbol),
                                    "action": action,
                                    "strategy": f"{strategy.name} (AI: {decision})",
                                    "price": current_price,
                                    "reason": ai_eval.get("reasoning", signal.get("reason", "")),
                                    "timestamp": time.strftime("%H:%M:%S")
                                })
                                self.latest_signals = self.latest_signals[:20]

                                if decision == "CONFIRM":
                                    logger.info(f"[TRADE APPROVED BY AI] {symbol} [{action}] by {strategy.name} | Spot: ${current_price:.2f}")
                                    
                                    # For options, size contracts
                                    if isinstance(self.broker, PaperDeltaBroker):
                                        qty = 1.0  # 1 contract
                                        self.executor.execute_trade(symbol, signal, qty)
                                    elif self.risk_manager.validate_signal(signal, acc.get("total_equity", 60.0)):
                                        qty = self.risk_manager.calculate_position_size(current_price, acc.get("available", 60.0))
                                        if qty > 0:
                                            self.executor.execute_trade(symbol, signal, qty)
                                else:
                                    logger.warning(f"[TRADE VETOED BY AI OVERSEER] {symbol} [{action}] Vetoed: {ai_eval.get('reasoning')}")
                except Exception as e:
                    logger.error(f"Error in strategy runner loop: {e}")

            time.sleep(5)  # 5-second tick interval
