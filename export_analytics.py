"""
export_analytics.py — Exporter & Strategy Performance Reporter.

Run this script anytime to:
  1. Print a full performance report of your strategies (Win rate, total P&L per strategy).
  2. Export all trades and signal telemetry to CSV files for Excel/Python analysis.

Usage:
  python export_analytics.py
"""

import os
import sys
import csv
import sqlite3
from datetime import datetime

# Windows console encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import config
from utils.analytics_logger import AnalyticsLogger


def export_data():
    os.makedirs("reports", exist_ok=True)
    db_path = config.DATABASE_PATH
    analytics = AnalyticsLogger(db_path)

    print("=" * 60)
    print(" 📊 TRADING BOT — 1-3 WEEK PAPER TRADING ANALYTICS REPORT")
    print("=" * 60)
    print(f" Report Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Database File:       {db_path}\n")

    # 1. Strategy Breakdown
    summary = analytics.get_strategy_performance_summary()
    if summary:
        print("🏆 STRATEGY PERFORMANCE BREAKDOWN:")
        print(f" {'Strategy':<18} | {'Trades':<7} | {'Wins':<5} | {'Losses':<6} | {'Win Rate':<8} | {'Total P&L (INR)':<15}")
        print("-" * 75)
        for s in summary:
            pnl_str = f"+{s['total_pnl']:.2f}" if s['total_pnl'] > 0 else f"{s['total_pnl']:.2f}"
            print(f" {s['strategy']:<18} | {s['total_trades']:<7} | {s['wins']:<5} | {s['losses']:<6} | {s['win_rate']:>6.1f}% | {pnl_str:>15}")
        print("-" * 75)
    else:
        print("ℹ No completed trades found yet in database.\n")

    # 2. Export Trades to CSV
    trades_csv = "reports/trades_export.csv"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades ORDER BY entry_time DESC").fetchall()
        if trades:
            with open(trades_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(trades[0].keys())
                for t in trades:
                    writer.writerow(list(t))
            print(f"✓ Exported {len(trades)} trades to: {trades_csv}")

    # 3. Export Telemetry Signals to CSV
    telemetry_csv = "reports/signals_telemetry_export.csv"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        telemetry = conn.execute("SELECT * FROM signal_telemetry ORDER BY timestamp DESC").fetchall()
        if telemetry:
            with open(telemetry_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(telemetry[0].keys())
                for tm in telemetry:
                    writer.writerow(list(tm))
            print(f"✓ Exported {len(telemetry)} telemetry signals to: {telemetry_csv}")

    print("\n" + "=" * 60)
    print(" You can open the CSV files in Microsoft Excel or Google Sheets")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    export_data()
