"""
paper_spot_broker.py — Paper Spot Trading Broker for ETH/BTC.

No theta decay. Clean buy/sell mechanics.
Used as the primary broker for spot momentum scalping (Strategy A).
Capital allocation: $600 of the $1,000 total.
"""

from typing import Dict, Any, List, Optional
import time
from binance_crypto_bot.utils.logger import logger

TAKER_FEE = 0.001   # 0.1% spot taker fee (Binance/Delta standard)


class PaperSpotBroker:
    def __init__(self, initial_capital: float = 600.0, max_positions: int = 5):
        self.wallet_balance  = initial_capital
        self.initial_capital = initial_capital
        self.max_positions   = max_positions
        self.positions:      Dict[str, Dict[str, Any]] = {}
        self.trade_history:  List[Dict[str, Any]] = []
        self.realized_pnl    = 0.0
        self.mode            = "paper"

    def connect(self) -> bool:
        logger.info(
            f"Paper Spot Broker initialized with ${self.wallet_balance:.2f} USDT "
            f"(Max Positions: {self.max_positions} | Fee: {TAKER_FEE*100:.2f}%)"
        )
        return True

    def get_account_balance(self) -> Dict[str, float]:
        unrealized = self.get_total_unrealized_pnl()
        used_margin = sum(p["cost"] for p in self.positions.values())
        return {
            "wallet_balance": round(self.wallet_balance, 4),
            "available":      round(self.wallet_balance - used_margin, 4),
            "unrealized_pnl": round(unrealized, 4),
            "total_equity":   round(self.wallet_balance + unrealized, 4),
        }

    def get_total_unrealized_pnl(self) -> float:
        return sum(p.get("unrealized_pnl", 0.0) for p in self.positions.values())

    def place_order(
        self,
        symbol:     str,
        side:       str,   # "BUY" or "SELL"
        price:      float,
        qty:        float,
        tp_price:   Optional[float] = None,
        sl_price:   Optional[float] = None,
    ) -> Dict[str, Any]:
        """Open a spot long position."""
        if side != "BUY":
            return {"status": "REJECTED", "reason": "Only BUY (long) supported in paper spot"}

        if len(self.positions) >= self.max_positions:
            return {"status": "REJECTED", "reason": f"Max positions reached ({self.max_positions})"}

        # One position per symbol
        for pos in self.positions.values():
            if pos["symbol"] == symbol:
                return {"status": "REJECTED", "reason": f"Position already open for {symbol}"}

        cost = price * qty
        fee  = cost * TAKER_FEE
        total_cost = cost + fee

        if total_cost > (self.wallet_balance - sum(p["cost"] for p in self.positions.values())):
            return {"status": "REJECTED", "reason": "Insufficient funds"}

        order_id = f"SPOT-PAPER-{int(time.time() * 1000)}"
        pos_key  = f"{symbol}-{order_id}"

        self.positions[pos_key] = {
            "pos_key":        pos_key,
            "symbol":         symbol,
            "side":           "BUY",
            "qty":            qty,
            "entry_price":    price,
            "current_price":  price,
            "cost":           total_cost,
            "tp_price":       tp_price,
            "sl_price":       sl_price,
            "unrealized_pnl": 0.0,
            "opened_at":      time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        logger.info(
            f"[SPOT FILLED] BUY {qty:.6f} {symbol} @ ${price:.2f} | "
            f"Cost: ${total_cost:.4f} | TP: ${tp_price} | SL: ${sl_price}"
        )
        return {"status": "FILLED", "order_id": order_id, "pos_key": pos_key}

    def update_prices(self, current_prices: Dict[str, float]):
        """Mark-to-market all open positions and check TP/SL."""
        for pos_key, pos in list(self.positions.items()):
            sym   = pos["symbol"]
            price = current_prices.get(sym)
            if price is None:
                continue

            pos["current_price"]  = price
            pos["unrealized_pnl"] = round((price - pos["entry_price"]) * pos["qty"], 4)

            # Take Profit
            if pos["tp_price"] and price >= pos["tp_price"]:
                self._close_position(pos_key, price, "Take Profit Hit (+1.5%)")
                continue

            # Stop Loss
            if pos["sl_price"] and price <= pos["sl_price"]:
                self._close_position(pos_key, price, "Stop Loss Hit (-0.8%)")
                continue

    def _close_position(self, pos_key: str, exit_price: float, reason: str):
        pos       = self.positions.pop(pos_key)
        gross_pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        fee       = exit_price * pos["qty"] * TAKER_FEE
        net_pnl   = gross_pnl - fee

        self.wallet_balance += net_pnl
        self.realized_pnl   += net_pnl

        record = {
            "symbol":      pos["symbol"],
            "side":        "SPOT BUY",
            "qty":         pos["qty"],
            "entry_price": pos["entry_price"],
            "exit_price":  exit_price,
            "gross_pnl":   round(gross_pnl, 4),
            "fees":        round(fee,       4),
            "pnl":         round(net_pnl,   4),
            "reason":      reason,
            "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.trade_history.append(record)
        logger.info(
            f"[SPOT CLOSED] {pos['symbol']} @ ${exit_price:.2f} | "
            f"Net P&L: ${net_pnl:+.4f} ({reason})"
        )

    def square_off_all(self, current_prices: Dict[str, float]):
        for pos_key in list(self.positions.keys()):
            sym   = self.positions[pos_key]["symbol"]
            price = current_prices.get(sym, self.positions[pos_key]["entry_price"])
            self._close_position(pos_key, price, "Manual Square-Off")
