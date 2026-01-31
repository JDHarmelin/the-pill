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
            return {"error": "Finnhub API key not configured"}
        try:
            response = requests.get(
                f"{self.BASE_URL}/quote",
                params={"symbol": ticker.upper(), "token": self.api_key}
            )
            data = response.json()
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
