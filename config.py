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
    # Liquid High-Beta Stocks for optimal Intraday Risk-Reward
    "ETERNAL", "SUZLON", "TATASTEEL", "ADANIENT", "TMPV",
    "SBIN", "ICICIBANK", "RELIANCE", "BHEL", "IRFC",
    "HDFCBANK", "INFY", "ITC", "WIPRO", "AXISBANK"
]

# Default exchange for equities
DEFAULT_EXCHANGE = "NSE"

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
CAPITAL = 100_000           # Total capital in INR (update this)
RISK_PER_TRADE_PCT = 1.5    # Max % of capital to risk per trade (1.5%)
MAX_DAILY_LOSS_PCT = 2.0    # Stop bot if daily loss exceeds this %
MAX_OPEN_POSITIONS = 3      # Maximum simultaneous open positions
MAX_TRADES_PER_DAY = 5      # Maximum total executed trades per day to prevent overtrading
REWARD_TO_RISK_RATIO = 1.5  # Minimum R:R ratio for trade entry

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
ADX_TREND_THRESHOLD   = 15   # ADX > 15 → trending market
ADX_CHOPPY_THRESHOLD  = 12   # ADX < 12 → very choppy, skip trading

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
RSI_OVERSOLD   = 35
RSI_OVERBOUGHT = 65

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

# ─────────────────────────────────────────────
# MULTI-BOT ARCHITECTURE
# ─────────────────────────────────────────────
# Enable multi-bot mode (8 bots, shared Market Data Hub)
MULTI_BOT_MODE = os.getenv("MULTI_BOT_MODE", "true").lower() == "true"

# Unique ID for this bot instance (set via env var when running multiple bots)
BOT_ID = os.getenv("BOT_ID", "default")

# ─────────────────────────────────────────────
# CONSENSUS ENGINE SETTINGS
# ─────────────────────────────────────────────
# Minimum number of independent strategies that must agree for a trade entry
CONSENSUS_MIN_SIGNALS = 2

# Minimum confidence score for any individual signal
CONSENSUS_CONFIDENCE = 0.70

# High-confidence override: a single signal above this threshold can trade alone
CONSENSUS_HIGH_CONF = 0.85

# ─────────────────────────────────────────────
# OPTIONS TRADING SETTINGS
# ─────────────────────────────────────────────
# Options enabled by default in multi-bot mode
OPTIONS_TRADING_ENABLED = os.getenv("OPTIONS_TRADING_ENABLED", "true").lower() == "true"

# India VIX maximum for options selling strategies (Straddle, Iron Condor)
# High VIX = dangerous to sell options (unlimited risk amplified)
OPTIONS_VIX_MAX_SELL   = 18.0   # Block straddle/condor selling above this VIX
OPTIONS_VIX_MAX_BUY    = 25.0   # Block options buying above this VIX (too expensive)

# NIFTY/BANKNIFTY strike intervals for ATM calculation
NIFTY_STRIKE_INTERVAL     = 50    # NIFTY options are in ₹50 strike intervals
BANKNIFTY_STRIKE_INTERVAL = 100   # BANKNIFTY options are in ₹100 intervals

# NSE lot sizes (update when SEBI revises)
NIFTY_LOT_SIZE     = 75
BANKNIFTY_LOT_SIZE = 35

# Theta Straddle (Bot 06) parameters
STRADDLE_ENTRY_TIME       = "09:20"  # Enter at 9:20 AM sharp
STRADDLE_EXIT_TIME        = "15:00"  # Force-exit by 3:00 PM
STRADDLE_SL_PCT           = 40       # Exit if combined premium rises 40% (stop-loss)
STRADDLE_TARGET_PCT       = 50       # Exit if combined premium falls 50% (take-profit)

# Iron Condor (Bot 07) parameters
CONDOR_SPREAD_WIDTH       = 100      # ₹100 spread width (OTM distance for NIFTY)
CONDOR_ENTRY_DAYS         = ["Monday", "Tuesday"]   # Enter early in the week
CONDOR_TARGET_PCT         = 50       # Take profit at 50% of max premium collected
CONDOR_VIX_MAX            = 15.0     # Tighter VIX limit for condor (needs low vol)

# Options Momentum (Bot 08) parameters
OPTIONS_MOMENTUM_SL_PCT   = 30       # Stop-loss: exit if premium drops 30%
OPTIONS_MOMENTUM_TP_PCT   = 100      # Target: exit if premium doubles (+100%)
OPTIONS_MOMENTUM_WINDOW   = "13:30"  # No new buys after 1:30 PM (time decay risk)
