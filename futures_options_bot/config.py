"""
config.py — Central Configuration for Futures & Options (F&O) Trading Bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# BROKER SELECTION
# ─────────────────────────────────────────────
# "angel"   → Angel One (SmartAPI) — 100% FREE API (Recommended)
# "zerodha" → Zerodha (Kite Connect) — ₹2,000/month
BROKER = os.getenv("BROKER", "angel")

# ─────────────────────────────────────────────
# BROKER CREDENTIALS
# ─────────────────────────────────────────────
# Angel One
ANGEL_API_KEY      = os.getenv("ANGEL_API_KEY", "your_angel_api_key_here")
ANGEL_CLIENT_CODE  = os.getenv("ANGEL_CLIENT_CODE", "your_angel_client_code_here")
ANGEL_PASSWORD     = os.getenv("ANGEL_PASSWORD", "your_angel_password_here")
ANGEL_TOTP_SECRET  = os.getenv("ANGEL_TOTP_SECRET", "your_angel_totp_secret_here")

# Zerodha
KITE_API_KEY       = os.getenv("KITE_API_KEY", "your_api_key_here")
KITE_API_SECRET    = os.getenv("KITE_API_SECRET", "your_api_secret_here")
KITE_ACCESS_TOKEN  = os.getenv("KITE_ACCESS_TOKEN", "")

# ─────────────────────────────────────────────
# TRADING MODE
# ─────────────────────────────────────────────
# "paper" → Simulates trades & option prices without real order placement
# "live"  → Real order placement in NFO exchange
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# ─────────────────────────────────────────────
# F&O INSTRUMENTS & WATCHLIST
# ─────────────────────────────────────────────
# Underlyings to scan and trade (Indices and Stock F&O)
INDEX_WATCHLIST = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
STOCK_WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN"]

# Default underlying symbol
DEFAULT_UNDERLYING = "NIFTY"

# Exchange prefix for F&O segment in Indian market
DEFAULT_EXCHANGE = "NFO"  # NSE Futures & Options segment

# ─────────────────────────────────────────────
# F&O INSTRUMENT DETAILS (LOT SIZES & STEP SIZES)
# ─────────────────────────────────────────────
LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "RELIANCE": 250,
    "TCS": 175,
    "HDFCBANK": 550,
    "INFY": 400,
    "ICICIBANK": 700,
    "SBIN": 750,
}

STRIKE_STEP_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "MIDCPNIFTY": 25,
    "RELIANCE": 20,
    "TCS": 20,
    "HDFCBANK": 25,
    "INFY": 20,
    "ICICIBANK": 10,
    "SBIN": 10,
}

# Expiry selection: "current_week", "next_week", "monthly"
EXPIRY_PREFERENCE = "current_week"

# Strike selection offset relative to ATM:
#  0  = ATM (At The Money)
#  1  = ITM1 (Calls: ATM - 1 step, Puts: ATM + 1 step)
# -1  = OTM1 (Calls: ATM + 1 step, Puts: ATM - 1 step)
STRIKE_SELECTION_OFFSET = 0  # Default: ATM

# ─────────────────────────────────────────────
# RISK MANAGEMENT & POSITION SIZING
# ─────────────────────────────────────────────
CAPITAL = 200_000             # Total trading capital in INR
RISK_PER_TRADE_PCT = 2.0      # Max % of capital to risk per trade (2%)
MAX_DAILY_LOSS_PCT = 5.0      # Stop bot if daily loss exceeds this % (5%)
MAX_LOTS_PER_TRADE = 4        # Maximum number of lots per order
MAX_OPEN_POSITIONS = 3        # Maximum simultaneous open positions

# Default Stop-Loss & Target percentages on Option Premium / Futures Price
OPTION_SL_PCT = 15.0          # Stop loss at 15% of option premium
OPTION_TARGET_PCT = 30.0      # Target at 30% of option premium (1:2 R:R)
TRAILING_SL_ENABLED = True    # Enable trailing SL once 50% target is reached

FUTURES_SL_PCT = 0.5          # Stop loss on Futures price (%)
FUTURES_TARGET_PCT = 1.0      # Target on Futures price (%)

# Auto Square-Off time for intraday F&O (IST, 24h format)
SQUARE_OFF_HOUR   = 15
SQUARE_OFF_MINUTE = 15

# ─────────────────────────────────────────────
# STRATEGIES ENABLER
# ─────────────────────────────────────────────
STRATEGIES = {
    "option_buying":   True,  # Momentum Call/Put Buying
    "short_straddle":  True,  # Delta neutral theta decay straddle/strangle
    "credit_spreads":  True,  # Bull Call / Bear Put / Iron Condor Spreads
    "futures_trend":   True,  # Futures Long/Short trend following
}

CANDLE_INTERVAL = "5minute"  # Options candle timeframe
LOOKBACK_CANDLES = 100

# Risk-free interest rate for Black-Scholes greeks (7%)
RISK_FREE_RATE = 0.07

# Dashboard Server Settings
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5001
