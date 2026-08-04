"""
zerodha_fo_client.py — Zerodha Kite Connect F&O Broker Client.
"""

from futures_options_bot.broker.base_broker import BaseFOBroker
from futures_options_bot.utils.logger import logger
from futures_options_bot.config import KITE_API_KEY, KITE_ACCESS_TOKEN

class ZerodhaFOBroker(BaseFOBroker):

    def __init__(self):
        self.api_key = KITE_API_KEY
        self.access_token = KITE_ACCESS_TOKEN
        self.kite = None

    def connect(self) -> bool:
        """Connects to Zerodha Kite Connect API."""
        try:
            from kiteconnect import KiteConnect
            self.kite = KiteConnect(api_key=self.api_key)
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                logger.info("✅ [Zerodha] Connected to Kite Connect for F&O trading.")
                return True
            else:
                logger.warning("⚠️ [Zerodha] KITE_ACCESS_TOKEN not set in config/.env.")
                return False
        except ImportError:
            logger.error("❌ 'kiteconnect' library not installed. Run: pip install kiteconnect")
            return False
        except Exception as e:
            logger.error(f"❌ Zerodha connection failed: {e}")
            return False

    def get_underlying_ltp(self, symbol: str) -> float:
        if not self.kite:
            return 0.0
        try:
            quote = self.kite.quote(f"NSE:{symbol}")
            if quote and f"NSE:{symbol}" in quote:
                return float(quote[f"NSE:{symbol}"]["last_price"])
        except Exception as e:
            logger.error(f"Error fetching Zerodha LTP: {e}")
        return 0.0

    def get_option_chain(self, symbol: str, expiry_date=None) -> list:
        return []

    def place_order(self, symbol: str, option_type: str, strike: float,
                    transaction_type: str, quantity: int, order_type: str = "MARKET",
                    price: float = 0.0) -> dict:
        return {}

    def get_positions(self) -> list:
        if not self.kite:
            return []
        try:
            pos = self.kite.positions()
            return pos.get("net", [])
        except Exception as e:
            logger.error(f"Error fetching Zerodha positions: {e}")
        return []

    def square_off_all(self) -> bool:
        return True
