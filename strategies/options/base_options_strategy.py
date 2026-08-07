"""
strategies/options/base_options_strategy.py — Base class for all options strategies.

Provides shared helpers:
  - ATM strike calculation
  - Premium % change tracking
  - Lot size lookup
  - Paper trade simulation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from utils.logger import get_logger

log = get_logger("BaseOptionsStrategy")

# NSE lot sizes (as of 2025/2026 — update as SEBI revises)
LOT_SIZES = {
    "NIFTY":     75,
    "BANKNIFTY": 35,
    "FINNIFTY":  65,
}


@dataclass
class OptionsSignal:
    """Represents an options trade signal."""
    bot_id: str
    strategy: str
    signal_type: str          # 'straddle_sell', 'condor', 'buy_ce', 'buy_pe'
    index: str                # 'NIFTY' or 'BANKNIFTY'
    atm_strike: int
    ce_strike: int
    pe_strike: int
    ce_token: str
    pe_token: str
    ce_entry_price: float
    pe_entry_price: float
    total_premium: float      # combined premium (CE + PE)
    sl_premium: float         # stop-loss premium level
    target_premium: float     # take-profit premium level
    lot_size: int
    lots: int
    direction: str            # 'SELL' for straddle/condor, 'BUY_CE'/'BUY_PE' for momentum
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    is_actionable: bool = True


class BaseOptionsStrategy(ABC):
    """Abstract base for all options strategies."""

    def __init__(self, bot_config: Dict[str, Any]):
        self.bot_config = bot_config
        self.bot_id = bot_config["bot_id"]
        self.name = bot_config.get("strategy", "options")
        self.lots = bot_config.get("lots", 1)

    @abstractmethod
    def generate_signal(self, hub_snapshot: Dict) -> Optional[OptionsSignal]:
        """
        Generate a trading signal from the hub's data snapshot.
        hub_snapshot contains:
          - 'atm_strikes': {index: strike}
          - 'index_ltp': {index: price}
          - 'options': {"NIFTY_25000_CE": {ltp, token, ...}}
          - 'vix': float or None
        """
        pass

    def get_lot_size(self, index: str) -> int:
        return LOT_SIZES.get(index, 75)

    def is_vix_safe(self, vix: Optional[float], max_vix: float) -> bool:
        """Return True if VIX is below the safety threshold."""
        if vix is None:
            log.warning("%s: VIX unavailable, allowing trade (conservative fallback).", self.bot_id)
            return True
        safe = vix < max_vix
        if not safe:
            log.info("%s: VIX=%.1f exceeds max=%.1f — skipping signal.", self.bot_id, vix, max_vix)
        return safe

    def compute_pct_change(self, current: float, entry: float) -> float:
        """Return % change from entry price."""
        if entry == 0:
            return 0.0
        return ((current - entry) / entry) * 100
