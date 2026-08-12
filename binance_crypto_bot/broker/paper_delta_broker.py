"""
paper_delta_broker.py — Delta Crypto Options Paper Trading Simulator.
"""

from typing import Dict, Any, List, Optional
import time
from binance_crypto_bot.config import CAPITAL
from binance_crypto_bot.utils.greeks import calculate_black_scholes
from binance_crypto_bot.utils.logger import logger

class PaperDeltaBroker:
    def __init__(self, initial_capital: float = CAPITAL):
        self.wallet_balance = initial_capital
        self.initial_capital = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.realized_pnl = 0.0

    def connect(self) -> bool:
        logger.info(f"Paper Delta Options Broker initialized with ${self.wallet_balance:.2f} USDT capital.")
        return True

    def calculate_position_size(self, symbol: str, signal_price: float, risk_percentage: float = 0.05) -> float:
        """Calculate position contracts based on capital."""
        return 1.0

    def get_account_balance(self) -> Dict[str, float]:
        unrealized = self.get_total_unrealized_pnl()
        return {
            "wallet_balance": round(self.wallet_balance, 2),
            "available": round(self.wallet_balance - self._get_used_margin(), 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_equity": round(self.wallet_balance + unrealized, 2)
        }

    def _get_used_margin(self) -> float:
        used = 0.0
        for pos in self.positions.values():
            used += pos["entry_premium"] * pos["contracts"]
        return used

    def get_total_unrealized_pnl(self) -> float:
        total = 0.0
        for pos in self.positions.values():
            total += pos.get("unrealized_pnl", 0.0)
        return total

    def place_option_order(
        self,
        option_symbol: str,
        underlying: str,
        option_type: str,
        strike: float,
        spot_price: float,
        contracts: int,
        premium: float,
        sl_premium: Optional[float] = None,
        tp_premium: Optional[float] = None
    ) -> Dict[str, Any]:
        """Simulate buying or selling a Crypto Option contract."""
        side = "BUY"
        total_cost = contracts * premium

        # Limit to max 1 active position for strict capital protection
        if len(self.positions) >= 1:
            return {"status": "REJECTED", "reason": "Active scalp position already open"}

        if total_cost > (self.wallet_balance - self._get_used_margin()):
            logger.warning(f"[PAPER DELTA REJECTED] Insufficient balance for {contracts} contracts of {option_symbol} @ ${premium:.2f}")
            return {"status": "REJECTED", "reason": "Insufficient Funds"}

        # Calculate Greeks
        greeks = calculate_black_scholes(option_type, spot_price, strike, time_to_expiry_years=7/365.0)

        order_id = f"DELTA-PAPER-{int(time.time() * 1000)}"
        order = {
            "order_id": order_id,
            "symbol": option_symbol,
            "side": side,
            "contracts": contracts,
            "entry_premium": premium,
            "status": "FILLED",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.orders.append(order)

        pos_key = f"{option_symbol}-{order_id}"
        self.positions[pos_key] = {
            "pos_key": pos_key,
            "symbol": option_symbol,
            "underlying": underlying,
            "option_type": option_type,
            "strike": strike,
            "side": side,
            "contracts": contracts,
            "entry_premium": premium,
            "current_premium": premium,
            "stop_loss": sl_premium,
            "take_profit": tp_premium,
            "delta": greeks["delta"],
            "theta": greeks["theta"],
            "unrealized_pnl": 0.0,
            "opened_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        logger.info(f"[PAPER OPTION FILLED] {side} {contracts}x {option_symbol} @ Premium ${premium:.2f} | Strike: ${strike} | Delta: {greeks['delta']}")
        return order

    def update_prices(self, current_spot_prices: Dict[str, float]):
        """Update active option positions with current spot prices & Black-Scholes theoretical premiums."""
        for pos_key, pos in list(self.positions.items()):
            spot_price = current_spot_prices.get(pos["underlying"], pos["strike"])
            
            # Recalculate option premium & greeks via Black-Scholes
            greeks = calculate_black_scholes(pos["option_type"], spot_price, pos["strike"], time_to_expiry_years=7/365.0)
            current_premium = greeks["theoretical_price"]
            
            pos["current_premium"] = current_premium
            pos["delta"] = greeks["delta"]
            pos["theta"] = greeks["theta"]
            
            pnl = (current_premium - pos["entry_premium"]) * pos["contracts"]
            pos["unrealized_pnl"] = round(pnl, 2)

            # Trailing Stop Loss to Breakeven once gain reaches +4%
            if current_premium >= pos["entry_premium"] * 1.04:
                pos["stop_loss"] = max(pos["stop_loss"], pos["entry_premium"])

            # Stop Loss Trigger check
            if pos["stop_loss"] is not None and current_premium <= pos["stop_loss"]:
                self.close_position(pos_key, current_premium, reason="Option Stop Loss Triggered")
                continue

            # Take Profit Trigger check
            if pos["take_profit"] is not None and current_premium >= pos["take_profit"]:
                self.close_position(pos_key, current_premium, reason="Option Take Profit Triggered")
                continue

    def close_position(self, symbol: str, exit_premium: float, reason: str = "Manual Exit") -> Dict[str, Any]:
        """Close an open Option position."""
        if symbol not in self.positions:
            return {"status": "ERROR", "reason": "Position not found"}

        pos = self.positions.pop(symbol)
        gross_pnl = (exit_premium - pos["entry_premium"]) * pos["contracts"]

        # Delta Option Trading Fee (0.03% of contract value)
        contract_val = pos["strike"] * 0.001 * pos["contracts"]  # Approx value
        total_fee = contract_val * 0.0003 * 2  # Entry + Exit
        net_pnl = gross_pnl - total_fee

        self.wallet_balance += net_pnl
        self.realized_pnl += net_pnl

        trade_record = {
            "symbol": pos.get("symbol", symbol),
            "option_type": pos["option_type"],
            "strike": pos["strike"],
            "contracts": pos["contracts"],
            "entry_premium": pos["entry_premium"],
            "exit_premium": exit_premium,
            "gross_pnl": round(gross_pnl, 2),
            "fees": round(total_fee, 4),
            "pnl": round(net_pnl, 2),
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.trade_history.append(trade_record)
        logger.info(f"[PAPER OPTION CLOSED] {pos['option_type']} {symbol} @ ${exit_premium:.2f} | Net P&L: ${net_pnl:+.2f} ({reason})")
        return trade_record
