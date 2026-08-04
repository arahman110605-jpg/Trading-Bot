"""
config.py — Central Configuration for Binance Crypto & Web3 Trading Bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# BROKER & MODE SELECTION
# ─────────────────────────────────────────────
# TRADING_MODE: "paper" (Simulated trades) or "live" (Real Binance API / Web3 DEX execution)
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# BROKER_TYPE: "binance_spot", "binance_futures", or "web3_dex"
BROKER_TYPE = os.getenv("BROKER_TYPE", "binance_spot")

# ─────────────────────────────────────────────
# BINANCE CEX CREDENTIALS
# ─────────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

# Binance REST Endpoints
BINANCE_SPOT_MAINNET_URL = "https://api.binance.com"
BINANCE_SPOT_TESTNET_URL = "https://testnet.binance.vision"
BINANCE_FUTURES_MAINNET_URL = "https://fapi.binance.com"
BINANCE_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"

# Binance WebSocket Endpoints
BINANCE_SPOT_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_SPOT_TESTNET_WS_URL = "wss://testnet.binance.vision/ws"
BINANCE_FUTURES_WS_URL = "wss://fstream.binance.com/ws"
BINANCE_FUTURES_TESTNET_WS_URL = "wss://stream.binancefuture.com/ws"

# ─────────────────────────────────────────────
# WEB3 DEX CREDENTIALS & NETWORKS
# ─────────────────────────────────────────────
WEB3_RPC_URL = os.getenv("WEB3_RPC_URL", "https://bsc-dataseed.binance.org/")
WEB3_PRIVATE_KEY = os.getenv("WEB3_PRIVATE_KEY", "")
WEB3_CHAIN_ID = int(os.getenv("WEB3_CHAIN_ID", "56"))

# Known DEX Router Addresses (PancakeSwap V2 on BSC by default)
PANCAKESWAP_ROUTER_BSC = "0x10ED433C71B767884555d9C450d748305761380e"
UNISWAP_V2_ROUTER_ETH = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

# ─────────────────────────────────────────────
# CRYPTO WATCHLIST & PAIRS
# ─────────────────────────────────────────────
DEFAULT_SYMBOL = "BTCUSDT"
CRYPTO_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]

# Default timeframe: '1m', '5m', '15m', '1h', '4h', '1d'
DEFAULT_TIMEFRAME = "5m"

# ─────────────────────────────────────────────
# CAPITAL & RISK MANAGEMENT
# ─────────────────────────────────────────────
CAPITAL = float(os.getenv("CAPITAL", "1000.0"))  # Trading capital in USDT
POSITION_SIZE_PERCENT = 0.10  # 10% of total balance per trade
LEVERAGE = int(os.getenv("LEVERAGE", "5"))     # Default leverage for Futures (1x to 20x)

# Risk Thresholds
STOP_LOSS_PCT = 0.02      # 2% Stop Loss
TAKE_PROFIT_PCT = 0.04     # 4% Take Profit
TRAILING_STOP_PCT = 0.01   # 1% Trailing Stop
MAX_DAILY_LOSS_PCT = 0.05  # 5% Max Daily Loss Guard

# Web3 DEX Specific Settings
MAX_SLIPPAGE_PCT = 0.01    # 1% max slippage for swaps
GAS_LIMIT = 250000         # Default gas limit for Web3 transactions

# ─────────────────────────────────────────────
# DASHBOARD CONFIGURATION
# ─────────────────────────────────────────────
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5002"))
DASHBOARD_HOST = "0.0.0.0"
