"""
risk_manager.py — Crypto Risk Management Engine (Position Sizing, Leverage, Liquidation & Daily Loss Guard).
"""

from typing import Dict, Any, Tuple
from binance_crypto_bot.config import POSITION_SIZE_PERCENT, LEVERAGE, MAX_DAILY_LOSS_PCT
from binance_crypto_bot.utils.logger import logger

class CryptoRiskManager:
    def __init__(self, max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT, position_size_pct: float = POSITION_SIZE_PERCENT, leverage: int = LEVERAGE):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.position_size_pct = position_size_pct
        self.leverage = leverage
        self.starting_equity = 0.0
        self.trading_allowed = True

    def set_starting_equity(self, equity: float):
        self.starting_equity = equity

    def is_daily_loss_exceeded(self, current_equity: float) -> Tuple[bool, float]:
        """Check if daily loss exceeds risk limit."""
        if self.starting_equity <= 0:
            return False, 0.0

        drawdown = (self.starting_equity - current_equity) / self.starting_equity
        if drawdown >= self.max_daily_loss_pct:
            self.trading_allowed = False
            logger.critical(f"DAILY LOSS GUARD TRIGGERED! Drawdown: {drawdown*100:.2f}% >= Limit: {self.max_daily_loss_pct*100:.2f}%")
            return True, drawdown
        return False, drawdown

    def calculate_position_size(self, current_price: float, available_balance: float) -> float:
        """Calculate position size quantity based on available capital and leverage."""
        if current_price <= 0 or available_balance <= 0:
            return 0.0

        trade_value = available_balance * self.position_size_pct * self.leverage
        quantity = trade_value / current_price
        return round(quantity, 4)

    def validate_signal(self, signal: Dict[str, Any], current_equity: float) -> bool:
        """Validate if a trade signal satisfies risk parameters."""
        if not self.trading_allowed:
            logger.warning("Signal rejected: Daily Loss limit reached.")
            return False

        exceeded, drawdown = self.is_daily_loss_exceeded(current_equity)
        if exceeded:
            return False

        action = signal.get("action", "HOLD")
        if action not in ["BUY", "SELL"]:
            return False

        return True
