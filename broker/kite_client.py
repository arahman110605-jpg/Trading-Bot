"""
broker/kite_client.py — Zerodha Kite Connect wrapper.

Provides a clean interface for:
  - Fetching historical OHLCV data
  - Live quotes
  - Placing, modifying, cancelling orders
  - Fetching positions and portfolio
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

import config
from utils.logger import get_logger

log = get_logger("KiteClient")

# ── Try importing kiteconnect (not available if API not set up) ──────────────
try:
    from kiteconnect import KiteConnect, KiteTicker
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    log.warning("kiteconnect not installed. Running in paper-only mode.")


class KiteClient:
    """
    Wrapper around Zerodha KiteConnect SDK.
    In paper mode, order calls are simulated.
    In demo mode, market data comes from DemoMarket.
    """

    def __init__(self, kite=None, demo_feed=None):
        self.kite        = kite
        self.demo_feed   = demo_feed          # DemoMarket instance (demo mode)
        self.mode: str   = config.TRADING_MODE
        self._instrument_cache: Dict = {}
        log.info("KiteClient initialised | mode=%s%s", self.mode,
                 " | DEMO FEED ACTIVE" if demo_feed else "")

    # ── Instrument Lookup ────────────────────────────────────────────────────

    def get_instrument_token(self, symbol: str, exchange: str = config.DEFAULT_EXCHANGE) -> Optional[int]:
        """Returns instrument token for a symbol."""
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._instrument_cache:
            return self._instrument_cache[cache_key]

        if not self.kite:
            return None

        try:
            instruments = self.kite.instruments(exchange)
            for inst in instruments:
                if inst["tradingsymbol"] == symbol:
                    self._instrument_cache[cache_key] = inst["instrument_token"]
                    return inst["instrument_token"]
        except Exception as e:
            log.error("Failed to fetch instrument token for %s: %s", symbol, e)
        return None

    # ── Market Data ──────────────────────────────────────────────────────────

    def get_historical_data(
        self,
        symbol: str,
        interval: str = config.CANDLE_INTERVAL,
        days: int = 5,
        exchange: str = config.DEFAULT_EXCHANGE,
    ) -> pd.DataFrame:
        """Fetch OHLCV data. Uses demo feed if available."""
        # ── Demo mode ──
        if self.demo_feed:
            return self.demo_feed.get_historical_data(symbol)

        if not self.kite:
            log.warning("Kite not connected. Returning empty DataFrame.")
            return pd.DataFrame()

        token = self.get_instrument_token(symbol, exchange)
        if not token:
            log.error("Instrument token not found for %s", symbol)
            return pd.DataFrame()

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=days)

        try:
            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=False,
            )
            df = pd.DataFrame(data)
            df.set_index("date", inplace=True)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            log.error("Failed to fetch historical data for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_ltp(self, symbol: str, exchange: str = config.DEFAULT_EXCHANGE) -> Optional[float]:
        """Get Last Traded Price for a symbol."""
        if self.demo_feed:
            return self.demo_feed.get_ltp(symbol)
        if not self.kite:
            return None
        try:
            key = f"{exchange}:{symbol}"
            data = self.kite.ltp([key])
            return data[key]["last_price"]
        except Exception as e:
            log.error("Failed to get LTP for %s: %s", symbol, e)
            return None

    def get_quote(self, symbol: str, exchange: str = config.DEFAULT_EXCHANGE) -> Optional[Dict]:
        """Get full quote for a symbol."""
        if self.demo_feed:
            return self.demo_feed.get_quote(symbol)
        if not self.kite:
            return None
        try:
            key = f"{exchange}:{symbol}"
            return self.kite.quote([key]).get(key)
        except Exception as e:
            log.error("Failed to get quote for %s: %s", symbol, e)
            return None

    # ── Orders ───────────────────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        direction: str,  # "BUY" or "SELL"
        quantity: int,
        exchange: str = config.DEFAULT_EXCHANGE,
        tag: str = "bot",
    ) -> Optional[str]:
        """Place a market order. Returns order_id."""
        log.info(
            "[%s] MARKET ORDER → %s %s x%d on %s",
            self.mode.upper(), direction, symbol, quantity, exchange
        )

        if self.mode == "paper":
            fake_id = f"PAPER_{symbol}_{int(time.time())}"
            log.info("Paper order placed. id=%s", fake_id)
            return fake_id

        if not self.kite:
            log.error("Kite not connected for live order!")
            return None

        try:
            from kiteconnect import KiteConnect as _K
            txn = _K.TRANSACTION_TYPE_BUY if direction == "BUY" else _K.TRANSACTION_TYPE_SELL
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=exchange,
                transaction_type=txn,
                quantity=quantity,
                order_type=_K.ORDER_TYPE_MARKET,
                product=_K.PRODUCT_MIS,   # Intraday
                validity=_K.VALIDITY_DAY,
                tag=tag,
                variety=_K.VARIETY_REGULAR,
            )
            log.info("Live order placed. id=%s", order_id)
            return str(order_id)
        except Exception as e:
            log.error("Order placement failed for %s: %s", symbol, e)
            return None

    def place_sl_order(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        trigger_price: float,
        limit_price: float,
        exchange: str = config.DEFAULT_EXCHANGE,
        tag: str = "sl",
    ) -> Optional[str]:
        """Place a stop-loss order."""
        log.info(
            "[%s] SL ORDER → %s %s x%d trigger=%.2f limit=%.2f",
            self.mode.upper(), direction, symbol, quantity, trigger_price, limit_price
        )

        if self.mode == "paper":
            fake_id = f"SL_{symbol}_{int(time.time())}"
            return fake_id

        if not self.kite:
            return None

        try:
            from kiteconnect import KiteConnect as _K
            txn = _K.TRANSACTION_TYPE_SELL if direction == "BUY" else _K.TRANSACTION_TYPE_BUY
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=exchange,
                transaction_type=txn,
                quantity=quantity,
                order_type=_K.ORDER_TYPE_SL,
                price=limit_price,
                trigger_price=trigger_price,
                product=_K.PRODUCT_MIS,
                validity=_K.VALIDITY_DAY,
                tag=tag,
                variety=_K.VARIETY_REGULAR,
            )
            return str(order_id)
        except Exception as e:
            log.error("SL order failed for %s: %s", symbol, e)
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self.mode == "paper":
            log.info("Paper: cancelled order %s", order_id)
            return True
        if not self.kite:
            return False
        try:
            from kiteconnect import KiteConnect as _K
            self.kite.cancel_order(variety=_K.VARIETY_REGULAR, order_id=order_id)
            return True
        except Exception as e:
            log.error("Cancel order failed: %s", e)
            return False

    def get_positions(self) -> List[Dict]:
        """Fetch current open positions."""
        if self.mode == "paper" or not self.kite:
            return []
        try:
            pos = self.kite.positions()
            return pos.get("day", [])
        except Exception as e:
            log.error("Failed to fetch positions: %s", e)
            return []

    def get_orders(self) -> List[Dict]:
        """Fetch all orders for today."""
        if self.mode == "paper" or not self.kite:
            return []
        try:
            return self.kite.orders() or []
        except Exception as e:
            log.error("Failed to fetch orders: %s", e)
            return []
