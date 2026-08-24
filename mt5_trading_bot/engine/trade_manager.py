"""
Trade Manager for MT5 Bot
Manages open positions, handles dynamic ATR Trailing Stops and Breakeven adjustments.
"""
import logging
from typing import Dict, Any, List
try:
    from broker.mt5_client import MT5Client
except ImportError:
    from ..broker.mt5_client import MT5Client

logger = logging.getLogger("TradeManager")

class TradeManager:
    def __init__(
        self,
        client: MT5Client,
        enable_trailing_stop: bool = True,
        trailing_trigger_atr: float = 1.0,
        trailing_step_atr: float = 0.5
    ):
        self.client = client
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_trigger_atr = trailing_trigger_atr
        self.trailing_step_atr = trailing_step_atr

    def update_trailing_stops(self, open_positions: List[Dict[str, Any]], current_atrs: Dict[str, float]):
        """
        Iterates over open positions and updates Stop Loss dynamically to lock in profit.
        """
        if not self.enable_trailing_stop:
            return

        for pos in open_positions:
            ticket = pos.get("ticket")
            symbol = pos.get("symbol")
            pos_type = pos.get("type")  # 0 = Buy, 1 = Sell
            open_price = pos.get("price_open")
            current_price = pos.get("price_current")
            current_sl = pos.get("sl", 0.0)
            current_tp = pos.get("tp", 0.0)

            atr = current_atrs.get(symbol, 0.0)
            if atr <= 0:
                continue

            trigger_dist = atr * self.trailing_trigger_atr
            step_dist = atr * self.trailing_step_atr

            # For BUY positions
            if pos_type == 0:  # POSITION_TYPE_BUY
                profit_dist = current_price - open_price
                if profit_dist >= trigger_dist:
                    # Target new SL
                    new_sl = current_price - step_dist
                    # Only move SL up, never down, and must be better than entry or current SL
                    if new_sl > current_sl and (new_sl > open_price or current_sl < open_price):
                        logger.info(f"Trailing SL for BUY {symbol} #{ticket}: Moving SL from {current_sl} -> {new_sl:.5f}")
                        self.client.modify_position_sl_tp(ticket, symbol, new_sl, current_tp)

            # For SELL positions
            elif pos_type == 1:  # POSITION_TYPE_SELL
                profit_dist = open_price - current_price
                if profit_dist >= trigger_dist:
                    # Target new SL
                    new_sl = current_price + step_dist
                    # Only move SL down, never up
                    if (current_sl == 0 or new_sl < current_sl) and (new_sl < open_price or current_sl > open_price):
                        logger.info(f"Trailing SL for SELL {symbol} #{ticket}: Moving SL from {current_sl} -> {new_sl:.5f}")
                        self.client.modify_position_sl_tp(ticket, symbol, new_sl, current_tp)
