"""
utils/trade_journal.py — SQLite-backed trade journal for tracking all trades and P&L.
"""

import sqlite3
import os
from datetime import date, datetime
from typing import List, Optional, Dict, Any

import config
from utils.logger import get_logger

log = get_logger("TradeJournal")


class TradeJournal:
    """Persists all trades and provides P&L reporting."""

    def __init__(self, db_path: str = config.DATABASE_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date    TEXT NOT NULL,
                    symbol        TEXT NOT NULL,
                    exchange      TEXT NOT NULL,
                    direction     TEXT NOT NULL,   -- BUY / SELL
                    quantity      INTEGER NOT NULL,
                    entry_price   REAL NOT NULL,
                    exit_price    REAL,
                    stop_loss     REAL,
                    target        REAL,
                    strategy      TEXT,
                    status        TEXT DEFAULT 'OPEN',  -- OPEN / CLOSED / SL_HIT / TARGET_HIT
                    pnl           REAL DEFAULT 0,
                    entry_time    TEXT,
                    exit_time     TEXT,
                    order_id      TEXT,
                    exit_order_id TEXT,
                    mode          TEXT DEFAULT 'paper',
                    notes         TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_summary (
                    summary_date  TEXT PRIMARY KEY,
                    total_trades  INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades  INTEGER DEFAULT 0,
                    gross_pnl     REAL DEFAULT 0,
                    charges       REAL DEFAULT 0,
                    net_pnl       REAL DEFAULT 0
                );
            """)
        log.info("Trade journal database initialised at %s", self.db_path)

    # ── Write ──────────────────────────────────────────────────────────────

    def log_entry(
        self,
        symbol: str,
        exchange: str,
        direction: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        strategy: str,
        order_id: str = "",
        mode: str = config.TRADING_MODE,
    ) -> int:
        """Record a new trade entry. Returns the trade ID."""
        today = date.today().isoformat()
        now   = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO trades
                   (trade_date, symbol, exchange, direction, quantity,
                    entry_price, stop_loss, target, strategy,
                    status, entry_time, order_id, mode)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (today, symbol, exchange, direction, quantity,
                 entry_price, stop_loss, target, strategy,
                 "OPEN", now, order_id, mode),
            )
            trade_id = cur.lastrowid
        log.info("ENTRY logged | %s %s x%d @ %.2f | id=%d", direction, symbol, quantity, entry_price, trade_id)
        return trade_id

    def log_exit(
        self,
        trade_id: int,
        exit_price: float,
        status: str = "CLOSED",
        exit_order_id: str = "",
        notes: str = "",
    ):
        """Record exit details and compute P&L."""
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                log.warning("Trade id=%d not found for exit", trade_id)
                return
            direction = row["direction"]
            qty = row["quantity"]
            entry  = row["entry_price"]
            if direction == "BUY":
                pnl = (exit_price - entry) * qty
            else:
                pnl = (entry - exit_price) * qty

            conn.execute(
                """UPDATE trades SET
                   exit_price=?, exit_time=?, status=?,
                   exit_order_id=?, pnl=?, notes=?
                   WHERE id=?""",
                (exit_price, now, status, exit_order_id, round(pnl, 2), notes, trade_id),
            )
        log.info("EXIT logged | id=%d | exit=%.2f | P&L=%.2f | %s", trade_id, exit_price, pnl, status)

    # ── Read ───────────────────────────────────────────────────────────────

    def get_open_trades(self) -> List[Dict]:
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE trade_date=? AND status='OPEN'", (today,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_todays_trades(self) -> List[Dict]:
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE trade_date=? ORDER BY entry_time DESC", (today,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_todays_pnl(self) -> float:
        today = date.today().isoformat()
        with self._conn() as conn:
            result = conn.execute(
                "SELECT COALESCE(SUM(pnl),0) FROM trades WHERE trade_date=?", (today,)
            ).fetchone()
        return round(result[0], 2)

    def get_todays_stats(self) -> Dict[str, Any]:
        trades = self.get_todays_trades()
        closed = [t for t in trades if t["status"] != "OPEN"]
        winners = [t for t in closed if t["pnl"] > 0]
        losers  = [t for t in closed if t["pnl"] <= 0]
        total_pnl = sum(t["pnl"] for t in closed)
        return {
            "total_trades":   len(closed),
            "open_trades":    len([t for t in trades if t["status"] == "OPEN"]),
            "winning_trades": len(winners),
            "losing_trades":  len(losers),
            "win_rate":       round(len(winners) / len(closed) * 100, 1) if closed else 0,
            "gross_pnl":      round(total_pnl, 2),
            "net_pnl":        round(total_pnl, 2),  # Charges TBD
        }

    def get_all_trades(self, limit: int = 200) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
