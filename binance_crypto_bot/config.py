"""
config.py — Central Configuration for Binance & Delta Exchange Crypto Options Bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# BROKER & MODE SELECTION
# ─────────────────────────────────────────────
# TRADING_MODE: "paper" (Simulated trades) or "live" (Real API execution)
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# BROKER_TYPE: "binance_spot", "binance_futures", "web3_dex", or "delta_options"
BROKER_TYPE = os.getenv("BROKER_TYPE", "delta_options")

# ─────────────────────────────────────────────
# DELTA EXCHANGE CREDENTIALS & ENDPOINTS
# ─────────────────────────────────────────────
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
DELTA_TOTP_SECRET = os.getenv("DELTA_TOTP_SECRET", "")

# Delta Exchange Endpoints (india.delta.exchange or api.delta.exchange)
DELTA_BASE_URL = os.getenv("DELTA_BASE_URL", "https://india.delta.exchange")
DELTA_TESTNET_URL = "https://testnet-api.delta.exchange"

# ─────────────────────────────────────────────
# BINANCE CEX CREDENTIALS
# ─────────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

BINANCE_SPOT_MAINNET_URL = "https://api.binance.com"
BINANCE_SPOT_TESTNET_URL = "https://testnet.binance.vision"
BINANCE_FUTURES_MAINNET_URL = "https://fapi.binance.com"
BINANCE_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"

# ─────────────────────────────────────────────
# WEB3 DEX CREDENTIALS
# ─────────────────────────────────────────────
WEB3_RPC_URL = os.getenv("WEB3_RPC_URL", "https://bsc-dataseed.binance.org/")
WEB3_PRIVATE_KEY = os.getenv("WEB3_PRIVATE_KEY", "")
WEB3_CHAIN_ID = int(os.getenv("WEB3_CHAIN_ID", "56"))

PANCAKESWAP_ROUTER_BSC = "0x10ED433C71B767884555d9C450d748305761380e"
UNISWAP_V2_ROUTER_ETH = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

# ─────────────────────────────────────────────
# CRYPTO WATCHLIST & OPTIONS CONFIG
# ─────────────────────────────────────────────
DEFAULT_SYMBOL = "BTC"
CRYPTO_WATCHLIST = ["BTC", "ETH", "SOL"]

DEFAULT_TIMEFRAME = "5m"

# Option Strike Step Sizes & Expiries
OPTION_STRIKE_STEPS = {
    "BTC": 500,    # $500 strike step for BTC options
    "ETH": 50,     # $50 strike step for ETH options
    "SOL": 5       # $5 strike step for SOL options
}

OPTION_LOT_SIZES = {
    "BTC": 0.001,  # 1 contract = 0.001 BTC
    "ETH": 0.01,   # 1 contract = 0.01 ETH
    "SOL": 0.1     # 1 contract = 0.1 SOL
}

# ─────────────────────────────────────────────
# CAPITAL & RISK MANAGEMENT
# ─────────────────────────────────────────────
CAPITAL = float(os.getenv("CAPITAL", "60.0"))  # Trading capital in USDT ($60 ~ ₹5,000)
POSITION_SIZE_PERCENT = 0.15                  # 15% of total balance per trade
LEVERAGE = int(os.getenv("LEVERAGE", "5"))

# Risk Thresholds
STOP_LOSS_PCT = 0.15      # 15% Stop Loss on option premium
TAKE_PROFIT_PCT = 0.35     # 35% Take Profit on option premium
TRAILING_STOP_PCT = 0.05   # 5% Trailing Stop
MAX_DAILY_LOSS_PCT = 0.05  # 5% Max Daily Loss Guard

MAX_SLIPPAGE_PCT = 0.01
GAS_LIMIT = 250000

# ─────────────────────────────────────────────
# DASHBOARD CONFIGURATION
# ─────────────────────────────────────────────
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5002"))
DASHBOARD_HOST = "0.0.0.0"
