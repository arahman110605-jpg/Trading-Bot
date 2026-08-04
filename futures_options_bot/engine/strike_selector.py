"""
strike_selector.py — Strike Selection Engine for F&O Trading.

Maps underlying spot price & strategy signal to the exact Option Strike (ATM, ITM, OTM).
"""

from futures_options_bot.config import STRIKE_STEP_SIZES, LOT_SIZES
from futures_options_bot.utils.expiry_helper import get_current_expiry
from futures_options_bot.utils.logger import logger


class StrikeSelector:

    @staticmethod
    def get_atm_strike(symbol: str, spot_price: float) -> float:
        """Finds the nearest At-The-Money (ATM) strike price."""
        step = STRIKE_STEP_SIZES.get(symbol.upper(), 50)
        atm = round(spot_price / step) * step
        return float(atm)

    @staticmethod
    def select_strike(
        symbol: str,
        spot_price: float,
        option_type: str,
        offset: int = 0
    ) -> dict:
        """
        Selects exact strike price based on offset from ATM.

        offset:
          0  => ATM (At The Money)
          1  => ITM1 (Calls: ATM - 1 step, Puts: ATM + 1 step)
         -1  => OTM1 (Calls: ATM + 1 step, Puts: ATM - 1 step)
        """
        opt_type = option_type.upper()
        step = STRIKE_STEP_SIZES.get(symbol.upper(), 50)
        atm = StrikeSelector.get_atm_strike(symbol, spot_price)

        if opt_type == "CE":
            selected_strike = atm - (offset * step) if offset > 0 else atm + (abs(offset) * step) if offset < 0 else atm
        elif opt_type == "PE":
            selected_strike = atm + (offset * step) if offset > 0 else atm - (abs(offset) * step) if offset < 0 else atm
        else:  # Futures
            selected_strike = atm

        expiry = get_current_expiry(symbol)
        lot_size = LOT_SIZES.get(symbol.upper(), 25)

        trading_symbol = f"{symbol.upper()}{expiry.strftime('%d%b').upper()}{int(selected_strike)}{opt_type}" if opt_type != "FUT" else f"{symbol.upper()}-{expiry.strftime('%b').upper()}-FUT"

        return {
            "symbol": symbol.upper(),
            "spot_price": spot_price,
            "atm_strike": atm,
            "selected_strike": selected_strike,
            "option_type": opt_type,
            "offset": offset,
            "expiry_date": expiry,
            "lot_size": lot_size,
            "trading_symbol": trading_symbol,
        }
