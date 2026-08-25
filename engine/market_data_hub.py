"""
engine/market_data_hub.py — Shared Market Data Hub for Multi-Bot Architecture.

A single AngelClient login fetches ALL market data (equity OHLCV + options chain)
and caches it in a thread-safe dict. All 8 bots read from this cache instead of
making their own API calls — preventing Angel One rate limit errors.

Refresh cycle: Every CANDLE_INTERVAL seconds (same as strategy runner).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Any

import pandas as pd

import config
from broker.angel_client import AngelClient
from utils.logger import get_logger

log = get_logger("MarketDataHub")


class MarketDataHub:
    """
    Singleton-style shared data hub.
    Owns the ONE AngelClient connection and broadcasts data to all bot threads.
    """

    INDEX_STRIKE_INTERVALS = {
        "NIFTY":     50,
        "BANKNIFTY": 100,
    }

    def __init__(self):
        log.info("MarketDataHub: Initialising shared Angel One connection...")
        self._client = AngelClient()                # ONE login for all bots
        self._equity_cache: Dict[str, pd.DataFrame] = {}
        self._options_cache: Dict[str, Dict[str, Any]] = {}
        self._atm_strikes: Dict[str, int] = {}
        self._index_ltp: Dict[str, float] = {}
        self._ltp_cache: Dict[str, float] = {}
        self._vix: Optional[float] = None
        self._consensus_direction: Optional[str] = None
        self._consensus_symbol: Optional[str] = None
        self._lock = threading.RLock()
        self._last_equity_refresh: Optional[datetime] = None
        self._last_options_refresh: Optional[datetime] = None
        self._running = False
        log.info("MarketDataHub: Initialised. Ready to serve dual engines (Intraday + F&O).")

    # ── Consensus Signal API ───────────────────────────────────────────────

    def set_consensus_signal(self, direction: str, symbol: str):
        with self._lock:
            self._consensus_direction = direction
            self._consensus_symbol = symbol

    def get_consensus_signal(self):
        with self._lock:
            return self._consensus_direction, self._consensus_symbol

    # ── Public read API ───────────────────────────────────────────────────────

    def get_ltp(self, symbol: str) -> Optional[float]:
        """Return latest live LTP for symbol (cached or freshly polled)."""
        with self._lock:
            cached = self._ltp_cache.get(symbol)
        if cached:
            return cached
        try:
            ltp = self._client.get_ltp(symbol)
            if ltp:
                with self._lock:
                    self._ltp_cache[symbol] = ltp
                return ltp
        except Exception:
            pass
        return None

    def get_equity(self, symbol: str) -> pd.DataFrame:
        """Return cached OHLCV DataFrame for an equity symbol. Thread-safe."""
        with self._lock:
            return self._equity_cache.get(symbol, pd.DataFrame())

    def get_all_equity(self) -> Dict[str, pd.DataFrame]:
        """Return full equity cache snapshot."""
        with self._lock:
            return dict(self._equity_cache)

    def get_option_ltp(self, index: str, strike: int, opt_type: str) -> Optional[float]:
        """Return cached LTP for an option contract."""
        with self._lock:
            return self._options_cache.get(f"{index}_{strike}_{opt_type}", {}).get("ltp")

    def get_option_entry(self, index: str, strike: int, opt_type: str) -> Dict:
        """Return full cached option entry (ltp, token, etc)."""
        with self._lock:
            return dict(self._options_cache.get(f"{index}_{strike}_{opt_type}", {}))

    def get_atm_strike(self, index: str) -> Optional[int]:
        with self._lock:
            return self._atm_strikes.get(index)

    def get_index_ltp(self, index: str) -> Optional[float]:
        with self._lock:
            return self._index_ltp.get(index)

    def get_vix(self) -> Optional[float]:
        with self._lock:
            return self._vix

    def get_options_snapshot(self) -> Dict[str, Dict]:
        with self._lock:
            return dict(self._options_cache)

    def get_market_trend(self) -> str:
        """
        Determine broader market regime across watchlist breadth (% above 20 EMA).
        Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
        """
        with self._lock:
            bullish_count = 0
            bearish_count = 0
            for df in self._equity_cache.values():
                if df is not None and len(df) >= 20:
                    ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
                    close = df["close"].iloc[-1]
                    if close > ema20:
                        bullish_count += 1
                    else:
                        bearish_count += 1
            total = bullish_count + bearish_count
            if total >= 5:
                ratio = bullish_count / total
                if ratio >= 0.60:
                    return "BULLISH"
                elif ratio <= 0.40:
                    return "BEARISH"
            return "NEUTRAL"

    def last_refresh_time(self) -> Optional[datetime]:
        """Return timestamp of the last equity data refresh."""
        with self._lock:
            return self._last_equity_refresh

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def refresh_equity(self):
        """Fetch fresh OHLCV for all watchlist symbols."""
        log.info("MarketDataHub: Refreshing equity data (%d symbols)...", len(config.WATCHLIST))
        updated = 0
        for symbol in config.WATCHLIST:
            try:
                df = self._client.get_historical_data(
                    symbol,
                    interval=config.CANDLE_INTERVAL,
                    days=max(2, config.LOOKBACK_CANDLES // 75 + 1),
                )
                if df is not None and not df.empty:
                    with self._lock:
                        self._equity_cache[symbol] = df
                    updated += 1
                time.sleep(0.35)
            except Exception as e:
                log.error("MarketDataHub: Equity fetch failed for %s: %s", symbol, e)

        with self._lock:
            self._last_equity_refresh = datetime.now()
        log.info("MarketDataHub: Equity refreshed (%d/%d OK).", updated, len(config.WATCHLIST))

    def refresh_options(self):
        """Fetch index spot prices, compute ATM, cache option LTPs."""
        log.info("MarketDataHub: Refreshing options chain...")

        for index, interval in self.INDEX_STRIKE_INTERVALS.items():
            try:
                spot = self._client.get_ltp(index)
                if not spot:
                    log.warning("MarketDataHub: Could not fetch spot for %s", index)
                    continue

                atm = int(round(spot / interval) * interval)
                with self._lock:
                    self._index_ltp[index] = spot
                    self._atm_strikes[index] = atm

                log.debug("%s spot=%.1f ATM=%d", index, spot, atm)

                # Fetch CE and PE for ATM-4 to ATM+4 strikes (covers Iron Condor wings +/-200)
                for offset in range(-4, 5):
                    strike = atm + (offset * interval)
                    for opt_type in ("CE", "PE"):
                        try:
                            token = self._resolve_option_token(index, strike, opt_type)
                            if not token:
                                continue
                            ltp = self._client.get_ltp_by_token(token)
                            if ltp is not None:
                                key = f"{index}_{strike}_{opt_type}"
                                with self._lock:
                                    self._options_cache[key] = {
                                        "ltp": ltp,
                                        "strike": strike,
                                        "type": opt_type,
                                        "index": index,
                                        "token": token,
                                        "timestamp": datetime.now().isoformat(),
                                    }
                            time.sleep(0.35)
                        except Exception as oe:
                            log.debug("Option LTP fail %s %d %s: %s", index, strike, opt_type, oe)

            except Exception as e:
                log.error("MarketDataHub: Options refresh failed for %s: %s", index, e)

        # India VIX
        try:
            vix = self._client.get_ltp("INDIA VIX")
            if vix:
                with self._lock:
                    self._vix = vix
        except Exception:
            pass

        with self._lock:
            self._last_options_refresh = datetime.now()
        log.info("MarketDataHub: Options refreshed. ATM=%s VIX=%s", self._atm_strikes, self._vix)

    def _resolve_option_token(self, index: str, strike: int, opt_type: str) -> Optional[str]:
        """Resolve Angel One token for an option contract from the token map."""
        try:
            token_map = getattr(self._client, "_token_map", {})
            today = date.today()
            # Find current or next Thursday (weekly expiry)
            days_ahead = (3 - today.weekday()) % 7
            expiry = today + timedelta(days=days_ahead)

            month_short = expiry.strftime("%b").upper()
            year_short  = expiry.strftime("%y")

            candidates = [
                f"{index}{year_short}{month_short}{strike}{opt_type}",
                f"{index}{year_short}{expiry.month:02d}{expiry.day:02d}{strike}{opt_type}",
                f"{index}{year_short}{month_short}{int(strike)}{opt_type}",
            ]
            for sym in candidates:
                if sym in token_map:
                    return token_map[sym]
            return None
        except Exception:
            return None

    # ── Background loop ───────────────────────────────────────────────────────

    def start_refresh_loop(self, equity_interval_sec: int = 300):
        """Start background thread that refreshes data every cycle."""
        self._running = True

        def _loop():
            log.info("MarketDataHub: Refresh loop started (interval=%ds).", equity_interval_sec)
            self.refresh_equity()
            self.refresh_options()
            while self._running:
                time.sleep(equity_interval_sec)
                if not self._running:
                    break
                try:
                    self.refresh_equity()
                    self.refresh_options()
                except Exception as e:
                    log.error("MarketDataHub: Refresh loop error: %s", e)
                    time.sleep(30)

        def _fast_ltp_loop():
            log.info("MarketDataHub: Fast live LTP ticker thread started (3s cycle).")
            while self._running:
                try:
                    # Update live LTP for watchlist & active symbols
                    for sym in config.WATCHLIST:
                        if not self._running:
                            break
                        ltp = self._client.get_ltp(sym)
                        if ltp:
                            with self._lock:
                                self._ltp_cache[sym] = ltp
                        time.sleep(0.3)
                except Exception as e:
                    log.debug("Fast LTP ticker error: %s", e)
                time.sleep(3)

        t = threading.Thread(target=_loop, name="MarketDataHub-Refresh", daemon=True)
        t.start()
        
        t_fast = threading.Thread(target=_fast_ltp_loop, name="MarketDataHub-FastLTP", daemon=True)
        t_fast.start()
        return t

    def stop(self):
        self._running = False

    def wait_for_initial_data(self, timeout_sec: int = 180) -> bool:
        """Block until first equity refresh completes."""
        start = time.time()
        while time.time() - start < timeout_sec:
            with self._lock:
                if self._last_equity_refresh is not None:
                    log.info("MarketDataHub: Initial data ready (%.1fs)", time.time() - start)
                    return True
            time.sleep(1)
        log.error("MarketDataHub: Timed out waiting for initial data!")
        return False
