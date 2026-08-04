"""
config.py — Central configuration for the Trading Bot.

All sensitive credentials MUST be set via environment variables or a local .env file.
Never hardcode credentials here — this file is committed to version control.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # Loads from .env file if present

# ─────────────────────────────────────────────
# BROKER SELECTION
# ─────────────────────────────────────────────
# "angel"   → Angel One (SmartAPI) — 100% FREE API (Recommended)
# "zerodha" → Zerodha (Kite Connect) — ₹2,000/month
BROKER = os.getenv("BROKER", "angel")

# ─────────────────────────────────────────────
# ANGEL ONE SMARTAPI CREDENTIALS (100% FREE)
# Set these via .env file or Render environment variables — NEVER hardcode here
# ─────────────────────────────────────────────
ANGEL_API_KEY      = os.getenv("ANGEL_API_KEY", "")
ANGEL_CLIENT_CODE  = os.getenv("ANGEL_CLIENT_CODE", "")
ANGEL_PASSWORD     = os.getenv("ANGEL_PASSWORD", "")
ANGEL_TOTP_SECRET  = os.getenv("ANGEL_TOTP_SECRET", "")

# ─────────────────────────────────────────────
# ZERODHA KITE CONNECT CREDENTIALS
# ─────────────────────────────────────────────
KITE_API_KEY    = os.getenv("KITE_API_KEY", "your_api_key_here")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "your_api_secret_here")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# ─────────────────────────────────────────────
# TRADING MODE
# ─────────────────────────────────────────────
# "paper"  → Simulate trades, no real orders
# "live"   → Real orders via Kite Connect
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# ─────────────────────────────────────────────
# WATCHLIST — Stocks to scan and trade
# ─────────────────────────────────────────────
# Use NSE symbols. Exchange prefix handled automatically.
WATCHLIST = [
    # Nifty 50 — Top 25 most liquid large-cap stocks
    "RELIANCE",  "TCS",       "HDFCBANK",  "INFY",      "ICICIBANK",
    "SBIN",      "AXISBANK",  "WIPRO",     "TATAMOTORS","BAJFINANCE",
    "BHARTIARTL","LT",        "ITC",       "KOTAKBANK", "HINDUNILVR",
    "SUNPHARMA", "MARUTI",    "TATASTEEL", "TITAN",     "NTPC",
    "HCLTECH",   "ADANIPORTS","DRREDDY",   "ULTRACEMCO","M&M",
]

# Default exchange for equities
DEFAULT_EXCHANGE = "NSE"

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
CAPITAL = 100_000           # Total capital in INR (update this)
RISK_PER_TRADE_PCT = 1.5    # Max % of capital to risk per trade (1.5%)
MAX_DAILY_LOSS_PCT = 4.0    # Stop bot if daily loss exceeds this %
MAX_OPEN_POSITIONS = 3      # Maximum simultaneous open positions
REWARD_TO_RISK_RATIO = 2.0  # Minimum R:R ratio for trade entry

# Auto square-off time (IST, 24h format)
SQUARE_OFF_HOUR   = 15
SQUARE_OFF_MINUTE = 15

# ─────────────────────────────────────────────
# STRATEGY SETTINGS
# ─────────────────────────────────────────────
# Enable/disable individual strategies
STRATEGIES = {
    "ema_crossover": True,
    "rsi":           True,
    "vwap":          True,
    "supertrend":    True,
    "candlestick":   True,
    "orb":           True,   # Opening Range Breakout
}

# Minimum confidence score to execute a trade (0.0 – 1.0)
MIN_SIGNAL_CONFIDENCE = 0.70

# Volume filter multiplier — signal candle must have volume > N × 20-bar average
VOLUME_FILTER_MULT = 1.5

# ADX period for market regime detection
ADX_PERIOD = 14
ADX_TREND_THRESHOLD   = 25   # ADX > 25 → trending market
ADX_CHOPPY_THRESHOLD  = 15   # ADX < 15 → very choppy, skip trading

# Opening Range Breakout: minutes after 09:15 to define the opening range
ORB_MINUTES = 15  # 09:15 – 09:30 AM defines opening range

# Time-of-day filter: block new entries during midday lull (IST)
NO_TRADE_START_HOUR, NO_TRADE_START_MIN = 11, 30
NO_TRADE_END_HOUR,   NO_TRADE_END_MIN   = 13, 30

# Candle interval for strategy signals
# Options: "minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute"
CANDLE_INTERVAL = "5minute"

# Number of historical candles to fetch for indicator calculation
LOOKBACK_CANDLES = 100

# ─────────────────────────────────────────────
# EMA CROSSOVER SETTINGS
# ─────────────────────────────────────────────
EMA_FAST  = 9
EMA_SLOW  = 21

# ─────────────────────────────────────────────
# RSI SETTINGS
# ─────────────────────────────────────────────
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70

# ─────────────────────────────────────────────
# VWAP SETTINGS
# ─────────────────────────────────────────────
VWAP_DEVIATION_PCT = 0.5   # % away from VWAP to consider for entry

# ─────────────────────────────────────────────
# SUPERTREND SETTINGS
# ─────────────────────────────────────────────
SUPERTREND_ATR_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
DASHBOARD_DEBUG = False

# ─────────────────────────────────────────────
# TELEGRAM NOTIFICATIONS (optional)
# ─────────────────────────────────────────────
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_LEVEL = "INFO"   # DEBUG / INFO / WARNING / ERROR
LOG_FILE  = "logs/trading_bot.log"

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
DATABASE_PATH = "data/trades.db"
