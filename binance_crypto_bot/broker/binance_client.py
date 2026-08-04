"""
binance_client.py — Binance CEX REST & WebSocket API wrapper for Spot & USD-M Futures.
"""

import hmac
import hashlib
import time
import requests
import pandas as pd
from typing import Dict, Any, Optional, List
from binance_crypto_bot.config import (
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
    BINANCE_SPOT_MAINNET_URL, BINANCE_SPOT_TESTNET_URL,
    BINANCE_FUTURES_MAINNET_URL, BINANCE_FUTURES_TESTNET_URL
)
from binance_crypto_bot.utils.logger import logger

class BinanceClient:
    def __init__(self, is_futures: bool = False, testnet: bool = BINANCE_TESTNET):
        self.is_futures = is_futures
        self.testnet = testnet
        self.api_key = BINANCE_API_KEY
        self.api_secret = BINANCE_API_SECRET
        
        if is_futures:
            self.base_url = BINANCE_FUTURES_TESTNET_URL if testnet else BINANCE_FUTURES_MAINNET_URL
        else:
            self.base_url = BINANCE_SPOT_TESTNET_URL if testnet else BINANCE_SPOT_MAINNET_URL
            
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        })

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for authenticated endpoints."""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict[str, Any] = None, signed: bool = False) -> Dict[str, Any]:
        """Make HTTP request to Binance REST API."""
        if params is None:
            params = {}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)

        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                resp = self.session.get(url, params=params, timeout=10)
            elif method.upper() == 'POST':
                resp = self.session.post(url, data=params, timeout=10)
            elif method.upper() == 'DELETE':
                resp = self.session.delete(url, data=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Binance API Request Error ({endpoint}): {e}")
            return {"error": str(e)}

    def ping(self) -> bool:
        """Test API connectivity."""
        endpoint = "/fapi/v1/ping" if self.is_futures else "/api/v3/ping"
        res = self._request("GET", endpoint)
        return "error" not in res

    def get_ticker_price(self, symbol: str) -> float:
        """Get latest ticker price for a symbol."""
        endpoint = "/fapi/v1/ticker/price" if self.is_futures else "/api/v3/ticker/price"
        res = self._request("GET", endpoint, {"symbol": symbol.upper()})
        if "price" in res:
            return float(res["price"])
        return 0.0

    def get_klines(self, symbol: str, interval: str = "5m", limit: int = 100) -> pd.DataFrame:
        """Fetch candlestick/kline history and return a formatted pandas DataFrame."""
        endpoint = "/fapi/v1/klines" if self.is_futures else "/api/v3/klines"
        params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        raw_klines = self._request("GET", endpoint, params)

        if not isinstance(raw_klines, list):
            logger.warning(f"Failed to fetch klines for {symbol}: {raw_klines}")
            return pd.DataFrame()

        df = pd.DataFrame(raw_klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        
        # Convert numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
            
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df

    def set_leverage(self, symbol: str, leverage: int = 5) -> Dict[str, Any]:
        """Set leverage for Futures trading."""
        if not self.is_futures:
            return {"status": "skipped", "message": "Leverage only applies to Futures."}
        
        endpoint = "/fapi/v1/leverage"
        params = {"symbol": symbol.upper(), "leverage": leverage}
        return self._request("POST", endpoint, params, signed=True)

    def get_account_balance(self) -> Dict[str, float]:
        """Fetch account USDT balance."""
        if self.is_futures:
            endpoint = "/fapi/v2/account"
            res = self._request("GET", endpoint, signed=True)
            if "assets" in res:
                for asset in res["assets"]:
                    if asset["asset"] == "USDT":
                        return {"wallet_balance": float(asset["walletBalance"]), "available": float(asset["availableBalance"])}
        else:
            endpoint = "/api/v3/account"
            res = self._request("GET", endpoint, signed=True)
            if "balances" in res:
                for bal in res["balances"]:
                    if bal["asset"] == "USDT":
                        return {"wallet_balance": float(bal["free"]) + float(bal["locked"]), "available": float(bal["free"])}
        return {"wallet_balance": 0.0, "available": 0.0}

    def create_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Place market or limit order."""
        endpoint = "/fapi/v1/order" if self.is_futures else "/api/v3/order"
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }

        if order_type.upper() == "LIMIT":
            params["timeInForce"] = "GTC"
            params["price"] = price

        return self._request("POST", endpoint, params, signed=True)
