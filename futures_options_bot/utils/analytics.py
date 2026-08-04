"""
analytics.py — F&O Trade Performance Analytics & Export Utility.
"""

import json
import os
import pandas as pd
from datetime import datetime

ANALYTICS_FILE = "fo_trades.json"

def record_trade(trade_data: dict):
    """Saves completed F&O trade details to local JSON file."""
    trades = []
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, "r") as f:
                trades = json.load(f)
        except Exception:
            trades = []

    trade_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trades.append(trade_data)

    with open(ANALYTICS_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def generate_summary() -> dict:
    """Calculates win rate, total P&L, max drawdown for F&O trades."""
    if not os.path.exists(ANALYTICS_FILE):
        return {"total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "profit_factor": 0.0}

    try:
        with open(ANALYTICS_FILE, "r") as f:
            trades = json.load(f)
        
        if not trades:
            return {"total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "profit_factor": 0.0}

        df = pd.DataFrame(trades)
        if "pnl" not in df.columns:
            return {"total_trades": len(trades), "win_rate": 0.0, "total_pnl": 0.0, "profit_factor": 0.0}

        total_trades = len(df)
        wins = df[df["pnl"] > 0]
        losses = df[df["pnl"] < 0]
        win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
        total_pnl = df["pnl"].sum()
        
        gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0.0
        gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "profit_factor": round(profit_factor, 2)
        }
    except Exception as e:
        return {"error": str(e)}
