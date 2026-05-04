"""
Finnhub Real-Time Stock Data
"""

import os
import requests
from datetime import datetime


class FinnhubFetcher:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY")

    def get_realtime_quote(self, ticker):
        if not self.api_key:
            return {
                "ticker": ticker.upper(),
                "price": None,
                "change": None,
                "change_percent": None,
                "day_high": None,
                "day_low": None,
                "open": None,
                "previous_close": None,
                "timestamp": datetime.now().isoformat(),
                "realtime": False,
            }
        try:
            response = requests.get(
                f"{self.BASE_URL}/quote",
                params={"symbol": ticker.upper(), "token": self.api_key},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("c") == 0:
                return {"error": f"No real-time price available for {ticker}"}
                
            return {
                "ticker": ticker.upper(),
                "price": data.get("c"),
                "change": data.get("d"),
                "change_percent": data.get("dp"),
                "day_high": data.get("h"),
                "day_low": data.get("l"),
                "open": data.get("o"),
                "previous_close": data.get("pc"),
                "timestamp": datetime.now().isoformat(),
                "realtime": True
            }
        except Exception as e:
            return {"error": str(e)}

    def search_symbols(self, query, limit=5):
        """Search for stock symbols matching a query string."""
        if not self.api_key or not query:
            return []
        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                params={"q": query, "token": self.api_key},
                timeout=3
            )
            data = response.json()
            results = [
                {"symbol": r["displaySymbol"], "name": r["description"]}
                for r in data.get("result", [])
                if r.get("type") in ("Common Stock", "ETP")
            ]
            return results[:limit]
        except Exception:
            return []

    def get_company_news(self, ticker, days_back=7):
        """Get recent news for a ticker."""
        if not self.api_key:
            return []
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            response = requests.get(
                f"{self.BASE_URL}/company-news",
                params={
                    "symbol": ticker.upper(),
                    "from": start_date,
                    "to": end_date,
                    "token": self.api_key
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()[:15] # Top 15 news items
        except Exception as e:
            return {"error": str(e)}

    def get_peers(self, ticker):
        """Get peer companies for a ticker."""
        if not self.api_key:
            return {"error": "No Finnhub API key configured"}
        try:
            response = requests.get(
                f"{self.BASE_URL}/stock/peers",
                params={"symbol": ticker.upper(), "token": self.api_key},
                timeout=10
            )
            response.raise_for_status()
            peers = response.json()
            return {"ticker": ticker.upper(), "peers": peers}
        except Exception as e:
            return {"error": str(e)}
