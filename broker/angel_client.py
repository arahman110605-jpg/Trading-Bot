"""
broker/angel_client.py — Angel One SmartAPI Wrapper.

Provides a clean interface for:
  - Angel One SmartAPI Login (TOTP authentication)
  - Historical OHLCV data & Live quotes
  - Placing, modifying, cancelling intraday (MIS) orders
  - Fully compatible with Paper Trading & Live Trading modes
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

import config
from utils.logger import get_logger

log = get_logger("AngelClient")

try:
    try:
        from SmartApi import SmartConnect
    except ImportError:
        from smartapi import SmartConnect
    import pyotp
    ANGEL_AVAILABLE = True
except ImportError as e:
    ANGEL_AVAILABLE = False
    log.warning("smartapi-python or pyotp not installed or import failed: %s", e)


class AngelClient:
    """Wrapper around Angel One SmartAPI SDK."""

    def __init__(self, api_key: str = "", client_code: str = "", password: str = "", totp_secret: str = "", demo_feed=None):
        self.api_key      = api_key or config.ANGEL_API_KEY or os.getenv("ANGEL_API_KEY", "8NVXD5FQ")
        self.client_code  = client_code or config.ANGEL_CLIENT_CODE or os.getenv("ANGEL_CLIENT_CODE", "AABB879420")
        self.password     = password or config.ANGEL_PASSWORD or os.getenv("ANGEL_PASSWORD", "9440")
        self.totp_secret  = totp_secret or config.ANGEL_TOTP_SECRET or os.getenv("ANGEL_TOTP_SECRET", "ZWIRJNNMNNTPDPXYBECPQXWZVE")
        self.demo_feed    = demo_feed
        self.mode: str    = config.TRADING_MODE

        self.smart_api: Optional["SmartConnect"] = None
        self._token_map: Dict[str, str] = {}  # symbol -> token string

        log.info("AngelClient init | ANGEL_AVAILABLE=%s | api_key=%s... | client_code=%s",
                 ANGEL_AVAILABLE, self.api_key[:4] if self.api_key else 'NONE', self.client_code)

        if ANGEL_AVAILABLE and self.api_key and self.client_code:
            self._login()
        else:
            log.warning("AngelClient cannot login | ANGEL_AVAILABLE=%s | api_key=%s | client_code=%s",
                        ANGEL_AVAILABLE, bool(self.api_key), bool(self.client_code))

    def _login(self):
        """Authenticate with Angel One SmartAPI using TOTP."""
        try:
            log.info("Logging into Angel One SmartAPI...")
            self.smart_api = SmartConnect(api_key=self.api_key)

            totp = pyotp.TOTP(self.totp_secret).now() if self.totp_secret else ""
            data = self.smart_api.generateSession(self.client_code, self.password, totp)

            if data.get("status"):
                log.info("✓ Angel One authentication successful!")
                # Extract auth token if needed
                jwt_token = data["data"]["jwtToken"]
                self.smart_api.getProfile(jwt_token)
            else:
                log.error("Angel One login failed: %s", data.get("message"))
        except Exception as e:
            log.error("Angel One login error: %s", e)

    # ── Market Data ──────────────────────────────────────────────────────────

    def get_historical_data(
        self,
        symbol: str,
        interval: str = config.CANDLE_INTERVAL,
        days: int = 5,
        exchange: str = "NSE",
    ) -> pd.DataFrame:
        """Fetch OHLCV data for symbol."""
        if self.demo_feed:
            return self.demo_feed.get_historical_data(symbol)

        if not self.smart_api:
            log.warning("Angel API not connected. Returning empty DataFrame.")
            return pd.DataFrame()

        # Map timeframe interval strings for Angel API
        interval_map = {
            "1minute": "ONE_MINUTE",
            "3minute": "THREE_MINUTE",
            "5minute": "FIVE_MINUTE",
            "15minute": "FIFTEEN_MINUTE",
            "30minute": "THIRTY_MINUTE",
            "60minute": "ONE_HOUR",
        }
        angel_interval = interval_map.get(interval, "FIVE_MINUTE")

        token = self._get_symbol_token(symbol, exchange)
        if not token:
            return pd.DataFrame()

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=days)

        for attempt in range(3):
            try:
                params = {
                    "exchange": exchange,
                    "symboltoken": token,
                    "interval": angel_interval,
                    "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                    "todate": to_date.strftime("%Y-%m-%d %H:%M"),
                }
                res = self.smart_api.getCandleData(params)

                if isinstance(res, dict) and res.get("status") and res.get("data"):
                    cols = ["date", "open", "high", "low", "close", "volume"]
                    df = pd.DataFrame(res["data"], columns=cols)
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    return df

                msg = res.get("message", "") if isinstance(res, dict) else str(res)
                if "Too many requests" in msg or "access rate" in msg or "AB1021" in msg:
                    log.debug("Rate limit hit for %s (attempt %d/3). Pausing 1.2s...", symbol, attempt+1)
                    time.sleep(1.2)
                    continue

                log.error("Angel candle fetch failed for %s: %s", symbol, msg)
                return pd.DataFrame()

            except Exception as e:
                if "access rate" in str(e) or "Too many requests" in str(e):
                    time.sleep(1.2)
                    continue
                log.error("Failed to fetch historical data for %s: %s", symbol, e)
                return pd.DataFrame()

        return pd.DataFrame()

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get Last Traded Price."""
        if self.demo_feed:
            return self.demo_feed.get_ltp(symbol)

        if not self.smart_api:
            return None

        token = self._get_symbol_token(symbol, exchange)
        if not token:
            return None

        try:
            res = self.smart_api.ltpData(exchange, f"{symbol}-EQ", token)
            if res.get("status") and res.get("data"):
                return float(res["data"]["ltp"])
        except Exception as e:
            log.error("Failed to fetch LTP for %s: %s", symbol, e)
        return None

    # ── Orders ───────────────────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        direction: str,  # "BUY" or "SELL"
        quantity: int,
        exchange: str = "NSE",
        tag: str = "bot",
    ) -> Optional[str]:
        """Place an intraday market order."""
        log.info(
            "[%s - ANGEL ONE] MARKET ORDER → %s %s x%d",
            self.mode.upper(), direction, symbol, quantity
        )

        if self.mode == "paper":
            fake_id = f"ANGEL_PAPER_{symbol}_{int(time.time())}"
            return fake_id

        if not self.smart_api:
            log.error("Angel API not connected!")
            return None

        try:
            token = self._get_symbol_token(symbol, exchange)
            params = {
                "variety": "NORMAL",
                "tradingsymbol": f"{symbol}-EQ",
                "symboltoken": token,
                "transactiontype": direction,
                "exchange": exchange,
                "ordertype": "MARKET",
                "producttype": "INTRADAY",  # MIS equivalent in Angel One
                "duration": "DAY",
                "price": "0",
                "quantity": str(quantity),
            }
            res = self.smart_api.placeOrder(params)
            if res.get("status"):
                order_id = str(res["data"]["orderid"])
                log.info("Live Angel One order placed: id=%s", order_id)
                return order_id
            else:
                log.error("Angel order error: %s", res.get("message"))
                return None
        except Exception as e:
            log.error("Order placement exception for %s: %s", symbol, e)
            return None

    def _get_symbol_token(self, symbol: str, exchange: str = "NSE") -> str:
        """Lookup token for symbol."""
        DEFAULT_TOKENS = {
            "RELIANCE":   "2885",
            "TCS":        "11536",
            "HDFCBANK":   "1333",
            "INFY":       "1594",
            "ICICIBANK":  "4963",
            "SBIN":       "3045",
            "AXISBANK":   "5900",
            "WIPRO":      "3787",
            "TATAMOTORS":  "3456",
            "BAJFINANCE":  "317",
            "BHARTIARTL": "10604",
            "LT":         "11483",
            "ITC":        "1660",
            "KOTAKBANK":  "1922",
            "HINDUNILVR": "1394",
            "SUNPHARMA":  "3351",
            "MARUTI":     "10999",
            "TATASTEEL":  "3499",
            "TITAN":      "3506",
            "NTPC":       "11630",
            "HCLTECH":    "7229",
            "ADANIPORTS": "15083",
            "DRREDDY":    "881",
            "ULTRACEMCO": "11532",
            "M&M":        "2031",
        }
        return DEFAULT_TOKENS.get(symbol, "")
