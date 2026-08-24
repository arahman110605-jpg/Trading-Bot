"""
MT5 Trading Bot - Configuration Settings
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MetaTrader 5 Connection Settings (Optional if MT5 is already running locally)
MT5_ACCOUNT = os.getenv("MT5_ACCOUNT", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "")

# Symbols to trade across the diversified portfolio
SYMBOLS = [
    "EURUSD",   # Euro / Dollar (Open and active)
    "GBPUSD",   # Pound / Dollar (Open and active)
    "USDJPY",   # Dollar / Yen (Open and active)
    "BTC"       # Bitcoin CFD
]

# Timeframe for strategy execution
# "M15" provides ~35 to 50 high-quality trades per month across the portfolio
TIMEFRAME = "M15"

# Strategy Parameters (EMA Pullback & Momentum + MACD + RSI + ATR)
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
RSI_PERIOD = 14
RSI_BUY_MIN = 40.0
RSI_BUY_MAX = 70.0
RSI_SELL_MIN = 30.0
RSI_SELL_MAX = 60.0
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.0   # Stop loss = 1.0 * ATR
ATR_TP_MULTIPLIER = 2.5   # Take profit = 2.5 * ATR (1:2.5 Risk:Reward)

# Trailing Stop & Risk
ENABLE_TRAILING_STOP = True
TRAILING_TRIGGER_ATR = 1.0   # Move SL to breakeven after +1.0 * ATR profit
TRAILING_STEP_ATR = 0.5      # Trail SL every 0.5 * ATR

# Risk Management
MAGIC_NUMBER = 888001
MAX_RISK_PER_TRADE_PERCENT = 1.0  # Risk 1.0% of account equity per trade
DEFAULT_LOT_SIZE = 0.01          # 0.01 Micro lot (for ₹10,000 / $120 balance)
USE_FIXED_LOT = True             # True = use 0.01 fixed lot
MAX_OPEN_TRADES_TOTAL = 3        # Maximum simultaneous open positions across all pairs
MAX_OPEN_TRADES_PER_SYMBOL = 1   # Maximum 1 position per symbol at a time
MAX_ALLOWED_SPREAD_PIPS = 3.5    # Filter out trades if spread is too high (in pips)

# Loop & Execution Interval (seconds)
SLEEP_INTERVAL_SECONDS = 15
