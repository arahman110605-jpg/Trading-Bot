"""
expiry_helper.py — Indian F&O Expiry Calendar & Symbol Formatting Utility.
"""

from datetime import datetime, date, timedelta


def get_next_weekday(start_date: date, weekday: int) -> date:
    """
    Finds the next occurrence of a weekday.
    weekday: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday...
    """
    days_ahead = weekday - start_date.weekday()
    if days_ahead < 0:  # Target day already passed this week
        days_ahead += 7
    return start_date + timedelta(days=days_ahead)


def get_monthly_expiry(symbol: str, target_year: int, target_month: int) -> date:
    """
    Calculates the last Thursday (or specified day) of the month for Indian stock/index F&O.
    NIFTY/BANKNIFTY monthly options expire on the last Thursday of the month.
    """
    # Start at the last day of the month
    if target_month == 12:
        next_month = date(target_year + 1, 1, 1)
    else:
        next_month = date(target_year, target_month + 1, 1)
    last_day = next_month - timedelta(days=1)

    # Walk backwards to find the last Thursday (weekday 3)
    offset = (last_day.weekday() - 3) % 7
    last_thursday = last_day - timedelta(days=offset)
    return last_thursday


def get_current_expiry(symbol: str = "NIFTY", preference: str = "current_week") -> date:
    """
    Returns the target expiry date for NIFTY, BANKNIFTY, FINNIFTY, or stock options.
    """
    today = date.today()

    # Default expiry weekday: Thursday (3) for NIFTY/BANKNIFTY, Tuesday (1) for FINNIFTY
    target_weekday = 1 if symbol.upper() == "FINNIFTY" else 3

    if preference == "monthly":
        monthly_exp = get_monthly_expiry(symbol, today.year, today.month)
        if today > monthly_exp:
            # Move to next month
            next_m = today.month + 1 if today.month < 12 else 1
            next_y = today.year if today.month < 12 else today.year + 1
            monthly_exp = get_monthly_expiry(symbol, next_y, next_m)
        return monthly_exp

    elif preference == "next_week":
        current_exp = get_next_weekday(today, target_weekday)
        return current_exp + timedelta(days=7)

    else:  # "current_week"
        current_exp = get_next_weekday(today, target_weekday)
        return current_exp


def format_expiry_str_for_symbol(expiry_date: date) -> str:
    """
    Formats date into standard NFO symbol string.
    Example: 2026-08-06 -> "26AUG" or "26806"
    """
    year_str = str(expiry_date.year)[2:]  # "26"
    month_str = expiry_date.strftime("%b").upper()  # "AUG"
    day_str = f"{expiry_date.day:02d}"  # "06"
    return f"{year_str}{month_str}"


def get_time_to_expiry_years(expiry_date: date) -> float:
    """Returns remaining time to expiry in years."""
    today = date.today()
    days_left = (expiry_date - today).days
    if days_left <= 0:
        return 0.5 / 365.0  # Half day for expiry day
    return days_left / 365.0
