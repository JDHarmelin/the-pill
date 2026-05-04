"""
Sector cache — file-backed ticker-to-sector lookup.
Avoids repeated yfinance info calls.
"""

import os
import json
import threading
import time

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sector_cache.json")
_FALLBACK_TTL = 86400 * 7  # 7 days for unknown tickers
_lock = threading.RLock()


def _load():
    try:
        with open(_CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data):
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_sector(ticker: str) -> str:
    """Return sector for a ticker. Uses cache, falls back to yfinance."""
    ticker = ticker.upper()
    with _lock:
        cache = _load()
    entry = cache.get(ticker)
    if entry and isinstance(entry, str):
        return entry
    if entry and isinstance(entry, dict):
        if time.time() - entry.get("ts", 0) < _FALLBACK_TTL:
            return entry.get("sector", "Unknown")

    # Fallback to yfinance
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown") or "Unknown"
    except Exception:
        sector = "Unknown"

    with _lock:
        cache = _load()
        cache[ticker] = {"sector": sector, "ts": int(time.time())}
        _save(cache)
    return sector


def get_sectors(tickers: list) -> dict:
    """Batch sector lookup."""
    return {t: get_sector(t) for t in tickers}
