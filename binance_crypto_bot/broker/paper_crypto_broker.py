"""
paper_crypto_broker.py — Paper Trading Broker Simulator for Crypto (Spot & Futures).
"""

from typing import Dict, Any, List, Optional
import time
from binance_crypto_bot.config import CAPITAL, LEVERAGE
from binance_crypto_bot.utils.logger import logger

class PaperCryptoBroker:
    def __init__(self, initial_capital: float = CAPITAL, default_leverage: int = LEVERAGE):
        self.wallet_balance = initial_capital
        self.initial_capital = initial_capital
        self.leverage = default_leverage
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.realized_pnl = 0.0

    def connect(self) -> bool:
        logger.info(f"Paper Crypto Broker initialized with ${self.wallet_balance:.2f} USDT capital ({self.leverage}x leverage).")
        return True

    def get_account_balance(self) -> Dict[str, float]:
        unrealized = self.get_total_unrealized_pnl()
        return {
            "wallet_balance": round(self.wallet_balance, 2),
            "available": round(self.wallet_balance - self._get_used_margin(), 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_equity": round(self.wallet_balance + unrealized, 2)
        }

    def _get_used_margin(self) -> float:
        margin = 0.0
        for pos in self.positions.values():
            margin += (pos["size"] * pos["entry_price"]) / self.leverage
        return margin

    def get_total_unrealized_pnl(self) -> float:
        total = 0.0
        for pos in self.positions.values():
            total += pos.get("unrealized_pnl", 0.0)
        return total

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        self.leverage = leverage
        logger.info(f"[PAPER] Leverage set to {leverage}x for {symbol}")
        return True

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: float, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]:
        """Simulate placing a market or limit order."""
        side = side.upper()
        margin_required = (quantity * price) / self.leverage

        if margin_required > (self.wallet_balance - self._get_used_margin()):
            logger.warning(f"[PAPER REJECTED] Insufficient margin for {quantity} {symbol} @ ${price:.2f}")
            return {"status": "REJECTED", "reason": "Insufficient Margin"}

        order_id = f"PAPER-{int(time.time() * 1000)}"
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.orders.append(order)

        # Update position
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos["side"] == side:
                # Add to existing position
                total_qty = pos["size"] + quantity
                avg_entry = ((pos["size"] * pos["entry_price"]) + (quantity * price)) / total_qty
                pos["size"] = total_qty
                pos["entry_price"] = avg_entry
            else:
                # Close or reverse position
                self.close_position(symbol, price, reason="Reverse Signal")
                if quantity > 0:
                    self._create_position(symbol, side, quantity, price, sl, tp)
        else:
            self._create_position(symbol, side, quantity, price, sl, tp)

        logger.info(f"[PAPER ORDER FILLED] {side} {quantity:.4f} {symbol} @ ${price:.2f} | Leverage: {self.leverage}x")
        return order

    def _create_position(self, symbol: str, side: str, quantity: float, price: float, sl: Optional[float], tp: Optional[float]):
        liquidation_buffer = (price / self.leverage) * 0.9  # Approx liquidation price
        liq_price = price - liquidation_buffer if side == "BUY" else price + liquidation_buffer

        self.positions[symbol] = {
            "symbol": symbol,
            "side": side,
            "size": quantity,
            "entry_price": price,
            "current_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "liquidation_price": max(0.0, liq_price),
            "unrealized_pnl": 0.0,
            "leverage": self.leverage,
            "opened_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def update_prices(self, current_prices: Dict[str, float]):
        """Update open positions with current live price feeds & check SL/TP/Liquidation."""
        for symbol, current_price in current_prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos["current_price"] = current_price
                
                # Calculate P&L
                if pos["side"] == "BUY":
                    pnl = (current_price - pos["entry_price"]) * pos["size"]
                else:
                    pnl = (pos["entry_price"] - current_price) * pos["size"]
                
                pos["unrealized_pnl"] = round(pnl, 2)

                # Check Stop Loss
                if pos["stop_loss"] is not None:
                    if pos["side"] == "BUY" and current_price <= pos["stop_loss"]:
                        self.close_position(symbol, current_price, reason="Stop Loss Triggered")
                        continue
                    elif pos["side"] == "SELL" and current_price >= pos["stop_loss"]:
                        self.close_position(symbol, current_price, reason="Stop Loss Triggered")
                        continue

                # Check Take Profit
                if pos["take_profit"] is not None:
                    if pos["side"] == "BUY" and current_price >= pos["take_profit"]:
                        self.close_position(symbol, current_price, reason="Take Profit Triggered")
                        continue
                    elif pos["side"] == "SELL" and current_price <= pos["take_profit"]:
                        self.close_position(symbol, current_price, reason="Take Profit Triggered")
                        continue

                # Liquidation Check
                if pos["side"] == "BUY" and current_price <= pos["liquidation_price"]:
                    self.close_position(symbol, current_price, reason="LIQUIDATED")
                elif pos["side"] == "SELL" and current_price >= pos["liquidation_price"]:
                    self.close_position(symbol, current_price, reason="LIQUIDATED")

    def close_position(self, symbol: str, exit_price: float, reason: str = "Manual Exit") -> Dict[str, Any]:
        """Close an existing position."""
        if symbol not in self.positions:
            return {"status": "ERROR", "reason": "No position exists"}

        pos = self.positions.pop(symbol)
        if pos["side"] == "BUY":
            gross_pnl = (exit_price - pos["entry_price"]) * pos["size"]
        else:
            gross_pnl = (pos["entry_price"] - exit_price) * pos["size"]

        # Binance Trading Fee (0.1% Spot / 0.05% Futures per leg)
        fee_rate = 0.0005 if self.leverage > 1 else 0.0010
        entry_val = pos["entry_price"] * pos["size"]
        exit_val = exit_price * pos["size"]
        total_fees = (entry_val + exit_val) * fee_rate

        net_pnl = gross_pnl - total_fees
        self.wallet_balance += net_pnl
        self.realized_pnl += net_pnl

        trade_record = {
            "symbol": symbol,
            "side": pos["side"],
            "size": pos["size"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "gross_pnl": round(gross_pnl, 2),
            "fees": round(total_fees, 4),
            "pnl": round(net_pnl, 2),
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.trade_history.append(trade_record)
        logger.info(f"[PAPER CLOSED] {pos['side']} {symbol} @ ${exit_price:.2f} | Net P&L: ${net_pnl:+.2f} (Fees: ${total_fees:.4f}) ({reason})")
        return trade_record
