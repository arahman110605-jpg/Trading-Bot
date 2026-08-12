"""
order_executor.py — Unified Order Execution Engine for Binance CEX, Delta Options, Web3 DEX, and Paper Trading.
"""

from typing import Dict, Any, Optional
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.paper_delta_broker import PaperDeltaBroker
from binance_crypto_bot.broker.binance_client import BinanceClient
from binance_crypto_bot.broker.delta_option_client import DeltaOptionClient
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

        logger.info(f"[EXECUTOR] Triggering {action} order for {symbol} @ ${price:.2f}")

        # Paper Delta Options Execution
        if hasattr(self.broker, "place_option_order"):
            strike = signal.get("strike", signal.get("sell_strike", price))
            opt_type = signal.get("option_type", "CALL")
            opt_symbol = signal.get("symbol") or signal.get("call_symbol") or f"{'C' if opt_type=='CALL' else 'P'}-{symbol}-{int(strike)}"
            underlying = signal.get("underlying", symbol)
            premium = signal.get("premium", signal.get("total_premium", signal.get("net_credit", 20.0)))
            contracts = max(int(quantity), 1)

            return self.broker.place_option_order(
                option_symbol=opt_symbol,
                underlying=underlying,
                option_type=opt_type,
                strike=strike,
                spot_price=price,
                contracts=contracts,
                premium=premium,
                sl_premium=sl,
                tp_premium=tp
            )

        # Real Delta Exchange Execution
        elif isinstance(self.broker, DeltaOptionClient):
            opt_symbol = signal.get("symbol", f"C-{symbol}-60000")
            side = "buy" if "BUY" in action else "sell"
            size = max(int(quantity), 1)
            res = self.broker.create_order(opt_symbol, side, "market_order", size)
            return {"status": "FILLED", "raw": res}

        # Paper Spot/Futures Execution
        elif isinstance(self.broker, PaperCryptoBroker):
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
            amount_in_wei = int(quantity * (10**18))
            return self.broker.execute_swap(token_in="0x...", token_out="0x...", amount_in_wei=amount_in_wei)

        return {"status": "FAILED", "reason": "Unknown broker instance"}

    def square_off_all(self, current_prices: Dict[str, float]):
        """Emergency square off all active positions."""
        logger.warning("[EXECUTOR] Emergency Square-off triggered for all positions!")
        if isinstance(self.broker, PaperDeltaBroker):
            for sym, pos in list(self.broker.positions.items()):
                self.broker.close_position(sym, pos["current_premium"], reason="Emergency Square Off")
        elif isinstance(self.broker, PaperCryptoBroker):
            symbols = list(self.broker.positions.keys())
            for sym in symbols:
                exit_price = current_prices.get(sym, self.broker.positions[sym]["current_price"])
                self.broker.close_position(sym, exit_price, reason="Emergency Square Off")
