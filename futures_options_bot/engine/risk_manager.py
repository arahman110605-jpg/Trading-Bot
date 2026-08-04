"""
risk_manager.py — F&O Risk Management Engine.
"""

from datetime import datetime
from futures_options_bot.config import (
    CAPITAL, RISK_PER_TRADE_PCT, MAX_DAILY_LOSS_PCT,
    MAX_LOTS_PER_TRADE, MAX_OPEN_POSITIONS, LOT_SIZES,
    OPTION_SL_PCT, OPTION_TARGET_PCT, SQUARE_OFF_HOUR, SQUARE_OFF_MINUTE
)
from futures_options_bot.utils.logger import logger


class FORiskManager:

    def __init__(self, capital: float = CAPITAL):
        self.capital = capital
        self.initial_capital = capital
        self.daily_pnl = 0.0
        self.is_bot_halted = False

    def can_open_trade(self, open_positions_count: int) -> tuple[bool, str]:
        """Validates risk limits before allowing a new F&O trade."""
        if self.is_bot_halted:
            return False, "Bot is halted due to max daily loss breach."

        if open_positions_count >= MAX_OPEN_POSITIONS:
            return False, f"Max open positions limit ({MAX_OPEN_POSITIONS}) reached."

        # Check max daily loss
        max_allowed_loss = (MAX_DAILY_LOSS_PCT / 100.0) * self.initial_capital
        if self.daily_pnl <= -max_allowed_loss:
            self.is_bot_halted = True
            logger.error(f"🛑 [MAX DAILY LOSS BREACH] Loss ₹{abs(self.daily_pnl):.2f} exceeds limit ₹{max_allowed_loss:.2f}. Halting Bot!")
            return False, "Max daily loss limit breached."

        return True, "Approved"

    def calculate_lot_size(self, symbol: str, option_premium: float) -> int:
        """Calculates safe number of lots based on capital risk rules."""
        lot_unit = LOT_SIZES.get(symbol.upper(), 25)
        risk_amount = (RISK_PER_TRADE_PCT / 100.0) * self.capital
        sl_per_unit = option_premium * (OPTION_SL_PCT / 100.0)
        
        if sl_per_unit <= 0:
            return 1

        qty_by_risk = int(risk_amount / sl_per_unit)
        lots_by_risk = max(1, int(qty_by_risk / lot_unit))

        # Enforce maximum lots per order limit
        final_lots = min(lots_by_risk, MAX_LOTS_PER_TRADE)
        return final_lots

    def check_stop_loss_target(self, position: dict, current_price: float) -> tuple[bool, str]:
        """
        Checks if position has hit SL or Target.
        Returns (should_close: bool, reason: str).
        """
        entry_price = position["entry_price"]
        opt_type = position.get("option_type", "CE")
        is_buy = (position["transaction_type"] == "BUY")

        if entry_price <= 0:
            return False, ""

        if is_buy:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
            if pnl_pct <= -OPTION_SL_PCT:
                return True, f"Stop-Loss hit ({pnl_pct:.2f}% <= -{OPTION_SL_PCT}%)"
            elif pnl_pct >= OPTION_TARGET_PCT:
                return True, f"Target hit ({pnl_pct:.2f}% >= +{OPTION_TARGET_PCT}%)"
        else:  # Option Selling / Short
            pnl_pct = ((entry_price - current_price) / entry_price) * 100.0
            if pnl_pct <= -OPTION_SL_PCT:
                return True, f"Short Stop-Loss hit ({pnl_pct:.2f}% <= -{OPTION_SL_PCT}%)"
            elif pnl_pct >= OPTION_TARGET_PCT:
                return True, f"Short Target hit ({pnl_pct:.2f}% >= +{OPTION_TARGET_PCT}%)"

        return False, ""

    def is_auto_square_off_time(self) -> bool:
        """Returns True if current time >= auto square-off threshold (e.g. 3:15 PM IST)."""
        now = datetime.now()
        if now.hour > SQUARE_OFF_HOUR or (now.hour == SQUARE_OFF_HOUR and now.minute >= SQUARE_OFF_MINUTE):
            return True
        return False
