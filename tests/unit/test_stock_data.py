"""Tests for StockDataFetcher."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from tools.stock_data import StockDataFetcher


@pytest.fixture
def fetcher():
    return StockDataFetcher()


class TestGetQuote:
    """Tests for StockDataFetcher.get_quote."""

    def test_success(self, fetcher, mock_yf_ticker):
        """Successful quote returns all expected fields."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_quote("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["price"] == 150.25
        assert result["previous_close"] == 147.75
        assert result["market_cap"] == 2500000000000
        assert result["shares_outstanding"] == 16000000000
        assert result["currency"] == "USD"
        assert "timestamp" in result

    def test_fallback_keys(self, fetcher, mock_yf_ticker):
        """Uses regularMarket* keys when primary keys are missing."""
        mock_ticker = mock_yf_ticker(info_override={
            "currentPrice": None,
            "previousClose": None,
            "open": None,
            "dayHigh": None,
            "dayLow": None,
            "volume": None,
            "regularMarketPrice": 149.00,
            "regularMarketPreviousClose": 146.00,
            "regularMarketOpen": 148.00,
            "regularMarketDayHigh": 150.00,
            "regularMarketDayLow": 147.00,
            "regularMarketVolume": 40000000,
        })
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_quote("AAPL")

        assert result["price"] == 149.00
        assert result["previous_close"] == 146.00
        assert result["open"] == 148.00
        assert result["day_high"] == 150.00
        assert result["day_low"] == 147.00
        assert result["volume"] == 40000000

    def test_error_on_exception(self, fetcher):
        """Returns error dict when yfinance raises."""
        with patch("tools.stock_data.yf.Ticker", side_effect=Exception("API down")):
            result = fetcher.get_quote("INVALID")

        assert "error" in result
        assert "INVALID" in result["error"]

    def test_empty_info(self, fetcher, mock_yf_ticker):
        """Empty .info dict returns None for value fields without crashing."""
        mock_ticker = mock_yf_ticker(info_override={
            k: None for k in [
                "currentPrice", "previousClose", "open", "dayHigh", "dayLow",
                "volume", "averageVolume", "marketCap", "sharesOutstanding",
                "floatShares", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "exchange", "quoteType"
            ]
        })
        mock_ticker.info.pop("regularMarketPrice", None)
        mock_ticker.info.pop("regularMarketPreviousClose", None)
        mock_ticker.info.pop("regularMarketOpen", None)
        mock_ticker.info.pop("regularMarketDayHigh", None)
        mock_ticker.info.pop("regularMarketDayLow", None)
        mock_ticker.info.pop("regularMarketVolume", None)

        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_quote("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["price"] is None

    def test_ticker_uppercased(self, fetcher, mock_yf_ticker):
        """Lowercase ticker is uppercased in result."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_quote("aapl")

        assert result["ticker"] == "AAPL"


class TestGetCompanyInfo:
    """Tests for StockDataFetcher.get_company_info."""

    def test_success(self, fetcher, mock_yf_ticker):
        """Returns all expected company info fields."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_company_info("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["sector"] == "Technology"
        assert result["industry"] == "Consumer Electronics"
        assert result["headquarters"]["city"] == "Cupertino"
        assert result["headquarters"]["state"] == "CA"
        assert result["headquarters"]["country"] == "United States"

    def test_officers_truncated_to_five(self, fetcher, mock_yf_ticker):
        """Only top 5 officers are returned even if more exist."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_company_info("AAPL")

        assert len(result["officers"]) == 5

    def test_no_officers_key(self, fetcher, mock_yf_ticker):
        """Missing companyOfficers key returns empty list."""
        info = {
            "longName": "Test Corp",
            "sector": "Tech",
            "industry": "Software",
            "city": "SF",
            "state": "CA",
            "country": "US",
        }
        mock_ticker = mock_yf_ticker(info_override=info)
        # Remove the officers key entirely
        mock_ticker.info.pop("companyOfficers", None)

        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_company_info("AAPL")

        assert result["officers"] == []

    def test_name_fallback_to_short_name(self, fetcher, mock_yf_ticker):
        """Uses shortName when longName is missing."""
        mock_ticker = mock_yf_ticker(info_override={"longName": None})
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_company_info("AAPL")

        assert result["name"] == "Apple"

    def test_error_on_exception(self, fetcher):
        """Returns error dict when yfinance raises."""
        with patch("tools.stock_data.yf.Ticker", side_effect=Exception("fail")):
            result = fetcher.get_company_info("BAD")

        assert "error" in result
        assert "BAD" in result["error"]


class TestGetFinancials:
    """Tests for StockDataFetcher.get_financials."""

    def test_all_statements(self, fetcher, mock_yf_ticker):
        """statement_type='all' returns all 6 statement keys."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "all")

        assert result["ticker"] == "AAPL"
        assert "quarterly_income_statement" in result
        assert "annual_income_statement" in result
        assert "quarterly_balance_sheet" in result
        assert "annual_balance_sheet" in result
        assert "quarterly_cash_flow" in result
        assert "annual_cash_flow" in result

    def test_income_only(self, fetcher, mock_yf_ticker):
        """statement_type='income' returns only income keys."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "income")

        assert "quarterly_income_statement" in result
        assert "annual_income_statement" in result
        assert "quarterly_balance_sheet" not in result
        assert "quarterly_cash_flow" not in result

    def test_balance_only(self, fetcher, mock_yf_ticker):
        """statement_type='balance' returns only balance sheet keys."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "balance")

        assert "quarterly_balance_sheet" in result
        assert "annual_balance_sheet" in result
        assert "quarterly_income_statement" not in result
        assert "quarterly_cash_flow" not in result

    def test_cashflow_only(self, fetcher, mock_yf_ticker):
        """statement_type='cashflow' returns only cash flow keys."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "cashflow")

        assert "quarterly_cash_flow" in result
        assert "annual_cash_flow" in result
        assert "quarterly_income_statement" not in result
        assert "quarterly_balance_sheet" not in result

    def test_empty_dataframe_skipped(self, fetcher, mock_yf_ticker):
        """Empty DataFrames are not included in results."""
        mock_ticker = mock_yf_ticker(empty_financials=True)
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "all")

        assert result["ticker"] == "AAPL"
        assert "quarterly_income_statement" not in result
        assert "annual_income_statement" not in result

    def test_none_dataframe_handled(self, fetcher, mock_yf_ticker):
        """None DataFrames don't cause crashes."""
        mock_ticker = mock_yf_ticker()
        mock_ticker.quarterly_income_stmt = None
        mock_ticker.income_stmt = None

        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_financials("AAPL", "income")

        assert result["ticker"] == "AAPL"
        assert "quarterly_income_statement" not in result
        assert "annual_income_statement" not in result

    def test_error_on_exception(self, fetcher):
        """Returns error dict when yfinance raises."""
        with patch("tools.stock_data.yf.Ticker", side_effect=Exception("fail")):
            result = fetcher.get_financials("BAD", "all")

        assert "error" in result
        assert "BAD" in result["error"]


class TestGetKeyMetrics:
    """Tests for StockDataFetcher.get_key_metrics."""

    def test_success(self, fetcher, mock_yf_ticker):
        """Returns nested structure with all metric categories."""
        mock_ticker = mock_yf_ticker()
        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_key_metrics("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["valuation"]["trailing_pe"] == 28.5
        assert result["valuation"]["enterprise_value"] == 2600000000000
        assert result["profitability"]["profit_margin"] == 0.25
        assert result["profitability"]["gross_margin"] == 0.45
        assert result["income_statement"]["revenue"] == 380000000000
        assert result["balance_sheet"]["total_cash"] == 60000000000
        assert result["cash_flow"]["operating_cash_flow"] == 110000000000
        assert result["dividends"]["dividend_rate"] == 0.96
        assert result["growth"]["revenue_growth"] == 0.08

    def test_partial_data(self, fetcher, mock_yf_ticker):
        """Missing info keys map to None without crashes."""
        mock_ticker = mock_yf_ticker(info_override={
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": None,
        })
        # Remove keys entirely
        mock_ticker.info.pop("pegRatio", None)
        mock_ticker.info.pop("priceToBook", None)

        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_key_metrics("AAPL")

        assert result["valuation"]["trailing_pe"] is None
        assert result["valuation"]["forward_pe"] is None
        assert result["valuation"]["peg_ratio"] is None

    def test_levered_fcf_fallback(self, fetcher, mock_yf_ticker):
        """leveredFreeCashflow falls back to freeCashflow when missing."""
        mock_ticker = mock_yf_ticker()
        # Remove leveredFreeCashflow so dict.get falls through to freeCashflow
        del mock_ticker.info["leveredFreeCashflow"]

        with patch("tools.stock_data.yf.Ticker", return_value=mock_ticker):
            result = fetcher.get_key_metrics("AAPL")

        assert result["cash_flow"]["levered_free_cash_flow"] == 90000000000

    def test_error_on_exception(self, fetcher):
        """Returns error dict when yfinance raises."""
        with patch("tools.stock_data.yf.Ticker", side_effect=Exception("fail")):
            result = fetcher.get_key_metrics("BAD")

        assert "error" in result
        assert "BAD" in result["error"]
