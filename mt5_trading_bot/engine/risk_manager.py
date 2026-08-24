"""
Risk Manager for MT5 Trading Bot
Enforces lot size limits, risk percentage per trade, spread limits, and position limits.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("RiskManager")

class RiskManager:
    def __init__(
        self,
        max_risk_percent: float = 1.0,
        default_lot_size: float = 0.01,
        use_fixed_lot: bool = True,
        max_open_trades_total: int = 3,
        max_open_trades_per_symbol: int = 1,
        max_spread_pips: float = 3.5
    ):
        self.max_risk_percent = max_risk_percent
        self.default_lot_size = default_lot_size
        self.use_fixed_lot = use_fixed_lot
        self.max_open_trades_total = max_open_trades_total
        self.max_open_trades_per_symbol = max_open_trades_per_symbol
        self.max_spread_pips = max_spread_pips

    def check_spread(self, sym_info) -> bool:
        """Returns True if current spread is within acceptable threshold"""
        if sym_info is None:
            return False

        point = sym_info.point
        digits = sym_info.digits
        spread_points = sym_info.spread
        
        # In Forex, 1 pip = 10 points (for 3/5 digit brokers) or 1 point (for 2/4 digit brokers)
        pip_multiplier = 10 if (digits == 3 or digits == 5) else 1
        spread_pips = spread_points / pip_multiplier

        if spread_pips > self.max_spread_pips:
            logger.warning(
                f"[{sym_info.name}] Spread too wide: {spread_pips:.1f} pips (Max allowed: {self.max_spread_pips} pips). Trade skipped."
            )
            return False
        return True

    def calculate_lot_size(
        self,
        account_info: Dict[str, Any],
        sym_info,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculates safe lot size based on balance and SL distance, respecting broker lot step & min lot.
        """
        min_lot = sym_info.volume_min if sym_info else 0.01
        max_lot = sym_info.volume_max if sym_info else 100.0
        step_lot = sym_info.volume_step if sym_info else 0.01

        if self.use_fixed_lot or stop_loss == 0:
            lot = max(min_lot, min(self.default_lot_size, max_lot))
            return round(lot, 2)

        equity = account_info.get("equity", 1000.0)
        risk_amount = equity * (self.max_risk_percent / 100.0)
        sl_distance = abs(entry_price - stop_loss)

        if sl_distance <= 0:
            return min_lot

        tick_size = sym_info.trade_tick_size if sym_info.trade_tick_size > 0 else sym_info.point
        tick_value = sym_info.trade_tick_value if sym_info.trade_tick_value > 0 else 1.0

        risk_per_lot = (sl_distance / tick_size) * tick_value
        if risk_per_lot <= 0:
            return min_lot

        calculated_lot = risk_amount / risk_per_lot
        # Adjust to broker step
        steps = int(calculated_lot / step_lot)
        final_lot = steps * step_lot
        final_lot = max(min_lot, min(final_lot, max_lot))

        return round(final_lot, 2)

    def can_open_trade(
        self,
        symbol: str,
        open_positions: list,
        sym_info,
        account_info: Dict[str, Any]
    ) -> bool:
        """Evaluates whether all risk and capacity criteria are satisfied before entering a trade"""
        # 1. Check spread
        if not self.check_spread(sym_info):
            return False

        # 2. Check total open positions
        if len(open_positions) >= self.max_open_trades_total:
            logger.info(f"Max total open trades ({self.max_open_trades_total}) reached. Skipping.")
            return False

        # 3. Check open positions for this symbol
        symbol_positions = [p for p in open_positions if p.get("symbol") == symbol]
        if len(symbol_positions) >= self.max_open_trades_per_symbol:
            return False

        # 4. Check free margin
        free_margin = account_info.get("margin_free", 0.0)
        if free_margin <= 20.0:
            logger.warning(f"Free margin too low ({free_margin}). Cannot open new position.")
            return False

        return True
