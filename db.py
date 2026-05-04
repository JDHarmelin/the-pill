"""
SQLite database wrapper for portfolio persistence.
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("DATABASE_URL", "portfolios.db")


def _row_to_dict(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = _row_to_dict
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS portfolios (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    capital REAL DEFAULT 10000.0,
                    strategy TEXT DEFAULT 'custom',
                    benchmark TEXT DEFAULT 'SPY',
                    risk_tolerance TEXT DEFAULT 'moderate',
                    rebalance_schedule TEXT DEFAULT 'manual',
                    created TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id TEXT REFERENCES portfolios(id) ON DELETE CASCADE,
                    ticker TEXT NOT NULL,
                    shares REAL NOT NULL,
                    avg_cost REAL NOT NULL,
                    added_date TEXT,
                    tags TEXT,
                    target_weight REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id TEXT REFERENCES portfolios(id) ON DELETE CASCADE,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    shares REAL NOT NULL,
                    price REAL NOT NULL,
                    date TEXT NOT NULL,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS nav_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id TEXT REFERENCES portfolios(id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    total_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    benchmark_value REAL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id TEXT REFERENCES portfolios(id) ON DELETE CASCADE,
                    ticker TEXT,
                    type TEXT NOT NULL,
                    message TEXT,
                    created TEXT,
                    dismissed INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);
                CREATE INDEX IF NOT EXISTS idx_trades_portfolio ON trades(portfolio_id);
                CREATE INDEX IF NOT EXISTS idx_trades_portfolio_ticker ON trades(portfolio_id, ticker);
                CREATE INDEX IF NOT EXISTS idx_nav_portfolio ON nav_snapshots(portfolio_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_nav_portfolio_date ON nav_snapshots(portfolio_id, date);
                CREATE INDEX IF NOT EXISTS idx_alerts_portfolio ON alerts(portfolio_id);
                """
            )

    # ── Portfolios ──────────────────────────────────────────────────────────────

    def get_portfolios(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM portfolios ORDER BY created DESC").fetchall()
            for row in rows:
                row["positions"] = self.get_positions(row["id"])
            return rows

    def get_portfolio(self, pid: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM portfolios WHERE id = ?", (pid,)).fetchone()
            if not row:
                return None
            row["positions"] = self.get_positions(pid)
            return row

    def create_portfolio(self, data: dict) -> dict:
        pid = data.get("id") or str(uuid.uuid4())[:8]
        created = data.get("created") or datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO portfolios (id, name, capital, strategy, benchmark,
                                       risk_tolerance, rebalance_schedule, created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    data["name"],
                    float(data.get("capital", 10000.0)),
                    data.get("strategy", "custom"),
                    data.get("benchmark", "SPY"),
                    data.get("risk_tolerance", "moderate"),
                    data.get("rebalance_schedule", "manual"),
                    created,
                ),
            )
        # Seed positions if provided
        for pos in data.get("positions", []):
            self.add_position(pid, pos)
        return self.get_portfolio(pid)

    def delete_portfolio(self, pid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM portfolios WHERE id = ?", (pid,))
            return cur.rowcount > 0

    def update_portfolio_capital(self, pid: str, capital: float) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE portfolios SET capital = ? WHERE id = ?",
                (float(capital), pid),
            )
            return cur.rowcount > 0

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self, pid: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE portfolio_id = ? ORDER BY id",
                (pid,),
            ).fetchall()
            for row in rows:
                if row.get("tags"):
                    try:
                        row["tags"] = json.loads(row["tags"])
                    except json.JSONDecodeError:
                        pass
            return rows

    def add_position(self, pid: str, position: dict) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO positions
                (portfolio_id, ticker, shares, avg_cost, added_date, tags,
                 target_weight, stop_loss, take_profit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    position["ticker"].upper(),
                    float(position["shares"]),
                    float(position["avg_cost"]),
                    position.get("added_date") or datetime.now().strftime("%Y-%m-%d"),
                    json.dumps(position.get("tags", [])) if position.get("tags") else None,
                    position.get("target_weight"),
                    position.get("stop_loss"),
                    position.get("take_profit"),
                    position.get("notes"),
                ),
            )
            position["id"] = cur.lastrowid
            position["portfolio_id"] = pid
            return position

    def remove_position(self, pid: str, ticker: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM positions WHERE portfolio_id = ? AND ticker = ?",
                (pid, ticker.upper()),
            )
            return cur.rowcount > 0

    def update_position(self, pid: str, ticker: str, updates: dict) -> bool:
        allowed = {"shares", "avg_cost", "tags", "target_weight", "stop_loss", "take_profit", "notes"}
        fields = []
        values = []
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k == "tags":
                v = json.dumps(v) if v else None
            fields.append(f"{k} = ?")
            values.append(v)
        if not fields:
            return False
        values.extend([pid, ticker.upper()])
        with self._conn() as conn:
            cur = conn.execute(
                f"UPDATE positions SET {', '.join(fields)} WHERE portfolio_id = ? AND ticker = ?",
                values,
            )
            return cur.rowcount > 0

    # ── Trades ──────────────────────────────────────────────────────────────────

    def record_trade(self, pid: str, trade: dict) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO trades (portfolio_id, ticker, action, shares, price, date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    trade["ticker"].upper(),
                    trade["action"],
                    float(trade["shares"]),
                    float(trade["price"]),
                    trade.get("date") or datetime.now().strftime("%Y-%m-%d"),
                    trade.get("notes", ""),
                ),
            )
            trade["id"] = cur.lastrowid
            trade["portfolio_id"] = pid
            return trade

    def get_trades(self, pid: str, ticker: Optional[str] = None) -> list:
        with self._conn() as conn:
            if ticker:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE portfolio_id = ? AND ticker = ? ORDER BY date DESC, id DESC",
                    (pid, ticker.upper()),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE portfolio_id = ? ORDER BY date DESC, id DESC",
                    (pid,),
                ).fetchall()
            return rows

    # ── NAV snapshots ─────────────────────────────────────────────────────────

    def record_nav(self, pid: str, date: str, total_value: float, cash: float, benchmark_value: Optional[float] = None) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO nav_snapshots
                (portfolio_id, date, total_value, cash, benchmark_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pid, date, float(total_value), float(cash), benchmark_value),
            )
            return cur.rowcount > 0

    def get_nav_history(self, pid: str, days: int = 365) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM nav_snapshots
                WHERE portfolio_id = ?
                  AND date >= date('now', '-{} days')
                ORDER BY date ASC
                """.format(days),
                (pid,),
            ).fetchall()
            return rows

    # ── Alerts ──────────────────────────────────────────────────────────────────

    def add_alert(self, pid: str, alert: dict) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO alerts (portfolio_id, ticker, type, message, created, dismissed)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    pid,
                    alert.get("ticker", "").upper() if alert.get("ticker") else None,
                    alert["type"],
                    alert.get("message", ""),
                    alert.get("created") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            alert["id"] = cur.lastrowid
            alert["portfolio_id"] = pid
            alert["dismissed"] = 0
            return alert

    def get_alerts(self, pid: str, dismissed: bool = False) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE portfolio_id = ? AND dismissed = ? ORDER BY created DESC",
                (pid, 1 if dismissed else 0),
            ).fetchall()
            return rows

    def dismiss_alert(self, aid: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE alerts SET dismissed = 1 WHERE id = ?",
                (aid,),
            )
            return cur.rowcount > 0
