"""
delta_option_client.py — Real Delta Exchange REST Client for Crypto Options.
"""

import hmac
import hashlib
import time
import requests
from typing import Dict, Any, List, Optional
from binance_crypto_bot.config import DELTA_API_KEY, DELTA_API_SECRET, DELTA_BASE_URL
from binance_crypto_bot.utils.logger import logger

class DeltaOptionClient:
    def __init__(self, api_key: str = DELTA_API_KEY, api_secret: str = DELTA_API_SECRET, base_url: str = DELTA_BASE_URL):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _generate_signature(self, method: str, path: str, timestamp: str, payload_str: str = "") -> str:
        """Generate Delta Exchange HMAC SHA256 signature."""
        signature_data = method.upper() + timestamp + path + payload_str
        return hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict[str, Any] = None, data: Dict[str, Any] = None, signed: bool = True) -> Dict[str, Any]:
        """Send authenticated HTTP request to Delta Exchange API."""
        url = f"{self.base_url}{endpoint}"
        query_str = ""
        
        if params:
            query_str = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            url += query_str

        path_with_query = endpoint + query_str
        timestamp = str(int(time.time()))
        payload_str = ""

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if signed and self.api_key and self.api_secret:
            if data:
                import json
                payload_str = json.dumps(data)
            
            sig = self._generate_signature(method, path_with_query, timestamp, payload_str)
            headers["api-key"] = self.api_key
            headers["signature"] = sig
            headers["timestamp"] = timestamp

        try:
            if method.upper() == "GET":
                resp = self.session.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                resp = self.session.post(url, headers=headers, data=payload_str, timeout=10)
            elif method.upper() == "DELETE":
                resp = self.session.delete(url, headers=headers, data=payload_str, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Delta API Request Error ({endpoint}): {e}")
            return {"success": False, "error": str(e)}

    def ping(self) -> bool:
        """Check Delta Exchange API connectivity."""
        res = self._request("GET", "/v2/products", signed=False)
        return "success" in res or "result" in res or isinstance(res, dict)

    def is_connected(self) -> bool:
        return self.ping()

    def get_account_balance(self) -> Dict[str, float]:
        """Fetch account USDT wallet balance."""
        res = self._request("GET", "/v2/wallet/balances", signed=True)
        if isinstance(res, dict) and "result" in res:
            for item in res["result"]:
                if item.get("asset_symbol") == "USDT":
                    balance = float(item.get("balance", 0.0))
                    available = float(item.get("available_balance", balance))
                    return {"wallet_balance": round(balance, 2), "available": round(available, 2)}
        return {"wallet_balance": 0.0, "available": 0.0}

    def get_option_products(self, underlying: str = "BTC") -> List[Dict[str, Any]]:
        """Fetch active option contracts for given underlying (BTC / ETH)."""
        res = self._request("GET", "/v2/products", params={"contract_types": "call_options,put_options"}, signed=False)
        products = []
        if isinstance(res, dict) and "result" in res:
            for p in res["result"]:
                if underlying.upper() in p.get("symbol", ""):
                    products.append(p)
        return products

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker for an option contract or underlying asset."""
        res = self._request("GET", f"/v2/tickers/{symbol}", signed=False)
        if isinstance(res, dict) and "result" in res:
            return res["result"]
        return {}

    def create_order(self, symbol: str, side: str, order_type: str, size: int, price: Optional[float] = None) -> Dict[str, Any]:
        """Place Market or Limit Option Order on Delta Exchange."""
        payload = {
            "product_symbol": symbol,
            "size": size,
            "side": side.lower(),  # "buy" or "sell"
            "order_type": order_type.lower()  # "market_order" or "limit_order"
        }
        if order_type.lower() == "limit_order" and price:
            payload["limit_price"] = str(price)

        res = self._request("POST", "/v2/orders", data=payload, signed=True)
        logger.info(f"[DELTA ORDER] Placed {side} {size} contracts of {symbol} | Response: {res}")
        return res
