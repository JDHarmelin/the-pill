"""
JSON-backed data store. Replaces SQLite db.Database.
All data lives in data/*.json files under version control.
"""

import os
import json
import uuid
import threading
from datetime import datetime
from typing import Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _path(name: str) -> str:
    return os.path.join(_DATA_DIR, name)


def _load(name: str, default=None):
    try:
        with open(_path(name), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _save(name: str, data):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_path(name), "w") as f:
        json.dump(data, f, indent=2, default=str)


class JsonStore:
    """Drop-in replacement for db.Database using JSON files."""

    def __init__(self):
        self._lock = threading.RLock()
        self._ensure_files()

    def _ensure_files(self):
        if not os.path.exists(_path("portfolios.json")):
            _save("portfolios.json", [])
        if not os.path.exists(_path("trades.json")):
            _save("trades.json", {})
        if not os.path.exists(_path("nav_snapshots.json")):
            _save("nav_snapshots.json", {})
        if not os.path.exists(_path("alerts.json")):
            _save("alerts.json", {})
        if not os.path.exists(_path("watchlists.json")):
            _save("watchlists.json", {"watchlists": [], "items": {}})

    # ── Portfolios ─────────────────────────────────────────────────────────────

    def get_portfolios(self) -> list:
        with self._lock:
            return _load("portfolios.json", [])

    def get_portfolio(self, pid: str) -> Optional[dict]:
        with self._lock:
            for p in _load("portfolios.json", []):
                if p["id"] == pid:
                    return p
            return None

    def create_portfolio(self, data: dict) -> dict:
        pid = data.get("id") or str(uuid.uuid4())[:8]
        created = data.get("created") or datetime.now().strftime("%Y-%m-%d")
        portfolio = {
            "id": pid,
            "name": data["name"],
            "capital": float(data.get("capital", 10000.0)),
            "strategy": data.get("strategy", "custom"),
            "benchmark": data.get("benchmark", "SPY"),
            "risk_tolerance": data.get("risk_tolerance", "moderate"),
            "rebalance_schedule": data.get("rebalance_schedule", "manual"),
            "created": created,
            "positions": [],
        }
        for pos in data.get("positions", []):
            portfolio["positions"].append({
                "ticker": pos["ticker"].upper(),
                "shares": round(float(pos["shares"]), 6),
                "avg_cost": round(float(pos["avg_cost"]), 6),
                "added_date": pos.get("added_date", created),
                "tags": pos.get("tags"),
                "target_weight": pos.get("target_weight"),
                "stop_loss": pos.get("stop_loss"),
                "take_profit": pos.get("take_profit"),
                "notes": pos.get("notes"),
            })
        with self._lock:
            all_p = _load("portfolios.json", [])
            all_p.append(portfolio)
            _save("portfolios.json", all_p)
        return portfolio

    def delete_portfolio(self, pid: str) -> bool:
        with self._lock:
            all_p = _load("portfolios.json", [])
            before = len(all_p)
            all_p = [p for p in all_p if p["id"] != pid]
            if len(all_p) == before:
                return False
            _save("portfolios.json", all_p)
            # Cascade delete related data
            trades = _load("trades.json", {})
            trades.pop(pid, None)
            _save("trades.json", trades)
            nav = _load("nav_snapshots.json", {})
            nav.pop(pid, None)
            _save("nav_snapshots.json", nav)
            alerts = _load("alerts.json", {})
            alerts.pop(pid, None)
            _save("alerts.json", alerts)
            return True

    def update_portfolio_capital(self, pid: str, capital: float) -> bool:
        with self._lock:
            all_p = _load("portfolios.json", [])
            for p in all_p:
                if p["id"] == pid:
                    p["capital"] = float(capital)
                    _save("portfolios.json", all_p)
                    return True
            return False

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self, pid: str) -> list:
        p = self.get_portfolio(pid)
        return p["positions"] if p else []

    def add_position(self, pid: str, position: dict) -> dict:
        pos = {
            "ticker": position["ticker"].upper(),
            "shares": round(float(position["shares"]), 6),
            "avg_cost": round(float(position["avg_cost"]), 6),
            "added_date": position.get("added_date") or datetime.now().strftime("%Y-%m-%d"),
            "tags": position.get("tags"),
            "target_weight": position.get("target_weight"),
            "stop_loss": position.get("stop_loss"),
            "take_profit": position.get("take_profit"),
            "notes": position.get("notes"),
        }
        with self._lock:
            all_p = _load("portfolios.json", [])
            for p in all_p:
                if p["id"] == pid:
                    p["positions"].append(pos)
                    _save("portfolios.json", all_p)
                    return pos
        return pos

    def remove_position(self, pid: str, ticker: str) -> bool:
        with self._lock:
            all_p = _load("portfolios.json", [])
            for p in all_p:
                if p["id"] == pid:
                    before = len(p["positions"])
                    p["positions"] = [pos for pos in p["positions"] if pos["ticker"] != ticker.upper()]
                    if len(p["positions"]) < before:
                        _save("portfolios.json", all_p)
                        return True
            return False

    def update_position(self, pid: str, ticker: str, updates: dict) -> bool:
        allowed = {"shares", "avg_cost", "tags", "target_weight", "stop_loss", "take_profit", "notes"}
        with self._lock:
            all_p = _load("portfolios.json", [])
            for p in all_p:
                if p["id"] == pid:
                    for pos in p["positions"]:
                        if pos["ticker"] == ticker.upper():
                            for k, v in updates.items():
                                if k in allowed:
                                    pos[k] = v
                            _save("portfolios.json", all_p)
                            return True
            return False

    # ── Trades ─────────────────────────────────────────────────────────────────

    def record_trade(self, pid: str, trade: dict) -> dict:
        trade = {
            "id": int(datetime.now().timestamp() * 1000),
            "portfolio_id": pid,
            "ticker": trade["ticker"].upper(),
            "action": trade["action"],
            "shares": float(trade["shares"]),
            "price": float(trade["price"]),
            "date": trade.get("date") or datetime.now().strftime("%Y-%m-%d"),
            "notes": trade.get("notes", ""),
        }
        with self._lock:
            trades = _load("trades.json", {})
            trades.setdefault(pid, []).insert(0, trade)
            _save("trades.json", trades)
        return trade

    def get_trades(self, pid: str, ticker: Optional[str] = None) -> list:
        with self._lock:
            trades = _load("trades.json", {}).get(pid, [])
            if ticker:
                ticker = ticker.upper()
                return [t for t in trades if t["ticker"] == ticker]
            return list(trades)

    # ── NAV snapshots ─────────────────────────────────────────────────────────

    def record_nav(self, pid: str, date: str, total_value: float, cash: float, benchmark_value: Optional[float] = None) -> bool:
        with self._lock:
            nav = _load("nav_snapshots.json", {})
            entries = nav.setdefault(pid, [])
            # Replace existing entry for this date
            entries = [e for e in entries if e["date"] != date]
            entries.append({
                "date": date,
                "total_value": float(total_value),
                "cash": float(cash),
                "benchmark_value": benchmark_value,
            })
            entries.sort(key=lambda e: e["date"])
            nav[pid] = entries
            _save("nav_snapshots.json", nav)
        return True

    def get_nav_history(self, pid: str, days: int = 365) -> list:
        with self._lock:
            entries = _load("nav_snapshots.json", {}).get(pid, [])
            return entries[-days:] if days else entries

    # ── Alerts ─────────────────────────────────────────────────────────────────

    def add_alert(self, pid: str, alert: dict) -> dict:
        alert = {
            "id": int(datetime.now().timestamp() * 1000),
            "portfolio_id": pid,
            "ticker": alert.get("ticker", "").upper() if alert.get("ticker") else None,
            "type": alert["type"],
            "message": alert.get("message", ""),
            "created": alert.get("created") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dismissed": 0,
        }
        with self._lock:
            alerts = _load("alerts.json", {})
            alerts.setdefault(pid, []).insert(0, alert)
            _save("alerts.json", alerts)
        return alert

    def get_alerts(self, pid: str, dismissed: bool = False) -> list:
        with self._lock:
            alerts = _load("alerts.json", {}).get(pid, [])
            flag = 1 if dismissed else 0
            return [a for a in alerts if a.get("dismissed", 0) == flag]

    def dismiss_alert(self, aid: int) -> bool:
        with self._lock:
            alerts = _load("alerts.json", {})
            for pid, items in alerts.items():
                for a in items:
                    if a["id"] == aid:
                        a["dismissed"] = 1
                        _save("alerts.json", alerts)
                        return True
            return False

    # ── Watchlists ─────────────────────────────────────────────────────────────

    def get_watchlists(self) -> list:
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            result = []
            for w in data.get("watchlists", []):
                w = dict(w)
                w["items"] = data.get("items", {}).get(w["id"], [])
                result.append(w)
            return result

    def get_watchlist(self, wid: str) -> Optional[dict]:
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            for w in data.get("watchlists", []):
                if w["id"] == wid:
                    w = dict(w)
                    w["items"] = data.get("items", {}).get(wid, [])
                    return w
            return None

    def create_watchlist(self, name: str) -> dict:
        wid = str(uuid.uuid4())[:8]
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        w = {"id": wid, "name": name, "created": created}
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            data["watchlists"].append(w)
            _save("watchlists.json", data)
        return {**w, "items": []}

    def delete_watchlist(self, wid: str) -> bool:
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            before = len(data["watchlists"])
            data["watchlists"] = [w for w in data["watchlists"] if w["id"] != wid]
            data["items"].pop(wid, None)
            if len(data["watchlists"]) < before:
                _save("watchlists.json", data)
                return True
            return False

    def get_watchlist_items(self, wid: str) -> list:
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            return data.get("items", {}).get(wid, [])

    def add_watchlist_item(self, wid: str, ticker: str, notes: str = "") -> dict:
        item = {
            "id": int(datetime.now().timestamp() * 1000),
            "watchlist_id": wid,
            "ticker": ticker.upper(),
            "notes": notes,
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            items = data.setdefault("items", {}).setdefault(wid, [])
            # Prevent duplicates
            if any(i["ticker"] == item["ticker"] for i in items):
                return {"watchlist_id": wid, "ticker": item["ticker"], "status": "already_exists"}
            items.append(item)
            _save("watchlists.json", data)
        return {"watchlist_id": wid, "ticker": item["ticker"], "status": "added"}

    def remove_watchlist_item(self, wid: str, ticker: str) -> bool:
        with self._lock:
            data = _load("watchlists.json", {"watchlists": [], "items": {}})
            items = data.get("items", {}).get(wid, [])
            before = len(items)
            items = [i for i in items if i["ticker"] != ticker.upper()]
            if len(items) < before:
                data["items"][wid] = items
                _save("watchlists.json", data)
                return True
            return False
