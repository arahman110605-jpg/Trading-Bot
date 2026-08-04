"""
paper_fo_broker.py — Paper Trading Broker Simulator for F&O.
"""

import random
import time
from datetime import datetime, date
from futures_options_bot.broker.base_broker import BaseFOBroker
from futures_options_bot.utils.greeks import calculate_greeks, option_price
from futures_options_bot.utils.expiry_helper import get_current_expiry, get_time_to_expiry_years
from futures_options_bot.utils.logger import logger
from futures_options_bot.config import CAPITAL, LOT_SIZES, STRIKE_STEP_SIZES


class PaperFOBroker(BaseFOBroker):

    def __init__(self):
        self.connected = False
        self.capital = CAPITAL
        self.positions = {}
        self.order_history = []
        # Mock initial spot prices for key Indian indices
        self.spot_prices = {
            "NIFTY": 24500.0,
            "BANKNIFTY": 52200.0,
            "FINNIFTY": 23400.0,
            "RELIANCE": 3050.0,
            "TCS": 4200.0,
            "HDFCBANK": 1650.0,
        }

    def connect(self) -> bool:
        self.connected = True
        logger.info("⚡ [Paper Broker] F&O Simulator Initialized Successfully.")
        return True

    def get_underlying_ltp(self, symbol: str) -> float:
        """Simulates realistic micro-movements in underlying spot price."""
        if symbol not in self.spot_prices:
            self.spot_prices[symbol] = 1000.0

        # Random drift within ±0.15% per tick
        change_pct = random.uniform(-0.0015, 0.0015)
        self.spot_prices[symbol] = round(self.spot_prices[symbol] * (1.0 + change_pct), 2)
        return self.spot_prices[symbol]

    def get_option_chain(self, symbol: str, expiry_date: date = None) -> list:
        """Generates realistic option chain with Black-Scholes prices and greeks."""
        spot = self.get_underlying_ltp(symbol)
        step = STRIKE_STEP_SIZES.get(symbol, 50)
        atm_strike = round(spot / step) * step

        if expiry_date is None:
            expiry_date = get_current_expiry(symbol)

        T = get_time_to_expiry_years(expiry_date)
        chain = []

        # Generate 5 strikes above and 5 strikes below ATM
        for i in range(-5, 6):
            strike = atm_strike + (i * step)
            
            ce_greeks = calculate_greeks(spot, strike, T, option_type="CE")
            pe_greeks = calculate_greeks(spot, strike, T, option_type="PE")

            chain.append({
                "strike": strike,
                "is_atm": (i == 0),
                "ce": {
                    "symbol": f"{symbol}{expiry_date.strftime('%d%b').upper()}{int(strike)}CE",
                    "ltp": ce_greeks["price"],
                    "greeks": ce_greeks,
                },
                "pe": {
                    "symbol": f"{symbol}{expiry_date.strftime('%d%b').upper()}{int(strike)}PE",
                    "ltp": pe_greeks["price"],
                    "greeks": pe_greeks,
                }
            })

        return chain

    def get_option_ltp(self, symbol: str, option_type: str, strike: float, expiry_date: date = None) -> float:
        """Calculates current simulated option premium."""
        spot = self.get_underlying_ltp(symbol)
        if expiry_date is None:
            expiry_date = get_current_expiry(symbol)

        T = get_time_to_expiry_years(expiry_date)
        if option_type.upper() == "FUT":
            # Futures price = Spot + cost of carry (slight premium)
            return round(spot * 1.002, 2)

        return option_price(spot, strike, T, r=0.07, sigma=0.18, option_type=option_type)

    def place_order(self, symbol: str, option_type: str, strike: float,
                    transaction_type: str, quantity: int, order_type: str = "MARKET",
                    price: float = 0.0) -> dict:
        """Executes a paper order for F&O (CE/PE/FUT)."""
        expiry = get_current_expiry(symbol)
        opt_type = option_type.upper()

        if opt_type == "FUT":
            trading_symbol = f"{symbol}-{expiry.strftime('%b').upper()}-FUT"
            execution_price = self.get_underlying_ltp(symbol) if price == 0.0 else price
        else:
            trading_symbol = f"{symbol}{expiry.strftime('%d%b').upper()}{int(strike)}{opt_type}"
            execution_price = self.get_option_ltp(symbol, opt_type, strike, expiry) if price == 0.0 else price

        order_id = f"PAPER_FO_{int(time.time() * 1000)}"
        lot_size = LOT_SIZES.get(symbol, 25)
        total_qty = quantity * lot_size
        cost = execution_price * total_qty

        order_details = {
            "order_id": order_id,
            "symbol": symbol,
            "trading_symbol": trading_symbol,
            "option_type": opt_type,
            "strike": strike,
            "transaction_type": transaction_type.upper(),
            "lots": quantity,
            "quantity": total_qty,
            "entry_price": execution_price,
            "current_price": execution_price,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "status": "COMPLETE",
        }

        # Update position state
        pos_key = trading_symbol
        if pos_key in self.positions:
            pos = self.positions[pos_key]
            if pos["transaction_type"] == transaction_type.upper():
                # Add to existing position
                total_qty_new = pos["quantity"] + total_qty
                avg_price = ((pos["entry_price"] * pos["quantity"]) + cost) / total_qty_new
                pos["quantity"] = total_qty_new
                pos["entry_price"] = round(avg_price, 2)
            else:
                # Square off or reversal
                self._close_position(pos_key, execution_price)
        else:
            self.positions[pos_key] = order_details

        self.order_history.append(order_details)
        logger.info(
            f"📝 [PAPER F&O ORDER] {transaction_type} {quantity} Lots ({total_qty} qty) of "
            f"{trading_symbol} @ ₹{execution_price:.2f} | Order ID: {order_id}"
        )

        return order_details

    def _close_position(self, pos_key: str, exit_price: float):
        if pos_key in self.positions:
            pos = self.positions[pos_key]
            multiplier = 1 if pos["transaction_type"] == "BUY" else -1
            pnl = (exit_price - pos["entry_price"]) * pos["quantity"] * multiplier
            self.capital += pnl
            logger.info(
                f"🎯 [PAPER POSITION CLOSED] {pos_key} | Entry: ₹{pos['entry_price']:.2f} "
                f"| Exit: ₹{exit_price:.2f} | P&L: ₹{pnl:+.2f}"
            )
            del self.positions[pos_key]

    def get_positions(self) -> list:
        """Returns list of open positions with real-time calculated mark-to-market P&L."""
        active_pos_list = []
        for key, pos in list(self.positions.items()):
            symbol = pos["symbol"]
            opt_type = pos["option_type"]
            strike = pos["strike"]

            current_ltp = self.get_option_ltp(symbol, opt_type, strike)
            pos["current_price"] = current_ltp

            multiplier = 1 if pos["transaction_type"] == "BUY" else -1
            unrealized_pnl = (current_ltp - pos["entry_price"]) * pos["quantity"] * multiplier
            pnl_pct = ((current_ltp - pos["entry_price"]) / pos["entry_price"]) * 100.0 * multiplier if pos["entry_price"] > 0 else 0.0

            pos_copy = pos.copy()
            pos_copy["pnl"] = round(unrealized_pnl, 2)
            pos_copy["pnl_pct"] = round(pnl_pct, 2)
            active_pos_list.append(pos_copy)

        return active_pos_list

    def square_off_all(self) -> bool:
        """Closes all open positions immediately."""
        logger.info("🚨 [SQUARE OFF ALL] Closing all open F&O positions...")
        for key, pos in list(self.positions.items()):
            ltp = self.get_option_ltp(pos["symbol"], pos["option_type"], pos["strike"])
            self._close_position(key, ltp)
        return True
