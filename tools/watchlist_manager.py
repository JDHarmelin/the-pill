"""
Watchlist Manager — simple watchlist storage in the SQLite DB.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional

from db import _row_to_dict


class WatchlistManager:
    def __init__(self, db):
        self.db = db
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db.db_path)
        conn.row_factory = _row_to_dict
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created TEXT
                );
                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watchlist_id TEXT REFERENCES watchlists(id) ON DELETE CASCADE,
                    ticker TEXT NOT NULL,
                    notes TEXT,
                    added_date TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_watchlist_items ON watchlist_items(watchlist_id);
                CREATE INDEX IF NOT EXISTS idx_watchlist_items_ticker ON watchlist_items(watchlist_id, ticker);
                """
            )

    def get_watchlists(self) -> List[dict]:
        """Return all watchlists with their items."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlists ORDER BY created DESC"
            ).fetchall()
            for row in rows:
                row["items"] = self._get_items(row["id"])
            return rows

    def _get_items(self, watchlist_id: str) -> List[dict]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM watchlist_items WHERE watchlist_id = ? ORDER BY added_date DESC",
                (watchlist_id,),
            ).fetchall()

    def get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        """Return a single watchlist with its items."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM watchlists WHERE id = ?", (watchlist_id,)
            ).fetchone()
            if not row:
                return None
            row["items"] = self._get_items(watchlist_id)
            return row

    def create_watchlist(self, name: str) -> dict:
        """Create a new watchlist."""
        wid = str(uuid.uuid4())[:8]
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO watchlists (id, name, created) VALUES (?, ?, ?)",
                (wid, name, created),
            )
        return self.get_watchlist(wid)

    def add_ticker(self, watchlist_id: str, ticker: str, notes: str = "") -> dict:
        """Add ticker to watchlist."""
        ticker = ticker.upper()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM watchlist_items WHERE watchlist_id = ? AND ticker = ?",
                (watchlist_id, ticker),
            ).fetchone()
            if existing:
                return {
                    "watchlist_id": watchlist_id,
                    "ticker": ticker,
                    "status": "already_exists",
                }

            conn.execute(
                "INSERT INTO watchlist_items (watchlist_id, ticker, notes, added_date) VALUES (?, ?, ?, ?)",
                (watchlist_id, ticker, notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        return {"watchlist_id": watchlist_id, "ticker": ticker, "status": "added"}

    def remove_ticker(self, watchlist_id: str, ticker: str) -> bool:
        """Remove ticker from watchlist."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM watchlist_items WHERE watchlist_id = ? AND ticker = ?",
                (watchlist_id, ticker.upper()),
            )
            return cur.rowcount > 0

    def get_signals(self, watchlist_id: str):
        """Scan all tickers in watchlist for signals."""
        from tools.signal_engine import SignalEngine

        watchlist = self.get_watchlist(watchlist_id)
        if not watchlist:
            return []
        tickers = [item["ticker"] for item in watchlist.get("items", [])]
        if not tickers:
            return []
        se = SignalEngine()
        return se.scan_watchlist(tickers)
