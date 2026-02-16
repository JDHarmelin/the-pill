"""Tests for process_tool_call dispatch in app.py."""

import pytest
from unittest.mock import patch, MagicMock


class TestProcessToolCall:
    """Tests for the process_tool_call dispatch function."""

    def _call(self, tool_name, tool_input):
        """Import and call process_tool_call."""
        from app import process_tool_call
        return process_tool_call(tool_name, tool_input)

    @patch("app.finnhub_fetcher")
    def test_get_realtime_quote(self, mock_fetcher):
        """Dispatches to finnhub_fetcher.get_realtime_quote."""
        mock_fetcher.get_realtime_quote.return_value = {"price": 150}
        result = self._call("get_realtime_quote", {"ticker": "AAPL"})

        mock_fetcher.get_realtime_quote.assert_called_once_with("AAPL")
        assert result == {"price": 150}

    @patch("app.stock_fetcher")
    def test_get_stock_quote(self, mock_fetcher):
        """Dispatches to stock_fetcher.get_quote."""
        mock_fetcher.get_quote.return_value = {"price": 150}
        result = self._call("get_stock_quote", {"ticker": "AAPL"})

        mock_fetcher.get_quote.assert_called_once_with("AAPL")
        assert result == {"price": 150}

    @patch("app.stock_fetcher")
    def test_get_company_info(self, mock_fetcher):
        """Dispatches to stock_fetcher.get_company_info."""
        mock_fetcher.get_company_info.return_value = {"name": "Apple"}
        result = self._call("get_company_info", {"ticker": "AAPL"})

        mock_fetcher.get_company_info.assert_called_once_with("AAPL")
        assert result == {"name": "Apple"}

    @patch("app.stock_fetcher")
    def test_get_financial_statements(self, mock_fetcher):
        """Dispatches to stock_fetcher.get_financials with statement_type."""
        mock_fetcher.get_financials.return_value = {"data": True}
        result = self._call("get_financial_statements", {"ticker": "AAPL", "statement_type": "income"})

        mock_fetcher.get_financials.assert_called_once_with("AAPL", "income")
        assert result == {"data": True}

    @patch("app.stock_fetcher")
    def test_get_financial_statements_default_type(self, mock_fetcher):
        """Defaults to statement_type='all' when not provided."""
        mock_fetcher.get_financials.return_value = {"data": True}
        result = self._call("get_financial_statements", {"ticker": "AAPL"})

        mock_fetcher.get_financials.assert_called_once_with("AAPL", "all")

    @patch("app.sec_fetcher")
    def test_get_sec_filing(self, mock_fetcher):
        """Dispatches to sec_fetcher.get_filing with filing_type."""
        mock_fetcher.get_filing.return_value = {"filing": True}
        result = self._call("get_sec_filing", {"ticker": "AAPL", "filing_type": "10-K"})

        mock_fetcher.get_filing.assert_called_once_with("AAPL", "10-K")
        assert result == {"filing": True}

    @patch("app.sec_fetcher")
    def test_get_sec_filing_default_type(self, mock_fetcher):
        """Defaults to filing_type='10-Q' when not provided."""
        mock_fetcher.get_filing.return_value = {"filing": True}
        result = self._call("get_sec_filing", {"ticker": "AAPL"})

        mock_fetcher.get_filing.assert_called_once_with("AAPL", "10-Q")

    @patch("app.stock_fetcher")
    def test_get_key_metrics(self, mock_fetcher):
        """Dispatches to stock_fetcher.get_key_metrics."""
        mock_fetcher.get_key_metrics.return_value = {"metrics": True}
        result = self._call("get_key_metrics", {"ticker": "AAPL"})

        mock_fetcher.get_key_metrics.assert_called_once_with("AAPL")
        assert result == {"metrics": True}

    def test_unknown_tool(self):
        """Returns error for unknown tool names."""
        result = self._call("nonexistent_tool", {"ticker": "AAPL"})

        assert "error" in result
        assert "nonexistent_tool" in result["error"]

    @patch("app.finnhub_fetcher")
    def test_ticker_uppercased(self, mock_fetcher):
        """Lowercase ticker input is uppercased before dispatch."""
        mock_fetcher.get_realtime_quote.return_value = {"price": 150}
        self._call("get_realtime_quote", {"ticker": "aapl"})

        mock_fetcher.get_realtime_quote.assert_called_once_with("AAPL")

    @patch("app.finnhub_fetcher")
    def test_missing_ticker_key(self, mock_fetcher):
        """Missing ticker key defaults to empty string."""
        mock_fetcher.get_realtime_quote.return_value = {"price": None}
        self._call("get_realtime_quote", {})

        mock_fetcher.get_realtime_quote.assert_called_once_with("")
