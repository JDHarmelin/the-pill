"""
Price Cache — file-backed price storage with background refresh.
Avoids hitting live APIs on every dashboard load.
"""

import os
import json
import time
import threading
from datetime import datetime
from typing import Optional

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "prices.json")
CACHE_TTL_SECONDS = 120  # Prices considered fresh for 2 minutes


class PriceCache:
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = os.path.abspath(cache_file)
        self._data = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        try:
            with open(self.cache_file, "r") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        with self._lock:
            self._data = {k.upper(): v for k, v in raw.items()}

    def _save(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, ticker: str) -> Optional[dict]:
        ticker = ticker.upper()
        with self._lock:
            entry = self._data.get(ticker)
        if not entry:
            return None
        ts = entry.get("timestamp", 0)
        if time.time() - ts > CACHE_TTL_SECONDS:
            return None
        return entry

    def get_price(self, ticker: str) -> Optional[float]:
        entry = self.get(ticker)
        if entry:
            return entry.get("price")
        return None

    def set(self, ticker: str, price: float, **extra):
        ticker = ticker.upper()
        with self._lock:
            self._data[ticker] = {
                "price": round(float(price), 4),
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                **extra,
            }
            self._save()

    def set_batch(self, prices: dict):
        """ prices = {ticker: {"price": float, ...}} """
        now = time.time()
        dt = datetime.now().isoformat()
        with self._lock:
            for ticker, data in prices.items():
                ticker = ticker.upper()
                self._data[ticker] = {
                    "price": round(float(data.get("price", 0)), 4),
                    "timestamp": now,
                    "datetime": dt,
                    **{k: v for k, v in data.items() if k not in ("price", "timestamp", "datetime")},
                }
            self._save()

    def all_tickers(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def is_fresh(self, ticker: str) -> bool:
        return self.get(ticker) is not None


_price_cache = None

def get_price_cache() -> PriceCache:
    global _price_cache
    if _price_cache is None:
        _price_cache = PriceCache()
    return _price_cache
