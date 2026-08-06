"""
utils/trade_journal.py — Dual-backend trade journal for tracking all trades and P&L.
Supports Firebase Firestore with a seamless fallback to SQLite.
"""

import sqlite3
import os
import json
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Union

import config
from utils.logger import get_logger

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

log = get_logger("TradeJournal")


class TradeJournal:
    """Persists all trades and provides P&L reporting."""

    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self.use_firebase = False
        self.db = None
        self._total_pnl_cache = None
        
        # Try initializing Firebase first
        if FIREBASE_AVAILABLE:
            cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if cred_json:
                try:
                    if not firebase_admin._apps:
                        cred = credentials.Certificate(json.loads(cred_json))
                        firebase_admin.initialize_app(cred)
                    self.db = firestore.client()
                    self.use_firebase = True
                    log.info("Firebase Firestore connected successfully!")
                except Exception as e:
                    log.error("Failed to initialize Firebase: %s", e)

        # Fallback to SQLite if Firebase isn't available or configured
        if not self.use_firebase:
            log.warning("Firebase not configured. Falling back to local SQLite at %s", self.db_path)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._init_sqlite()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
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
            """)

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
    ) -> Union[int, str]:
        """Record a new trade entry. Returns the trade ID (str for Firebase, int for SQLite)."""
        today = date.today().isoformat()
        now   = datetime.now().isoformat(timespec="seconds")
        
        trade_data = {
            "trade_date": today,
            "symbol": symbol,
            "exchange": exchange,
            "direction": direction,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": None,
            "stop_loss": stop_loss,
            "target": target,
            "strategy": strategy,
            "status": "OPEN",
            "pnl": 0.0,
            "entry_time": now,
            "exit_time": None,
            "order_id": order_id,
            "exit_order_id": "",
            "mode": mode,
            "notes": ""
        }

        if self.use_firebase:
            doc_ref = self.db.collection('trades').document()
            trade_data["id"] = doc_ref.id
            doc_ref.set(trade_data)
            trade_id = doc_ref.id
        else:
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
                
        log.info("ENTRY logged | %s %s x%d @ %.2f | id=%s", direction, symbol, quantity, entry_price, trade_id)
        return trade_id

    def log_exit(
        self,
        trade_id: Union[int, str],
        exit_price: float,
        status: str = "CLOSED",
        exit_order_id: str = "",
        notes: str = "",
    ):
        """Record exit details and compute P&L."""
        now = datetime.now().isoformat(timespec="seconds")
        
        if self.use_firebase:
            doc_ref = self.db.collection('trades').document(str(trade_id))
            doc = doc_ref.get()
            if not doc.exists:
                log.warning("Trade id=%s not found for exit", trade_id)
                return
            row = doc.to_dict()
        else:
            with self._conn() as conn:
                row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                log.warning("Trade id=%s not found for exit", trade_id)
                return
            row = dict(row)

        direction = row["direction"]
        qty = row["quantity"]
        entry = row["entry_price"]
        
        if direction == "BUY":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty
            
        pnl = round(pnl, 2)

        if self.use_firebase:
            doc_ref.update({
                "exit_price": exit_price,
                "exit_time": now,
                "status": status,
                "exit_order_id": exit_order_id,
                "pnl": pnl,
                "notes": notes
            })
        else:
            with self._conn() as conn:
                conn.execute(
                    """UPDATE trades SET
                       exit_price=?, exit_time=?, status=?,
                       exit_order_id=?, pnl=?, notes=?
                       WHERE id=?""",
                    (exit_price, now, status, exit_order_id, pnl, notes, trade_id),
                )
                
        log.info("EXIT logged | id=%s | exit=%.2f | P&L=%.2f | %s", trade_id, exit_price, pnl, status)

    # ── Read ───────────────────────────────────────────────────────────────

    def get_open_trades(self) -> List[Dict]:
        today = date.today().isoformat()
        if self.use_firebase:
            docs = self.db.collection('trades').where('trade_date', '==', today).where('status', '==', 'OPEN').get()
            return [doc.to_dict() for doc in docs]
        else:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE trade_date=? AND status='OPEN'", (today,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_todays_trades(self) -> List[Dict]:
        today = date.today().isoformat()
        if self.use_firebase:
            docs = self.db.collection('trades').where('trade_date', '==', today).get()
            trades = [doc.to_dict() for doc in docs]
            trades.sort(key=lambda x: x.get('entry_time', ''), reverse=True)
            return trades
        else:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE trade_date=? ORDER BY entry_time DESC", (today,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_todays_pnl(self) -> float:
        trades = self.get_todays_trades()
        return round(sum(t.get('pnl', 0) for t in trades if t.get('status') != 'OPEN'), 2)

    def get_total_pnl(self) -> float:
        """Returns the total accumulated P&L across all historical closed trades."""
        if self._total_pnl_cache is not None:
            return self._total_pnl_cache
            
        try:
            if self.use_firebase:
                # Fetch all documents to compute total PnL
                # We use select(['pnl']) to minimise data transfer
                docs = self.db.collection('trades').select(['pnl']).get()
                total = sum(doc.to_dict().get('pnl', 0) for doc in docs)
            else:
                with self._conn() as conn:
                    res = conn.execute("SELECT SUM(pnl) FROM trades").fetchone()[0]
                    total = float(res) if res else 0.0
                    
            self._total_pnl_cache = round(total, 2)
            return self._total_pnl_cache
        except Exception as e:
            log.error("Failed to compute total PnL: %s", e)
            return 0.0

    def get_todays_stats(self) -> Dict[str, Any]:
        trades = self.get_todays_trades()
        closed = [t for t in trades if t.get("status") != "OPEN"]
        winners = [t for t in closed if t.get("pnl", 0) > 0]
        losers  = [t for t in closed if t.get("pnl", 0) <= 0]
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        return {
            "total_trades":   len(closed),
            "open_trades":    len([t for t in trades if t.get("status") == "OPEN"]),
            "winning_trades": len(winners),
            "losing_trades":  len(losers),
            "win_rate":       round(len(winners) / len(closed) * 100, 1) if closed else 0,
            "gross_pnl":      round(total_pnl, 2),
            "net_pnl":        round(total_pnl, 2),
        }

    def get_all_trades(self, limit: int = 200) -> List[Dict]:
        if self.use_firebase:
            docs = self.db.collection('trades').order_by('entry_time', direction=firestore.Query.DESCENDING).limit(limit).get()
            return [doc.to_dict() for doc in docs]
        else:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
