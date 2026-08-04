"""
order_manager.py — F&O Order Execution Manager.
"""

from futures_options_bot.broker.base_broker import BaseFOBroker
from futures_options_bot.engine.risk_manager import FORiskManager
from futures_options_bot.utils.logger import logger


class FOOrderManager:

    def __init__(self, broker: BaseFOBroker, risk_manager: FORiskManager):
        self.broker = broker
        self.risk_manager = risk_manager

    def execute_signal(self, signal: dict) -> dict:
        """
        Processes strategy signal dictionary:
          {
            "action": "BUY" | "SELL",
            "symbol": "NIFTY",
            "option_type": "CE" | "PE" | "FUT",
            "strike": 24500,
            "lots": 2,
            "strategy": "option_buying"
          }
        """
        symbol = signal["symbol"]
        opt_type = signal["option_type"]
        strike = signal["strike"]
        action = signal["action"]
        lots = signal.get("lots", 1)

        # Validate open positions risk
        positions = self.broker.get_positions()
        allowed, reason = self.risk_manager.can_open_trade(len(positions))

        if not allowed:
            logger.warning(f"⚠️ Order rejected by Risk Manager: {reason}")
            return {"status": "REJECTED", "reason": reason}

        # Submit order to broker
        order_res = self.broker.place_order(
            symbol=symbol,
            option_type=opt_type,
            strike=strike,
            transaction_type=action,
            quantity=lots
        )

        return order_res

    def monitor_and_manage_positions(self):
        """Monitors open positions for SL/Target hits or 3:15 PM square-off."""
        positions = self.broker.get_positions()

        if self.risk_manager.is_auto_square_off_time() and len(positions) > 0:
            logger.info("⏰ 3:15 PM IST reached — Initiating Auto Square-Off for all F&O positions!")
            self.broker.square_off_all()
            return

        for pos in positions:
            symbol = pos["symbol"]
            opt_type = pos["option_type"]
            strike = pos["strike"]
            current_price = pos["current_price"]

            should_close, reason = self.risk_manager.check_stop_loss_target(pos, current_price)
            if should_close:
                logger.info(f"🎯 [AUTO EXIT] Closing {pos['trading_symbol']} — Reason: {reason}")
                exit_action = "SELL" if pos["transaction_type"] == "BUY" else "BUY"
                self.broker.place_order(
                    symbol=symbol,
                    option_type=opt_type,
                    strike=strike,
                    transaction_type=exit_action,
                    quantity=pos["lots"]
                )
