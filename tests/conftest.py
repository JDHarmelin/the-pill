"""Shared test fixtures for The Pill test suite."""

import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Set required env vars before importing app (module-level side effects)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("FINNHUB_API_KEY", "test-finnhub-key")


@pytest.fixture
def flask_app():
    """Create Flask app configured for testing."""
    from app import app
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app):
    """Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def sample_finnhub_quote():
    """Sample Finnhub API response for a stock quote."""
    return {
        "c": 150.25,    # current price
        "d": 2.50,      # change
        "dp": 1.69,     # percent change
        "h": 151.00,    # high
        "l": 148.50,    # low
        "o": 149.00,    # open
        "pc": 147.75,   # previous close
        "t": 1700000000  # timestamp
    }


@pytest.fixture
def sample_yf_info():
    """Sample yfinance .info dict with all common keys."""
    return {
        "currentPrice": 150.25,
        "previousClose": 147.75,
        "open": 149.00,
        "dayHigh": 151.00,
        "dayLow": 148.50,
        "volume": 50000000,
        "averageVolume": 45000000,
        "marketCap": 2500000000000,
        "sharesOutstanding": 16000000000,
        "floatShares": 15800000000,
        "fiftyTwoWeekHigh": 200.00,
        "fiftyTwoWeekLow": 120.00,
        "currency": "USD",
        "exchange": "NMS",
        "quoteType": "EQUITY",
        "longName": "Apple Inc.",
        "shortName": "Apple",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "Apple designs, manufactures, and markets smartphones.",
        "website": "https://www.apple.com",
        "fullTimeEmployees": 164000,
        "city": "Cupertino",
        "state": "CA",
        "country": "United States",
        "companyOfficers": [
            {"name": "Tim Cook", "title": "CEO"},
            {"name": "Luca Maestri", "title": "CFO"},
            {"name": "Jeff Williams", "title": "COO"},
            {"name": "Deirdre O'Brien", "title": "SVP"},
            {"name": "Craig Federighi", "title": "SVP"},
            {"name": "John Ternus", "title": "SVP"},
            {"name": "Greg Joswiak", "title": "SVP"},
        ],
        # Key metrics
        "trailingPE": 28.5,
        "forwardPE": 25.0,
        "pegRatio": 1.5,
        "priceToBook": 45.0,
        "priceToSalesTrailing12Months": 8.0,
        "enterpriseValue": 2600000000000,
        "enterpriseToRevenue": 7.0,
        "enterpriseToEbitda": 20.0,
        "profitMargins": 0.25,
        "operatingMargins": 0.30,
        "grossMargins": 0.45,
        "returnOnAssets": 0.28,
        "returnOnEquity": 1.60,
        "totalRevenue": 380000000000,
        "revenuePerShare": 24.0,
        "grossProfits": 170000000000,
        "ebitda": 130000000000,
        "netIncomeToCommon": 95000000000,
        "trailingEps": 6.0,
        "forwardEps": 6.5,
        "totalCash": 60000000000,
        "totalCashPerShare": 3.75,
        "totalDebt": 110000000000,
        "debtToEquity": 180.0,
        "currentRatio": 1.0,
        "quickRatio": 0.9,
        "bookValue": 3.5,
        "operatingCashflow": 110000000000,
        "freeCashflow": 90000000000,
        "leveredFreeCashflow": 85000000000,
        "dividendRate": 0.96,
        "dividendYield": 0.006,
        "payoutRatio": 0.15,
        "exDividendDate": 1700000000,
        "revenueGrowth": 0.08,
        "earningsGrowth": 0.10,
        "earningsQuarterlyGrowth": 0.12,
    }


@pytest.fixture
def mock_yf_ticker(sample_yf_info):
    """Factory to create a mock yfinance Ticker with configurable .info and DataFrames."""
    def _make_ticker(info_override=None, empty_financials=False):
        mock_ticker = MagicMock()
        info = {**sample_yf_info}
        if info_override:
            info.update(info_override)
        mock_ticker.info = info

        if empty_financials:
            mock_ticker.quarterly_income_stmt = pd.DataFrame()
            mock_ticker.income_stmt = pd.DataFrame()
            mock_ticker.quarterly_balance_sheet = pd.DataFrame()
            mock_ticker.balance_sheet = pd.DataFrame()
            mock_ticker.quarterly_cashflow = pd.DataFrame()
            mock_ticker.cashflow = pd.DataFrame()
        else:
            dates = pd.to_datetime(["2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31"])
            sample_df = pd.DataFrame(
                {d: [1000, 500, 200] for d in dates},
                index=["Total Revenue", "Gross Profit", "Net Income"]
            )
            mock_ticker.quarterly_income_stmt = sample_df.copy()
            mock_ticker.income_stmt = sample_df.copy()
            mock_ticker.quarterly_balance_sheet = sample_df.copy()
            mock_ticker.balance_sheet = sample_df.copy()
            mock_ticker.quarterly_cashflow = sample_df.copy()
            mock_ticker.cashflow = sample_df.copy()

        return mock_ticker
    return _make_ticker


@pytest.fixture
def sample_sec_tickers():
    """Sample SEC company_tickers.json response."""
    return {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
        "2": {"cik_str": 1018724, "ticker": "AMZN", "title": "Amazon Com Inc"},
    }


@pytest.fixture
def sample_sec_submissions():
    """Sample SEC submissions response for CIK 0000320193."""
    return {
        "name": "Apple Inc.",
        "cik": "320193",
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K", "10-K", "8-K"],
                "filingDate": ["2025-10-31", "2025-10-15", "2025-01-31", "2025-01-10"],
                "accessionNumber": ["0000320193-25-000001", "0000320193-25-000002", "0000320193-24-000003", "0000320193-24-000004"],
                "primaryDocument": ["filing-10q.htm", "filing-8k.htm", "filing-10k.htm", "filing-8k2.htm"],
            }
        }
    }


@pytest.fixture
def sample_sec_company_facts():
    """Sample SEC XBRL company facts response."""
    return {
        "facts": {
            "us-gaap": {
                "CommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"end": "2025-09-30", "val": 15500000000},
                            {"end": "2025-06-30", "val": 15600000000},
                            {"end": "2025-03-31", "val": 15700000000},
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {"end": "2025-09-30", "val": 350000000000},
                            {"end": "2025-06-30", "val": 340000000000},
                        ]
                    }
                },
                "Liabilities": {
                    "units": {
                        "USD": [
                            {"end": "2025-09-30", "val": 290000000000},
                        ]
                    }
                },
                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {"end": "2025-09-30", "val": 60000000000},
                        ]
                    }
                },
            }
        }
    }
