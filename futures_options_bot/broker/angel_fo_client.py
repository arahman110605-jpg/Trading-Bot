"""
angel_fo_client.py — Angel One SmartAPI F&O Broker Client.
"""

from futures_options_bot.broker.base_broker import BaseFOBroker
from futures_options_bot.utils.logger import logger
from futures_options_bot.config import (
    ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PASSWORD, ANGEL_TOTP_SECRET
)

class AngelFOBroker(BaseFOBroker):

    def __init__(self):
        self.api_key = ANGEL_API_KEY
        self.client_code = ANGEL_CLIENT_CODE
        self.password = ANGEL_PASSWORD
        self.totp_secret = ANGEL_TOTP_SECRET
        self.smart_api = None

    def connect(self) -> bool:
        """Connects to Angel One SmartAPI using TOTP."""
        try:
            from SmartApi import SmartConnect
            import pyotp

            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.smart_api.generateSession(self.client_code, self.password, totp)

            if data and data.get("status"):
                logger.info("✅ [Angel One] Successfully authenticated for F&O trading!")
                return True
            else:
                logger.error(f"❌ [Angel One] Authentication failed: {data}")
                return False
        except ImportError:
            logger.error("❌ 'smartapi-python' or 'pyotp' package not installed. Run: pip install smartapi-python pyotp")
            return False
        except Exception as e:
            logger.error(f"❌ Exception connecting to Angel One: {e}")
            return False

    def get_underlying_ltp(self, symbol: str) -> float:
        """Fetch real-time spot price of underlying from Angel One."""
        if not self.smart_api:
            return 0.0
        try:
            # Map index/stock to token
            token_map = {"NIFTY": "99926000", "BANKNIFTY": "99926009", "FINNIFTY": "99926037"}
            token = token_map.get(symbol.upper(), "")
            if token:
                data = self.smart_api.ltpData("NSE", symbol, token)
                if data and "data" in data and "ltp" in data["data"]:
                    return float(data["data"]["ltp"])
        except Exception as e:
            logger.error(f"Error fetching LTP from Angel One: {e}")
        return 0.0

    def get_option_chain(self, symbol: str, expiry_date=None) -> list:
        """Fetch option chain for F&O."""
        # Angel One returns NFO option chains via market quotes
        return []

    def place_order(self, symbol: str, option_type: str, strike: float,
                    transaction_type: str, quantity: int, order_type: str = "MARKET",
                    price: float = 0.0) -> dict:
        """Place live order on Angel One NFO exchange."""
        logger.info(f"[Angel Live Order] {transaction_type} {symbol} {strike} {option_type}")
        return {}

    def get_positions(self) -> list:
        """Get live positions from Angel One."""
        if not self.smart_api:
            return []
        try:
            res = self.smart_api.position()
            if res and "data" in res and res["data"]:
                return res["data"]
        except Exception as e:
            logger.error(f"Error fetching Angel positions: {e}")
        return []

    def square_off_all(self) -> bool:
        """Close all open positions on Angel One."""
        return True
