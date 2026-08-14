"""
app.py — Flask Web Dashboard server for Multi-Strategy Crypto Options Bot.

v3.0 — Supports MultiStrategyRunner (spot + options) and legacy CryptoStrategyRunner.
"""

from flask import Flask, render_template, jsonify, request
from typing import Any
import os
from binance_crypto_bot.config import DASHBOARD_HOST, DASHBOARD_PORT
from binance_crypto_bot.broker.paper_crypto_broker import PaperCryptoBroker
from binance_crypto_bot.broker.paper_delta_broker import PaperDeltaBroker
from binance_crypto_bot.broker.paper_spot_broker import PaperSpotBroker

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

    from binance_crypto_bot.engine.multi_strategy_runner import MultiStrategyRunner
    is_multi = isinstance(RUNNER_REF, MultiStrategyRunner)

    # ── Balance ──────────────────────────────────────────────────────────────
    balance_info = RUNNER_REF.get_account_balance() if is_multi else (
        RUNNER_REF.broker.get_account_balance()
    )

    # ── Positions ─────────────────────────────────────────────────────────────
    if is_multi:
        positions = RUNNER_REF.get_positions()
    else:
        broker = RUNNER_REF.broker
        positions = list(broker.positions.values()) if hasattr(broker, "positions") else []

    # ── Trade history ─────────────────────────────────────────────────────────
    if is_multi:
        trade_hist = RUNNER_REF.get_trade_history()[:30]
    else:
        trade_hist = getattr(RUNNER_REF.broker, "trade_history", [])[-30:]

    # ── AI logs ───────────────────────────────────────────────────────────────
    ai_logs = []
    if hasattr(RUNNER_REF, "ai_overseer") and hasattr(RUNNER_REF.ai_overseer, "decision_logs"):
        ai_logs = RUNNER_REF.ai_overseer.decision_logs[:15]

    # ── Sub-broker balances (multi only) ──────────────────────────────────────
    sub_balances = {}
    if is_multi:
        sub_balances = {
            "spot":    RUNNER_REF.spot_broker.get_account_balance(),
            "options": RUNNER_REF.options_broker.get_account_balance(),
        }

    from binance_crypto_bot.strategies.delta_option_scalper import is_peak_window_active
    peak_active = is_peak_window_active()

    bot_status = "RUNNING" if RUNNER_REF.running and not RUNNER_REF.paused else (
        "PAUSED" if RUNNER_REF.paused else "STOPPED"
    )

    return jsonify({
        "status":             bot_status,
        "mode":               "paper",
        "is_multi_strategy":  is_multi,
        "balance":            balance_info,
        "sub_balances":       sub_balances,
        "positions":          positions,
        "signals":            RUNNER_REF.latest_signals,
        "tickers":            RUNNER_REF.market_prices,
        "trade_history":      trade_hist,
        "peak_window_active": peak_active,
        "ai_decision_logs":   ai_logs,
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
        from binance_crypto_bot.engine.multi_strategy_runner import MultiStrategyRunner
        if isinstance(RUNNER_REF, MultiStrategyRunner):
            RUNNER_REF.square_off_all()
        elif hasattr(RUNNER_REF, "executor"):
            RUNNER_REF.executor.square_off_all(RUNNER_REF.market_prices)
        return jsonify({"success": True, "message": "All positions squared off"})
    return jsonify({"success": False, "message": "Bot runner unavailable"})

@app.route("/api/control/reset", methods=["POST"])
def reset_account():
    if RUNNER_REF:
        from binance_crypto_bot.engine.multi_strategy_runner import MultiStrategyRunner
        if isinstance(RUNNER_REF, MultiStrategyRunner):
            RUNNER_REF.spot_broker.positions    = {}
            RUNNER_REF.spot_broker.trade_history= []
            RUNNER_REF.spot_broker.wallet_balance = RUNNER_REF.spot_broker.initial_capital
            RUNNER_REF.spot_broker.realized_pnl   = 0.0
            RUNNER_REF.options_broker.positions    = {}
            RUNNER_REF.options_broker.trade_history= []
            RUNNER_REF.options_broker.wallet_balance = RUNNER_REF.options_broker.initial_capital
            RUNNER_REF.options_broker.realized_pnl   = 0.0
        else:
            broker = RUNNER_REF.broker
            broker.positions = {}
            broker.trade_history = []
            if hasattr(broker, "wallet_balance"):
                broker.wallet_balance = broker.initial_capital
                broker.realized_pnl = 0.0
        return jsonify({"success": True, "message": "Account reset"})
    return jsonify({"success": False, "message": "Bot runner unavailable"})

def start_dashboard(host: str = DASHBOARD_HOST, port: int = DASHBOARD_PORT):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)
