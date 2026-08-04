"""
dashboard/server.py — Flask + Flask-SocketIO web dashboard server.

Serves the live trading dashboard and pushes real-time updates via WebSocket.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import TYPE_CHECKING

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

import config
from utils.logger import get_logger

if TYPE_CHECKING:
    from engine.strategy_runner import StrategyRunner
    from engine.order_manager import OrderManager
    from utils.trade_journal import TradeJournal

log = get_logger("Dashboard")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "trading_bot_secret_key_2024"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global references — set by init_dashboard()
_runner:  "StrategyRunner | None"  = None
_orders:  "OrderManager | None"    = None
_journal: "TradeJournal | None"    = None


def init_dashboard(runner, order_mgr, journal):
    """Connect dashboard to the trading engine."""
    global _runner, _orders, _journal
    _runner  = runner
    _orders  = order_mgr
    _journal = journal

    # Push updates to dashboard after every scan
    runner.set_update_callback(_push_update)
    log.info("Dashboard initialised and connected to engine.")


def _push_update():
    """Push current state to all connected dashboard clients."""
    socketio.emit("update", _build_state(), namespace="/")


def _build_state() -> dict:
    """Collect all dashboard data into one dict."""
    stats    = _journal.get_todays_stats() if _journal else {}
    trades   = _journal.get_todays_trades() if _journal else []
    signals  = _runner.get_signal_log() if _runner else []
    positions = _orders.get_open_positions() if _orders else []

    return {
        "mode":       config.TRADING_MODE,
        "bot_status": _runner.status if _runner else "STOPPED",
        "time":       datetime.now().strftime("%H:%M:%S"),
        "date":       datetime.now().strftime("%d %b %Y"),
        "stats":      stats,
        "positions":  positions,
        "trades":     trades[-30:],   # Last 30 trades
        "signals":    signals[:20],   # Last 20 signals
        "watchlist":  config.WATCHLIST,
        "strategies": config.STRATEGIES,
        "capital":    config.CAPITAL,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(_build_state())


@app.route("/api/bot/start", methods=["POST"])
def api_start():
    if _runner:
        _runner.start()
        log.info("Bot started via dashboard")
        return jsonify({"status": "started"})
    return jsonify({"error": "Runner not initialised"}), 500


@app.route("/api/bot/stop", methods=["POST"])
def api_stop():
    if _runner:
        _runner.stop()
        log.info("Bot stopped via dashboard")
        return jsonify({"status": "stopped"})
    return jsonify({"error": "Runner not initialised"}), 500


@app.route("/api/bot/pause", methods=["POST"])
def api_pause():
    if _runner:
        _runner.pause()
        return jsonify({"status": "paused"})
    return jsonify({"error": "Runner not initialised"}), 500


@app.route("/api/square_off", methods=["POST"])
def api_square_off():
    if _orders:
        _orders.square_off_all()
        log.warning("Manual square-off triggered via dashboard")
        return jsonify({"status": "squared_off"})
    return jsonify({"error": "Orders not initialised"}), 500


@app.route("/api/trades")
def api_trades():
    if _journal:
        return jsonify(_journal.get_all_trades(limit=100))
    return jsonify([])


@app.route("/api/analytics")
def api_analytics():
    if _journal:
        from utils.analytics_logger import AnalyticsLogger
        analytics = AnalyticsLogger()
        return jsonify({
            "strategy_performance": analytics.get_strategy_performance_summary(),
            "signal_telemetry": analytics.get_signal_history(limit=50)
        })
    return jsonify({})


@app.route("/api/toggle_mode", methods=["POST"])
def api_toggle_mode():
    """Toggle between paper and live mode (requires bot stop first)."""
    if _runner and _runner.status == "RUNNING":
        return jsonify({"error": "Stop bot before changing mode"}), 400
    new_mode = "live" if config.TRADING_MODE == "paper" else "paper"
    config.TRADING_MODE = new_mode
    if _orders:
        _orders.kite.mode = new_mode
    return jsonify({"mode": new_mode})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    log.debug("Dashboard client connected")
    emit("update", _build_state())


@socketio.on("ping")
def on_ping():
    emit("pong", {"time": datetime.now().isoformat()})


# ── Launch ───────────────────────────────────────────────────────────────────

def run_dashboard(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT):
    """Start the dashboard server (blocking)."""
    log.info("Dashboard starting at http://localhost:%d", port)
    socketio.run(
        app,
        host=host,
        port=port,
        debug=config.DASHBOARD_DEBUG,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
        log_output=False,
    )
