"""
XM Competitions Local Signal Bridge & Strategy Server
Continuously scans live market data from MT5 and serves optimal signals
to the XM Competitions Browser Bot via a lightweight local REST/WebSocket server.
"""
import sys
import os
import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Adjust path to import core strategy modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Bridge]: %(message)s")
logger = logging.getLogger("CompetitionBridge")

# Global Signal State
LATEST_SIGNALS = {}
SERVER_PORT = 8765

class BridgeHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/signals":
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "online",
                "timestamp": time.time(),
                "timeframe": config.TIMEFRAME,
                "signals": LATEST_SIGNALS
            }).encode("utf-8"))
        elif parsed.path == "/status":
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "running"}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/inject_signal":
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            try:
                data = json.loads(body)
                sym = data.get("symbol", "EURUSD")
                global LATEST_SIGNALS
                LATEST_SIGNALS[sym] = {
                    "symbol": sym,
                    "signal": data.get("signal", "BUY"),
                    "price": data.get("price", 1.15875),
                    "stop_loss": data.get("stop_loss", 1.15650),
                    "take_profit": data.get("take_profit", 1.16300),
                    "lots": data.get("lots", 0.10),
                    "reason": data.get("reason", "Manual Test Signal Trigger"),
                    "timestamp": time.time()
                }
                logger.info(f"💉 Signal Injected: {LATEST_SIGNALS[sym]}")
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "signal_injected", "data": LATEST_SIGNALS[sym]}).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif parsed.path == "/trade_executed":
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            try:
                data = json.loads(body)
                logger.info(f"🎉 Trade Executed in Browser: {data}")
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)

    def log_message(self, format, *args):
        return  # Suppress default HTTP logging to keep console clean

def start_strategy_scanner():
    """Runs continuous strategy scanner on MT5 data"""
    global LATEST_SIGNALS
    client = MT5Client(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH
    )

    if not client.connect():
        logger.error("Could not connect MT5 Client for strategy feed.")
        return

    strategy = TrendMomentumStrategy(
        ema_fast=config.EMA_FAST,
        ema_slow=config.EMA_SLOW,
        ema_trend=config.EMA_TREND,
        rsi_period=config.RSI_PERIOD,
        rsi_buy_min=config.RSI_BUY_MIN,
        rsi_buy_max=config.RSI_BUY_MAX,
        rsi_sell_min=config.RSI_SELL_MIN,
        rsi_sell_max=config.RSI_SELL_MAX,
        atr_period=config.ATR_PERIOD,
        atr_sl_mult=config.ATR_SL_MULTIPLIER,
        atr_tp_mult=config.ATR_TP_MULTIPLIER,
    )

    symbols_to_scan = ["EURUSD", "GBPUSD", "USDJPY", "GOLD"]
    logger.info(f"Competition Scanner started for: {symbols_to_scan}")

    while True:
        try:
            for sym in symbols_to_scan:
                df = client.get_market_data(sym, timeframe_str="M15", count=250)
                if df is not None and len(df) >= 220:
                    sig = strategy.generate_signal(df)
                    if sig:
                        LATEST_SIGNALS[sym] = {
                            "symbol": sym,
                            "signal": sig["signal"],
                            "price": sig["price"],
                            "stop_loss": round(sig["stop_loss"], 5),
                            "take_profit": round(sig["take_profit"], 5),
                            "reason": sig["reason"],
                            "timestamp": time.time()
                        }
                        logger.info(f"🔥 Signal for {sym}: {sig['signal']} @ {sig['price']} | TP: {sig['take_profit']} | SL: {sig['stop_loss']}")
                    else:
                        # Clear old signal if no longer valid
                        if sym in LATEST_SIGNALS and (time.time() - LATEST_SIGNALS[sym].get("timestamp", 0) > 900):
                            del LATEST_SIGNALS[sym]
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error in scanner loop: {e}")
            time.sleep(5)

def run_bridge_server():
    scanner_thread = threading.Thread(target=start_strategy_scanner, daemon=True)
    scanner_thread.start()

    server = HTTPServer(("localhost", SERVER_PORT), BridgeHandler)
    logger.info(f"🚀 XM Competition Bridge Server running at http://localhost:{SERVER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Bridge server stopping...")
        server.server_close()

if __name__ == "__main__":
    run_bridge_server()
