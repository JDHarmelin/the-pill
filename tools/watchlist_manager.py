"""
Watchlist Manager — simple watchlist storage in JSON files.
"""

from tools.json_store import JsonStore


class WatchlistManager:
    def __init__(self):
        self.db = JsonStore()

    def get_watchlists(self):
        return self.db.get_watchlists()

    def get_watchlist(self, watchlist_id):
        return self.db.get_watchlist(watchlist_id)

    def create_watchlist(self, name):
        return self.db.create_watchlist(name)

    def delete_watchlist(self, watchlist_id):
        return self.db.delete_watchlist(watchlist_id)

    def get_items(self, watchlist_id):
        return self.db.get_watchlist_items(watchlist_id)

    def add_ticker(self, watchlist_id, ticker, notes=""):
        return self.db.add_watchlist_item(watchlist_id, ticker, notes)

    def remove_ticker(self, watchlist_id, ticker):
        return self.db.remove_watchlist_item(watchlist_id, ticker)

    def get_signals(self, watchlist_id):
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
