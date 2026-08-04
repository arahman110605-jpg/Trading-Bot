"""
order_executor.py — Unified Order Execution Engine for Binance CEX, Web3 DEX, and Paper Trading.
"""

from typing import Dict, Any, Optional
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.broker.web3_dex_client import Web3DexClient
from binance_crypto_bot.utils.logger import logger

class CryptoOrderExecutor:
    def __init__(self, broker: Any):
        self.broker = broker

    def execute_trade(self, symbol: str, signal: Dict[str, Any], quantity: float) -> Dict[str, Any]:
        action = signal.get("action")
        price = signal.get("price", 0.0)
        sl = signal.get("stop_loss")
        tp = signal.get("take_profit")

        if quantity <= 0 or price <= 0:
            return {"status": "FAILED", "reason": "Invalid quantity or price"}

        logger.info(f"[EXECUTOR] Triggering {action} order for {quantity} {symbol} @ ${price:.2f}")

        # Paper Broker Execution
        if isinstance(self.broker, PaperCryptoBroker):
            return self.broker.place_order(symbol, action, "MARKET", quantity, price, sl, tp)

        # Binance CEX Execution
        elif isinstance(self.broker, BinanceClient):
            res = self.broker.create_order(symbol, action, "MARKET", quantity)
            if "orderId" in res:
                logger.info(f"[BINANCE LIVE ORDER] Placed successfully ID: {res['orderId']}")
                return {"status": "FILLED", "order_id": res["orderId"], "raw": res}
            else:
                logger.error(f"[BINANCE LIVE ORDER FAILED] {res}")
                return {"status": "FAILED", "error": res}

        # Web3 DEX Execution
        elif isinstance(self.broker, Web3DexClient):
            # Token swap execution
            amount_in_wei = int(quantity * (10**18))
            return self.broker.execute_swap(token_in="0x...", token_out="0x...", amount_in_wei=amount_in_wei)

        return {"status": "FAILED", "reason": "Unknown broker instance"}

    def square_off_all(self, current_prices: Dict[str, float]):
        """Emergency square off all active positions."""
        logger.warning("[EXECUTOR] Emergency Square-off triggered for all positions!")
        if isinstance(self.broker, PaperCryptoBroker):
            symbols = list(self.broker.positions.keys())
            for sym in symbols:
                exit_price = current_prices.get(sym, self.broker.positions[sym]["current_price"])
                self.broker.close_position(sym, exit_price, reason="Emergency Square Off")
