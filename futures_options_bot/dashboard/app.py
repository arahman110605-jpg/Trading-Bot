"""
app.py — Flask + SocketIO Server for F&O Live Web Dashboard.
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
from futures_options_bot.config import DASHBOARD_HOST, DASHBOARD_PORT, CAPITAL
from futures_options_bot.utils.analytics import generate_summary
from futures_options_bot.utils.logger import logger

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "fo_trading_bot_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

# References set by main runner
global_broker = None
global_runner = None


def set_runner_references(broker, runner):
    global global_broker, global_runner
    global_broker = broker
    global_runner = runner


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    summary = generate_summary()
    positions = global_broker.get_positions() if global_broker else []
    total_pnl = sum(p.get("pnl", 0.0) for p in positions)
    
    return jsonify({
        "status": "RUNNING" if global_runner and global_runner.running else "STOPPED",
        "capital": global_broker.capital if global_broker else CAPITAL,
        "active_positions_count": len(positions),
        "open_pnl": round(total_pnl, 2),
        "summary": summary,
    })


@app.route("/api/positions")
def get_positions():
    positions = global_broker.get_positions() if global_broker else []
    return jsonify(positions)


@app.route("/api/option_chain")
def get_option_chain():
    symbol = request.args.get("symbol", "NIFTY")
    if global_broker:
        chain = global_broker.get_option_chain(symbol)
        return jsonify(chain)
    return jsonify([])


@app.route("/api/square_off", methods=["POST"])
def square_off():
    if global_broker:
        global_broker.square_off_all()
        return jsonify({"status": "SUCCESS", "message": "All F&O positions squared off."})
    return jsonify({"status": "ERROR", "message": "Broker not initialized."}), 400


def background_broadcaster():
    """Emits real-time state updates to web clients over WebSocket every 1 second."""
    while True:
        try:
            if global_broker:
                positions = global_broker.get_positions()
                spot_prices = global_broker.spot_prices if hasattr(global_broker, "spot_prices") else {}
                total_pnl = sum(p.get("pnl", 0.0) for p in positions)
                
                socketio.emit("market_update", {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "spot_prices": spot_prices,
                    "positions": positions,
                    "total_pnl": round(total_pnl, 2),
                    "capital": global_broker.capital,
                })
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
        time.sleep(1.5)


def start_dashboard(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    t = threading.Thread(target=background_broadcaster, daemon=True)
    t.start()
    logger.info(f"🌐 F&O Web Dashboard running at http://localhost:{port}")
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
