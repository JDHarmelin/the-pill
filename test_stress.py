import sys
import os
from dotenv import load_dotenv

load_dotenv()

from tools.finnhub_fetcher import FinnhubFetcher
from tools.sec_fetcher import SECFetcher
from tools.stock_data import StockDataFetcher

tickers = ["AAPL", "INVALID123", "BTC-USD", "TCEHY"]

finnhub = FinnhubFetcher()
sec = SECFetcher()
stock = StockDataFetcher()

for t in tickers:
    print(f"\n--- Testing {t} ---")
    
    print("1. Finnhub Quote:")
    try:
        print(finnhub.get_realtime_quote(t))
    except Exception as e:
        print("ERROR:", e)

    print("\n2. SEC Filing (10-Q):")
    try:
        print(sec.get_filing(t))
    except Exception as e:
        print("ERROR:", e)

    print("\n3. yfinance Quote:")
    try:
        print(stock.get_quote(t))
    except Exception as e:
        print("ERROR:", e)

    print("\n4. yfinance Financials:")
    try:
        res = stock.get_financials(t)
        if "error" in res:
            print("ERROR RETURNED:", res)
        else:
            print("Keys:", list(res.keys()))
    except Exception as e:
        print("EXCEPTION:", e)
