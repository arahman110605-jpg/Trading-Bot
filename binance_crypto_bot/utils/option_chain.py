"""
option_chain.py — Strike Selection & Option Symbol Resolver for Crypto Options.
"""

from typing import Dict, Any, List
import time
from datetime import datetime, timedelta
from binance_crypto_bot.config import OPTION_STRIKE_STEPS

def get_atm_strike(spot_price: float, underlying: str = "BTC") -> float:
    """Calculate the nearest At-The-Money (ATM) strike price."""
    step = OPTION_STRIKE_STEPS.get(underlying.upper(), 500)
    return round(spot_price / step) * step

def get_otm_strikes(spot_price: float, underlying: str = "BTC", offset_steps: int = 1) -> Dict[str, float]:
    """Calculate Out-Of-The-Money (OTM) Call and Put strike prices."""
    atm = get_atm_strike(spot_price, underlying)
    step = OPTION_STRIKE_STEPS.get(underlying.upper(), 500)
    
    return {
        "call_otm": atm + (step * offset_steps),
        "put_otm": atm - (step * offset_steps),
        "atm": atm
    }

def format_delta_option_symbol(underlying: str, option_type: str, strike: float, expiry_str: str = "") -> str:
    """
    Format Delta Exchange Option contract symbol string.
    Example: C-BTC-60000-280826 (Call) or P-BTC-60000-280826 (Put)
    """
    opt_prefix = "C" if option_type.upper() in ["CALL", "BUY_CALL", "C"] else "P"
    strike_int = int(strike)
    
    if not expiry_str:
        # Default to upcoming Friday / daily expiry (DDMMYY format)
        today = datetime.now()
        days_ahead = (4 - today.weekday()) % 7  # 4 = Friday
        if days_ahead == 0 and today.hour >= 12:
            days_ahead = 7
        expiry_dt = today + timedelta(days=days_ahead)
        expiry_str = expiry_dt.strftime("%d%m%y")

    return f"{opt_prefix}-{underlying.upper()}-{strike_int}-{expiry_str}"
