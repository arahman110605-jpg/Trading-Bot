"""
app.py — Flask Web Dashboard server for Binance Crypto & Web3 Bot.
"""

from flask import Flask, render_template, jsonify, request
from typing import Any
import os
from binance_crypto_bot.config import DASHBOARD_HOST, DASHBOARD_PORT
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker

app = Flask(__name__, template_folder="templates", static_folder="static")

RUNNER_REF = None

def set_runner_reference(runner: Any):
    global RUNNER_REF
    RUNNER_REF = runner

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    if RUNNER_REF is None:
        return jsonify({"status": "OFFLINE", "message": "Bot not initialized"})

    broker = RUNNER_REF.broker
    balance_info = broker.get_account_balance()

    positions = []
    if isinstance(broker, PaperCryptoBroker):
        positions = list(broker.positions.values())

    return jsonify({
        "status": "RUNNING" if RUNNER_REF.running and not RUNNER_REF.paused else ("PAUSED" if RUNNER_REF.paused else "STOPPED"),
        "mode": getattr(broker, "mode", "paper"),
        "balance": balance_info,
        "positions": positions,
        "signals": RUNNER_REF.latest_signals,
        "tickers": RUNNER_REF.market_prices,
        "trade_history": getattr(broker, "trade_history", [])[-20:]
    })

@app.route("/api/control/pause", methods=["POST"])
def pause_bot():
    if RUNNER_REF:
        RUNNER_REF.pause()
        return jsonify({"success": True, "message": "Bot paused"})
    return jsonify({"success": False, "message": "Bot runner unavailable"})

@app.route("/api/control/resume", methods=["POST"])
def resume_bot():
    if RUNNER_REF:
        RUNNER_REF.resume()
        return jsonify({"success": True, "message": "Bot resumed"})
    return jsonify({"success": False, "message": "Bot runner unavailable"})

@app.route("/api/control/squareoff", methods=["POST"])
def square_off():
    if RUNNER_REF:
        RUNNER_REF.executor.square_off_all(RUNNER_REF.market_prices)
        return jsonify({"success": True, "message": "All positions squared off"})
    return jsonify({"success": False, "message": "Bot runner unavailable"})

def start_dashboard(host: str = DASHBOARD_HOST, port: int = DASHBOARD_PORT):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)
