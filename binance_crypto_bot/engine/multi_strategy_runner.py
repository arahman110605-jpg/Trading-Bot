"""
multi_strategy_runner.py — Runs Spot + Options strategies on separate brokers simultaneously.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │  $1,000 Total Paper Capital                                 │
  │                                                             │
  │  PaperSpotBroker ($600)                                     │
  │    └─ EthSpotScalperStrategy  (TP +1.5%, SL -0.8%)         │
  │         └─ AI Overseer vets every signal                    │
  │                                                             │
  │  PaperDeltaBroker ($300 + $100 buffer)                      │
  │    ├─ DeltaOptionSellerStrategy  (ADX < 18 → sell OTM)     │
  │    └─ DeltaOptionScalperStrategy (ADX > 22 → buy on spike) │
  │         └─ AI Overseer vets every signal                    │
  └─────────────────────────────────────────────────────────────┘

Dashboard exposes combined balance, positions, signals, and AI logs.
"""

import time
import threading
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from binance_crypto_bot.broker.paper_spot_broker import PaperSpotBroker
from binance_crypto_bot.broker.paper_delta_broker import PaperDeltaBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.strategies.base_strategy import BaseCryptoStrategy
from binance_crypto_bot.engine.ai_overseer_agent import AIStrategyOverseer
from binance_crypto_bot.utils.logger import logger


class MultiStrategyRunner:
    """
    Runs spot and options strategies concurrently on separate paper brokers.
    Exposes unified status to the dashboard via the same interface as CryptoStrategyRunner.
    """

    def __init__(
        self,
        spot_broker:        PaperSpotBroker,
        options_broker:     PaperDeltaBroker,
        spot_strategies:    List[BaseCryptoStrategy],
        options_strategies: List[BaseCryptoStrategy],
        symbols:            List[str],
        interval:           str = "5m",
    ):
        self.spot_broker        = spot_broker
        self.options_broker     = options_broker
        self.spot_strategies    = spot_strategies
        self.options_strategies = options_strategies
        self.symbols            = symbols
        self.interval           = interval

        self.running = False
        self.paused  = False
        self._thread: threading.Thread = None

        self.ai_overseer   = AIStrategyOverseer(confidence_threshold=0.70)
        self.binance_feeder= BinanceClient(is_futures=False, testnet=False)

        # Dashboard state
        self.latest_signals:  List[Dict[str, Any]] = []
        self.market_prices:   Dict[str, float]     = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Dashboard-compatible interface
    # ──────────────────────────────────────────────────────────────────────────

    def get_account_balance(self) -> Dict[str, float]:
        """Combined balance across both brokers."""
        spot = self.spot_broker.get_account_balance()
        opts = self.options_broker.get_account_balance()
        return {
            "wallet_balance": round(spot["wallet_balance"] + opts["wallet_balance"], 2),
            "available":      round(spot["available"]     + opts["available"],      2),
            "unrealized_pnl": round(spot["unrealized_pnl"]+ opts["unrealized_pnl"],2),
            "total_equity":   round(spot["total_equity"]  + opts["total_equity"],   2),
            "spot_balance":   spot["wallet_balance"],
            "options_balance":opts["wallet_balance"],
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """Combined positions from both brokers."""
        all_pos = []
        for pos in self.spot_broker.positions.values():
            all_pos.append({**pos, "broker": "SPOT"})
        for pos in self.options_broker.positions.values():
            all_pos.append({**pos, "broker": "OPTIONS"})
        return all_pos

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Combined trade history from both brokers."""
        hist = (
            [{"broker": "SPOT",    **t} for t in self.spot_broker.trade_history] +
            [{"broker": "OPTIONS", **t} for t in self.options_broker.trade_history]
        )
        return sorted(hist, key=lambda x: x.get("timestamp", ""), reverse=True)

    def square_off_all(self):
        prices = {s: self.market_prices.get(s, 0) for s in self.symbols}
        self.spot_broker.square_off_all(prices)
        for pos_key in list(self.options_broker.positions.keys()):
            sym   = self.options_broker.positions[pos_key]["underlying"]
            price = prices.get(sym, self.options_broker.positions[pos_key]["entry_premium"])
            self.options_broker.close_position(pos_key, price, "Manual Square-Off")

    # ──────────────────────────────────────────────────────────────────────────
    # Bot controls
    # ──────────────────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self.paused  = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"[MULTI-RUNNER] Started — Symbols: {self.symbols} | "
            f"Spot: ${self.spot_broker.wallet_balance} | "
            f"Options: ${self.options_broker.wallet_balance}"
        )

    def stop(self):
        self.running = False
        logger.info("[MULTI-RUNNER] Stopped.")

    def pause(self):
        self.paused = True
        logger.info("[MULTI-RUNNER] Paused.")

    def resume(self):
        self.paused = False
        logger.info("[MULTI-RUNNER] Resumed.")

    # ──────────────────────────────────────────────────────────────────────────
    # Core loop
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_cp_ratio(df: pd.DataFrame) -> float:
        if df.empty or len(df) < 10:
            return 0.50
        recent = df.tail(20).copy()
        up   = recent[recent["close"] > recent["open"]]["volume"].sum()
        down = recent[recent["close"] < recent["open"]]["volume"].sum()
        total = up + down
        return float(round(up / total, 3)) if total > 0 else 0.50

    def _fetch_klines(self, symbol: str) -> pd.DataFrame:
        feed_sym = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol
        df = self.binance_feeder.get_klines(feed_sym, interval=self.interval, limit=100)
        if not df.empty:
            return df
        # Synthetic fallback
        import numpy as np
        now   = pd.Timestamp.now()
        times = [now - pd.Timedelta(minutes=5*i) for i in range(100)][::-1]
        base  = 63000.0 if "BTC" in symbol else 1900.0
        prices= base + np.cumsum(np.random.normal(0, base*0.001, 100))
        return pd.DataFrame({
            "open_time": times, "open": prices*0.999, "high": prices*1.002,
            "low": prices*0.998, "close": prices,
            "volume": np.random.uniform(10, 100, 100)
        })

    def _run_loop(self):
        while self.running:
            if not self.paused:
                try:
                    current_prices: Dict[str, float] = {}

                    for symbol in self.symbols:
                        df = self._fetch_klines(symbol)
                        df.attrs["symbol"] = symbol
                        price = float(df.iloc[-1]["close"])
                        self.market_prices[symbol] = price
                        current_prices[symbol]     = price

                        cp_ratio = self._estimate_cp_ratio(df)
                        self.ai_overseer.update_cp_ratio(symbol, cp_ratio)

                        # ── Update open positions on both brokers ──────────
                        self.spot_broker.update_prices(current_prices)
                        self.options_broker.update_prices(current_prices)

                        acc_combined = self.get_account_balance()
                        acc_spot     = self.spot_broker.get_account_balance()
                        acc_options  = self.options_broker.get_account_balance()

                        # ── Run SPOT strategies ───────────────────────────
                        for strategy in self.spot_strategies:
                            signal = strategy.generate_signal(df)
                            signal["underlying"] = symbol
                            action = signal.get("action", "HOLD")

                            if action == "BUY":
                                ai_eval  = self.ai_overseer.evaluate_signal(signal, df, acc_spot)
                                decision = ai_eval["decision"]

                                self._log_signal(signal, ai_eval, price, strategy)

                                if decision == "CONFIRM":
                                    qty = signal.get("qty", 0)
                                    if qty > 0:
                                        self.spot_broker.place_order(
                                            symbol    = symbol,
                                            side      = "BUY",
                                            price     = price,
                                            qty       = qty,
                                            tp_price  = signal.get("tp_price"),
                                            sl_price  = signal.get("sl_price"),
                                        )

                        # ── Run OPTIONS strategies ────────────────────────
                        for strategy in self.options_strategies:
                            signal = strategy.generate_signal(df)
                            signal["underlying"] = symbol
                            action = signal.get("action", "HOLD")

                            if action in ["BUY_CALL", "BUY_PUT", "SELL_OPTION"]:
                                ai_eval  = self.ai_overseer.evaluate_signal(signal, df, acc_options)
                                decision = ai_eval["decision"]

                                self._log_signal(signal, ai_eval, price, strategy)

                                # Option seller gets through if AI doesn't flag risk
                                if decision == "CONFIRM" or (
                                    action == "SELL_OPTION" and
                                    ai_eval["confidence_score"] >= 0.40
                                ):
                                    premium = signal.get("premium", 0)
                                    if premium > 0:
                                        if action == "SELL_OPTION":
                                            self.options_broker.sell_option(
                                                option_symbol = signal["symbol"],
                                                underlying    = signal["underlying"],
                                                option_type   = signal["option_type"],
                                                strike        = signal["strike"],
                                                spot_price    = price,
                                                contracts     = 1,
                                                premium       = premium,
                                                tp_premium    = signal.get("tp_premium"),
                                                sl_premium    = signal.get("sl_premium"),
                                            )
                                        else:
                                            self.options_broker.place_option_order(
                                                option_symbol = signal["symbol"],
                                                underlying    = signal["underlying"],
                                                option_type   = signal["option_type"],
                                                strike        = signal["strike"],
                                                spot_price    = price,
                                                contracts     = 1,
                                                premium       = premium,
                                                sl_premium    = signal.get("stop_loss"),
                                                tp_premium    = signal.get("take_profit"),
                                            )
                except Exception as e:
                    logger.error(f"[MULTI-RUNNER] Error in loop: {e}", exc_info=True)

            time.sleep(5)

    def _log_signal(self, signal, ai_eval, price, strategy):
        action   = signal.get("action", "HOLD")
        decision = ai_eval.get("decision", "VETO")
        entry = {
            "symbol":    signal.get("symbol", signal.get("underlying", "")),
            "action":    action,
            "strategy":  f"{strategy.name} (AI: {decision})",
            "price":     price,
            "reason":    ai_eval.get("reasoning", signal.get("reason", "")),
            "timestamp": time.strftime("%H:%M:%S"),
        }
        self.latest_signals.insert(0, entry)
        self.latest_signals = self.latest_signals[:25]
