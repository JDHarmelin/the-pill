"""
Portfolio Manager — Paper trading & watchlist tracker.
Data persists in SQLite via db.Database.
"""

import os
import time
import json
from copy import deepcopy
from datetime import datetime
import yfinance as yf
import pandas as pd

from db import Database

# ── Load default portfolios from file (fast, no seeding delay) ───────────────
_DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "portfolios.json")

def _load_default_portfolios():
    try:
        with open(_DEFAULTS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return []

_DEFAULT_PORTFOLIOS = _load_default_portfolios()

# ── Default sector portfolios ($10K each, equal-weight) ──────────────────────

_DEFAULT_PORTFOLIOS = [
    {
        "id": "space-satellites", "name": "Space & Satellites", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "ASTS", "shares": 40.0, "avg_cost": 25.00, "added_date": "2025-01-01"},
            {"ticker": "RKLB", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "IRDM", "shares": 30.0, "avg_cost": 33.33, "added_date": "2025-01-01"},
            {"ticker": "GSAT", "shares": 175.0, "avg_cost": 5.71, "added_date": "2025-01-01"},
            {"ticker": "PL", "shares": 250.0, "avg_cost": 4.00, "added_date": "2025-01-01"},
            {"ticker": "GRMN", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "SATS", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "LHX", "shares": 4.5, "avg_cost": 222.22, "added_date": "2025-01-01"},
            {"ticker": "LMT", "shares": 2.0, "avg_cost": 500.00, "added_date": "2025-01-01"},
            {"ticker": "UFO", "shares": 33.0, "avg_cost": 30.30, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "defense-military", "name": "Defense & Military", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "LMT", "shares": 2.0, "avg_cost": 500.00, "added_date": "2025-01-01"},
            {"ticker": "NOC", "shares": 2.0, "avg_cost": 500.00, "added_date": "2025-01-01"},
            {"ticker": "RTX", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "GD", "shares": 3.5, "avg_cost": 285.71, "added_date": "2025-01-01"},
            {"ticker": "BA", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "LHX", "shares": 4.5, "avg_cost": 222.22, "added_date": "2025-01-01"},
            {"ticker": "LDOS", "shares": 6.5, "avg_cost": 153.85, "added_date": "2025-01-01"},
            {"ticker": "HII", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "KTOS", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "ITA", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "quantum", "name": "Quantum Computing", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "IONQ", "shares": 25.0, "avg_cost": 40.00, "added_date": "2025-01-01"},
            {"ticker": "RGTI", "shares": 70.0, "avg_cost": 14.29, "added_date": "2025-01-01"},
            {"ticker": "QBTS", "shares": 100.0, "avg_cost": 10.00, "added_date": "2025-01-01"},
            {"ticker": "IBM", "shares": 4.0, "avg_cost": 250.00, "added_date": "2025-01-01"},
            {"ticker": "GOOGL", "shares": 5.5, "avg_cost": 181.82, "added_date": "2025-01-01"},
            {"ticker": "MSFT", "shares": 2.3, "avg_cost": 434.78, "added_date": "2025-01-01"},
            {"ticker": "NVDA", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
            {"ticker": "INTC", "shares": 45.0, "avg_cost": 22.22, "added_date": "2025-01-01"},
            {"ticker": "HON", "shares": 4.5, "avg_cost": 222.22, "added_date": "2025-01-01"},
            {"ticker": "QTUM", "shares": 12.0, "avg_cost": 83.33, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "healthcare", "name": "Healthcare Large Cap", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "LLY", "shares": 1.2, "avg_cost": 833.33, "added_date": "2025-01-01"},
            {"ticker": "JNJ", "shares": 6.0, "avg_cost": 166.67, "added_date": "2025-01-01"},
            {"ticker": "UNH", "shares": 1.8, "avg_cost": 555.56, "added_date": "2025-01-01"},
            {"ticker": "ABBV", "shares": 5.5, "avg_cost": 181.82, "added_date": "2025-01-01"},
            {"ticker": "MRK", "shares": 9.0, "avg_cost": 111.11, "added_date": "2025-01-01"},
            {"ticker": "PFE", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "ABT", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "MDT", "shares": 11.0, "avg_cost": 90.91, "added_date": "2025-01-01"},
            {"ticker": "TMO", "shares": 1.8, "avg_cost": 555.56, "added_date": "2025-01-01"},
            {"ticker": "MCK", "shares": 1.5, "avg_cost": 666.67, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "major-banks", "name": "Major Banks", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "JPM", "shares": 4.0, "avg_cost": 250.00, "added_date": "2025-01-01"},
            {"ticker": "BAC", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
            {"ticker": "WFC", "shares": 14.0, "avg_cost": 71.43, "added_date": "2025-01-01"},
            {"ticker": "C", "shares": 14.0, "avg_cost": 71.43, "added_date": "2025-01-01"},
            {"ticker": "GS", "shares": 1.8, "avg_cost": 555.56, "added_date": "2025-01-01"},
            {"ticker": "MS", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "USB", "shares": 20.0, "avg_cost": 50.00, "added_date": "2025-01-01"},
            {"ticker": "PNC", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "TFC", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
            {"ticker": "COF", "shares": 5.5, "avg_cost": 181.82, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "fintech", "name": "Fintech Leaders", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "V", "shares": 3.0, "avg_cost": 333.33, "added_date": "2025-01-01"},
            {"ticker": "MA", "shares": 1.8, "avg_cost": 555.56, "added_date": "2025-01-01"},
            {"ticker": "PYPL", "shares": 12.0, "avg_cost": 83.33, "added_date": "2025-01-01"},
            {"ticker": "XYZ", "shares": 12.0, "avg_cost": 83.33, "added_date": "2025-01-01"},
            {"ticker": "FISV", "shares": 4.5, "avg_cost": 222.22, "added_date": "2025-01-01"},
            {"ticker": "GPN", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "INTU", "shares": 1.5, "avg_cost": 666.67, "added_date": "2025-01-01"},
            {"ticker": "ADYEY", "shares": 70.0, "avg_cost": 14.29, "added_date": "2025-01-01"},
            {"ticker": "NU", "shares": 70.0, "avg_cost": 14.29, "added_date": "2025-01-01"},
            {"ticker": "COIN", "shares": 4.0, "avg_cost": 250.00, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "ai-hardware", "name": "AI Hardware & Infrastructure", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "NVDA", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
            {"ticker": "AMD", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "AVGO", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "TSM", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "ASML", "shares": 1.3, "avg_cost": 769.23, "added_date": "2025-01-01"},
            {"ticker": "AMAT", "shares": 5.5, "avg_cost": 181.82, "added_date": "2025-01-01"},
            {"ticker": "MU", "shares": 9.0, "avg_cost": 111.11, "added_date": "2025-01-01"},
            {"ticker": "ANET", "shares": 10.0, "avg_cost": 100.00, "added_date": "2025-01-01"},
            {"ticker": "VRT", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "SMH", "shares": 3.5, "avg_cost": 285.71, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "real-estate", "name": "Real Estate & REITs", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "VNQ", "shares": 11.0, "avg_cost": 90.91, "added_date": "2025-01-01"},
            {"ticker": "XLRE", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
            {"ticker": "PLD", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "AMT", "shares": 4.5, "avg_cost": 222.22, "added_date": "2025-01-01"},
            {"ticker": "EQIX", "shares": 1.1, "avg_cost": 909.09, "added_date": "2025-01-01"},
            {"ticker": "DLR", "shares": 6.0, "avg_cost": 166.67, "added_date": "2025-01-01"},
            {"ticker": "O", "shares": 17.0, "avg_cost": 58.82, "added_date": "2025-01-01"},
            {"ticker": "WELL", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
            {"ticker": "SPG", "shares": 6.0, "avg_cost": 166.67, "added_date": "2025-01-01"},
            {"ticker": "SRVR", "shares": 28.0, "avg_cost": 35.71, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "nuclear-uranium", "name": "Nuclear & Uranium", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "CEG", "shares": 3.0, "avg_cost": 333.33, "added_date": "2025-01-01"},
            {"ticker": "CCJ", "shares": 18.0, "avg_cost": 55.56, "added_date": "2025-01-01"},
            {"ticker": "BWXT", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "LEU", "shares": 12.0, "avg_cost": 83.33, "added_date": "2025-01-01"},
            {"ticker": "SMR", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "OKLO", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "UEC", "shares": 125.0, "avg_cost": 8.00, "added_date": "2025-01-01"},
            {"ticker": "UUUU", "shares": 125.0, "avg_cost": 8.00, "added_date": "2025-01-01"},
            {"ticker": "URA", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "URNM", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "dividends", "name": "Dividend Beasts", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "SCHD", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "VYM", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "SPYD", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
            {"ticker": "JEPI", "shares": 17.0, "avg_cost": 58.82, "added_date": "2025-01-01"},
            {"ticker": "O", "shares": 17.0, "avg_cost": 58.82, "added_date": "2025-01-01"},
            {"ticker": "MO", "shares": 17.0, "avg_cost": 58.82, "added_date": "2025-01-01"},
            {"ticker": "VZ", "shares": 22.0, "avg_cost": 45.45, "added_date": "2025-01-01"},
            {"ticker": "T", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "EPD", "shares": 33.0, "avg_cost": 30.30, "added_date": "2025-01-01"},
            {"ticker": "ET", "shares": 55.0, "avg_cost": 18.18, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "bigbox-retail", "name": "Big Box & Home Improvement", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "HD", "shares": 2.5, "avg_cost": 400.00, "added_date": "2025-01-01"},
            {"ticker": "LOW", "shares": 3.5, "avg_cost": 285.71, "added_date": "2025-01-01"},
            {"ticker": "COST", "shares": 1.0, "avg_cost": 1000.00, "added_date": "2025-01-01"},
            {"ticker": "WMT", "shares": 11.0, "avg_cost": 90.91, "added_date": "2025-01-01"},
            {"ticker": "TGT", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
            {"ticker": "TSCO", "shares": 3.5, "avg_cost": 285.71, "added_date": "2025-01-01"},
            {"ticker": "FND", "shares": 9.0, "avg_cost": 111.11, "added_date": "2025-01-01"},
            {"ticker": "SHW", "shares": 2.5, "avg_cost": 400.00, "added_date": "2025-01-01"},
            {"ticker": "FAST", "shares": 12.0, "avg_cost": 83.33, "added_date": "2025-01-01"},
            {"ticker": "GWW", "shares": 1.0, "avg_cost": 1000.00, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "defense-adjacent", "name": "Defense Adjacents", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "BAH", "shares": 6.0, "avg_cost": 166.67, "added_date": "2025-01-01"},
            {"ticker": "CACI", "shares": 2.2, "avg_cost": 454.55, "added_date": "2025-01-01"},
            {"ticker": "SAIC", "shares": 7.0, "avg_cost": 142.86, "added_date": "2025-01-01"},
            {"ticker": "LDOS", "shares": 6.5, "avg_cost": 153.85, "added_date": "2025-01-01"},
            {"ticker": "AVAV", "shares": 5.0, "avg_cost": 200.00, "added_date": "2025-01-01"},
            {"ticker": "KTOS", "shares": 35.0, "avg_cost": 28.57, "added_date": "2025-01-01"},
            {"ticker": "VSAT", "shares": 25.0, "avg_cost": 40.00, "added_date": "2025-01-01"},
            {"ticker": "TDY", "shares": 2.0, "avg_cost": 500.00, "added_date": "2025-01-01"},
            {"ticker": "PLTR", "shares": 8.0, "avg_cost": 125.00, "added_date": "2025-01-01"},
            {"ticker": "CIBR", "shares": 16.0, "avg_cost": 62.50, "added_date": "2025-01-01"},
        ],
    },
    {
        "id": "mag7", "name": "MAG 7", "capital": 10000.0, "created": "2025-01-01",
        "positions": [
            {"ticker": "AAPL", "shares": 5.18, "avg_cost": 275.00, "added_date": "2025-01-01"},
            {"ticker": "MSFT", "shares": 3.14, "avg_cost": 455.00, "added_date": "2025-01-01"},
            {"ticker": "GOOGL", "shares": 5.91, "avg_cost": 192.00, "added_date": "2025-01-01"},
            {"ticker": "AMZN", "shares": 6.02, "avg_cost": 237.00, "added_date": "2025-01-01"},
            {"ticker": "NVDA", "shares": 7.77, "avg_cost": 138.00, "added_date": "2025-01-01"},
            {"ticker": "META", "shares": 2.87, "avg_cost": 593.00, "added_date": "2025-01-01"},
            {"ticker": "TSLA", "shares": 6.88, "avg_cost": 391.00, "added_date": "2025-01-01"},
        ],
    },
]


class PortfolioManager:
    def __init__(self):
        self.db = Database()
        self._seed_defaults()
        self._positions_cache = {}
        self._risk_cache = {}
        self._chart_cache = {}

    def _seed_defaults(self):
        existing = {p["id"] for p in self.db.get_portfolios()}
        for p in _DEFAULT_PORTFOLIOS:
            if p["id"] not in existing:
                self.db.create_portfolio(p)

    def _invalidate_runtime_caches(self, pid):
        self._positions_cache = {
            key: value
            for key, value in self._positions_cache.items()
            if key[0] != pid
        }
        self._risk_cache = {
            key: value
            for key, value in self._risk_cache.items()
            if key[0] != pid
        }
        self._chart_cache = {
            key: value
            for key, value in self._chart_cache.items()
            if key[0] != pid
        }

    def _portfolio_signature(self, portfolio):
        import json as _json
        return _json.dumps(
            {
                "capital": round(float(portfolio.get("capital", 0)), 6),
                "positions": [
                    {
                        "ticker": pos["ticker"],
                        "shares": round(float(pos["shares"]), 6),
                        "avg_cost": round(float(pos["avg_cost"]), 6),
                    }
                    for pos in portfolio.get("positions", [])
                ],
            },
            sort_keys=True,
        )

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def get_all(self):
        return self.db.get_portfolios()

    def get_portfolio(self, portfolio_id):
        return self.db.get_portfolio(portfolio_id)

    def create(self, name, capital=10000.0):
        return self.db.create_portfolio({"name": name, "capital": float(capital)})

    def delete(self, portfolio_id):
        self.db.delete_portfolio(portfolio_id)

    def update_capital(self, portfolio_id, capital):
        return self.db.update_portfolio_capital(portfolio_id, capital)

    def add_position(self, portfolio_id, ticker, shares, avg_cost):
        ticker = ticker.upper()
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return None

        # Check for existing position
        for pos in portfolio.get("positions", []):
            if pos["ticker"] == ticker:
                total_shares = float(pos["shares"]) + float(shares)
                total_cost = float(pos["shares"]) * float(pos["avg_cost"]) + float(shares) * float(avg_cost)
                new_avg = round(total_cost / total_shares, 6) if total_shares else float(pos["avg_cost"])
                self.db.update_position(
                    portfolio_id,
                    ticker,
                    {"shares": round(total_shares, 6), "avg_cost": new_avg},
                )
                self._invalidate_runtime_caches(portfolio_id)
                # Record trade
                self.record_trade(portfolio_id, ticker, "add", float(shares), float(avg_cost))
                return {**pos, "shares": round(total_shares, 6), "avg_cost": new_avg}

        # New position
        pos = {
            "ticker": ticker,
            "shares": round(float(shares), 6),
            "avg_cost": round(float(avg_cost), 6),
            "added_date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.db.add_position(portfolio_id, pos)
        self._invalidate_runtime_caches(portfolio_id)
        # Record trade
        self.record_trade(portfolio_id, ticker, "buy", float(shares), float(avg_cost))
        return pos

    def remove_position(self, portfolio_id, ticker):
        ticker = ticker.upper()
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False
        for pos in portfolio.get("positions", []):
            if pos["ticker"] == ticker:
                self.record_trade(
                    portfolio_id,
                    ticker,
                    "sell",
                    float(pos["shares"]),
                    float(pos.get("avg_cost", 0)),
                )
                break
        ok = self.db.remove_position(portfolio_id, ticker)
        if ok:
            self._invalidate_runtime_caches(portfolio_id)
        return ok

    def set_positions(self, portfolio_id, new_positions):
        """Atomically replace all positions (used by rebalance)."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False

        # Remove all current positions
        for pos in portfolio.get("positions", []):
            self.db.remove_position(portfolio_id, pos["ticker"])

        # Add new positions
        for pos in new_positions:
            if float(pos.get("shares", 0)) > 0:
                self.db.add_position(
                    portfolio_id,
                    {
                        "ticker": str(pos["ticker"]).upper(),
                        "shares": round(float(pos["shares"]), 6),
                        "avg_cost": round(float(pos["avg_cost"]), 6),
                        "added_date": datetime.now().strftime("%Y-%m-%d"),
                    },
                )
        self._invalidate_runtime_caches(portfolio_id)
        return True

    # ── Live data ─────────────────────────────────────────────────────────────

    def get_positions_with_returns(self, portfolio_id):
        """Return positions enriched with current price and gain/loss."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return [], 0.0

        now = time.time()
        cache_key = (portfolio_id, self._portfolio_signature(portfolio))
        cached = self._positions_cache.get(cache_key)
        if cached and (now - cached["timestamp"]) < 300:
            return deepcopy(cached["value"])

        positions = portfolio.get("positions", [])
        if not positions:
            return [], portfolio.get("capital", 0.0)

        tickers = [p["ticker"] for p in positions]
        prices = {}

        # 1. Try price cache first (instant)
        try:
            from tools.price_cache import get_price_cache
            cache = get_price_cache()
            for t in tickers:
                cp = cache.get_price(t)
                if cp:
                    prices[t] = cp
        except Exception:
            pass

        # 2. Fallback: batch download from yfinance for cache misses
        missing = [t for t in tickers if t not in prices]
        if missing:
            try:
                raw = yf.download(missing, period="5d", interval="1d",
                                  progress=False, auto_adjust=True, threads=False)["Close"]
                if isinstance(raw, pd.Series):
                    raw = raw.to_frame(name=missing[0])
                for t in missing:
                    if t in raw.columns:
                        series = raw[t].dropna()
                        if not series.empty:
                            prices[t] = float(series.iloc[-1])
            except Exception:
                pass

        # 3. Final fallback: Finnhub for any still missing
        still_missing = [t for t in tickers if t not in prices]
        if still_missing:
            try:
                from tools.finnhub_fetcher import FinnhubFetcher
                fh = FinnhubFetcher()
                for t in still_missing:
                    try:
                        quote = fh.get_realtime_quote(t)
                        if quote.get("price") and quote["price"] > 0:
                            prices[t] = float(quote["price"])
                    except Exception:
                        pass
            except Exception:
                pass

        results = []
        total_cost = 0.0
        for pos in positions:
            cost = float(pos["shares"]) * float(pos["avg_cost"])
            total_cost += cost
            cp = prices.get(pos["ticker"])
            if cp:
                cv = float(pos["shares"]) * cp
                gain = cv - cost
                gain_pct = (gain / cost * 100) if cost else 0
                results.append({
                    **pos,
                    "current_price": round(cp, 6),
                    "current_value": round(cv, 2),
                    "cost_basis": round(cost, 2),
                    "gain": round(gain, 2),
                    "gain_pct": round(gain_pct, 2),
                })
            else:
                results.append({**pos, "current_price": None,
                                "current_value": None, "cost_basis": round(cost, 2),
                                "gain": None, "gain_pct": None})

        cash = round(portfolio.get("capital", 0.0) - total_cost, 2)

        out = (results, cash)
        self._positions_cache = {
            key: value
            for key, value in self._positions_cache.items()
            if key[0] != portfolio_id
        }
        self._positions_cache[cache_key] = {"value": deepcopy(out), "timestamp": time.time()}
        return out

    def get_summary(self, portfolio_id, positions=None, cash=None):
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        if positions is None or cash is None:
            positions, cash = self.get_positions_with_returns(portfolio_id)
        position_value = sum(p["current_value"] or p["cost_basis"] for p in positions)
        total_value = max(0.0, cash) + position_value
        total_gain = total_value - portfolio.get("capital", 0.0)
        total_gain_pct = (total_gain / portfolio["capital"] * 100) if portfolio.get("capital") else 0

        # Calculate Risk Metrics
        risk = self.calculate_risk_metrics(portfolio_id)

        return {
            "total_value": round(total_value, 2),
            "cash": round(max(0.0, cash), 2),
            "position_value": round(position_value, 2),
            "total_gain": round(total_gain, 2),
            "total_gain_pct": round(total_gain_pct, 2),
            "risk": risk
        }

    def calculate_risk_metrics(self, portfolio_id):
        """Calculate Volatility, Beta, and Sharpe Ratio using 1Y of historical data."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio or not portfolio.get("positions"):
            return {"volatility": 0, "beta": 0, "sharpe": 0}

        cache_key = (portfolio_id, self._portfolio_signature(portfolio))
        cached = self._risk_cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < 900:
            return deepcopy(cached["value"])

        tickers = [p["ticker"] for p in portfolio["positions"]]
        benchmark = portfolio.get("benchmark", "SPY")
        all_tickers = tickers + [benchmark]

        try:
            # Get 1 year of daily data
            data = yf.download(all_tickers, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)["Close"]
            if isinstance(data, pd.Series):
                data = data.to_frame(name=tickers[0])

            returns = data.pct_change().dropna()

            # Filter to only tickers that actually downloaded successfully
            available_tickers = [t for t in tickers if t in returns.columns]
            if not available_tickers or benchmark not in returns.columns:
                risk = {"volatility": 0, "beta": 0, "sharpe": 0}
                self._risk_cache[cache_key] = {"value": deepcopy(risk), "timestamp": time.time()}
                return risk

            # Recalculate weights using only available tickers
            available_positions = [p for p in portfolio["positions"] if p["ticker"] in available_tickers]

            # Calculate portfolio daily returns based on weights
            weights = []
            total_cost = sum(float(p["shares"]) * float(p["avg_cost"]) for p in available_positions)
            for p in available_positions:
                weight = (float(p["shares"]) * float(p["avg_cost"])) / total_cost if total_cost else 0
                weights.append(weight)

            port_returns = (returns[available_tickers] * weights).sum(axis=1)
            bench_returns = returns[benchmark]

            # 1. Volatility (Annualized)
            vol = port_returns.std() * (252**0.5) * 100

            # 2. Beta
            covariance = port_returns.cov(bench_returns)
            variance = bench_returns.var()
            beta = covariance / variance if variance else 0

            # 3. Sharpe Ratio (Risk-free rate assumed at 4%)
            rf = 0.04
            excess_return = port_returns.mean() * 252 - rf
            sharpe = excess_return / (port_returns.std() * (252**0.5)) if port_returns.std() else 0

            risk = {
                "volatility": round(float(vol), 2),
                "beta": round(float(beta), 2),
                "sharpe": round(float(sharpe), 2)
            }
            self._risk_cache = {
                key: value
                for key, value in self._risk_cache.items()
                if key[0] != portfolio_id
            }
            self._risk_cache[cache_key] = {"value": deepcopy(risk), "timestamp": time.time()}
            return risk
        except Exception as e:
            print(f"Risk calculation error: {e}")
            return {"volatility": 0, "beta": 0, "sharpe": 0}

    def get_chart_data(self, portfolio_id, range_param="1y"):
        """Compute total portfolio value as a time series."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return {"error": "Portfolio not found"}

        positions = portfolio.get("positions", [])
        capital = portfolio.get("capital", 0.0)

        if not positions:
            return {"error": "No positions in portfolio"}

        RANGES = {
            "1d":  ("1d",   "5m",  True),
            "1w":  ("5d",   "60m", True),
            "1m":  ("1mo",  "1d",  False),
            "3m":  ("3mo",  "1d",  False),
            "6m":  ("6mo",  "1d",  False),
            "ytd": ("ytd",  "1d",  False),
            "1y":  ("1y",   "1d",  False),
        }
        period, interval, intraday = RANGES.get(range_param, RANGES["1y"])
        tickers = [p["ticker"] for p in positions]
        cache_key = (portfolio_id, range_param, self._portfolio_signature(portfolio))
        cached = self._chart_cache.get(cache_key)
        chart_ttl = 30 if intraday else 300
        if cached and (time.time() - cached["timestamp"]) < chart_ttl:
            return deepcopy(cached["value"])

        try:
            raw = yf.download(tickers, period=period, interval=interval,
                              progress=False, auto_adjust=True, threads=False)["Close"]
            if isinstance(raw, pd.Series):
                raw = raw.to_frame(name=tickers[0])
        except Exception as e:
            return {"error": f"Data fetch failed: {e}"}

        if raw.empty:
            return {"error": "No historical data"}

        # Total cost deployed
        total_cost = sum(float(p["shares"]) * float(p["avg_cost"]) for p in positions)
        cash = capital - total_cost

        chart_data = []
        for ts, row in raw.iterrows():
            pos_value = 0.0
            for pos in positions:
                price = row.get(pos["ticker"])
                if price is not None and not pd.isna(price):
                    pos_value += float(pos["shares"]) * float(price)
            total = max(0.0, cash) + pos_value
            time_val = int(ts.timestamp()) if intraday else ts.strftime("%Y-%m-%d")
            chart_data.append({"time": time_val, "value": round(total, 2)})

        if not chart_data:
            return {"error": "No chart data computed"}

        start_val = chart_data[0]["value"]
        end_val = chart_data[-1]["value"]
        period_change = round(end_val - start_val, 2)
        period_change_pct = round((end_val - start_val) / start_val * 100, 2) if start_val else 0
        total_gain = round(end_val - capital, 2)
        total_gain_pct = round((end_val - capital) / capital * 100, 2) if capital else 0

        payload = {
            "data": chart_data,
            "intraday": intraday,
            "current_value": end_val,
            "capital": capital,
            "period_change": period_change,
            "period_change_pct": period_change_pct,
            "total_gain": total_gain,
            "total_gain_pct": total_gain_pct,
        }
        self._chart_cache = {
            key: value
            for key, value in self._chart_cache.items()
            if key[0] != portfolio_id or key[1] != range_param
        }
        self._chart_cache[cache_key] = {"value": deepcopy(payload), "timestamp": time.time()}
        return payload

    # ── New trade / target / nav methods ───────────────────────────────────────

    def record_trade(self, portfolio_id, ticker, action, shares, price, date=None, notes=""):
        trade = {
            "ticker": ticker.upper(),
            "action": action,
            "shares": float(shares),
            "price": float(price),
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "notes": notes,
        }
        return self.db.record_trade(portfolio_id, trade)

    def get_trade_history(self, portfolio_id, ticker=None):
        return self.db.get_trades(portfolio_id, ticker)

    def set_position_targets(self, portfolio_id, ticker, target_weight=None, stop_loss=None, take_profit=None, tags=None, notes=None):
        updates = {}
        if target_weight is not None:
            updates["target_weight"] = float(target_weight)
        if stop_loss is not None:
            updates["stop_loss"] = float(stop_loss)
        if take_profit is not None:
            updates["take_profit"] = float(take_profit)
        if tags is not None:
            updates["tags"] = tags if isinstance(tags, list) else [tags]
        if notes is not None:
            updates["notes"] = str(notes)
        if not updates:
            return False
        ok = self.db.update_position(portfolio_id, ticker.upper(), updates)
        if ok:
            self._invalidate_runtime_caches(portfolio_id)
        return ok

    def get_nav_history(self, portfolio_id, days=365):
        return self.db.get_nav_history(portfolio_id, days)

    def record_daily_nav(self, portfolio_id):
        """Snapshot current portfolio value into nav_snapshots."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False
        positions, cash = self.get_positions_with_returns(portfolio_id)
        position_value = sum(p["current_value"] or p["cost_basis"] for p in positions)
        total_value = max(0.0, cash) + position_value
        today = datetime.now().strftime("%Y-%m-%d")
        self.db.record_nav(portfolio_id, today, total_value, cash)
        return True

    def get_alerts(self, portfolio_id, dismissed=False):
        return self.db.get_alerts(portfolio_id, dismissed)

    def add_alert(self, portfolio_id, alert):
        return self.db.add_alert(portfolio_id, alert)

    def dismiss_alert(self, alert_id):
        return self.db.dismiss_alert(alert_id)
