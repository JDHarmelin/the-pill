"""Tests for FinnhubFetcher."""

import os
import pytest
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from tools.finnhub_fetcher import FinnhubFetcher


class TestGetRealtimeQuote:
    """Tests for FinnhubFetcher.get_realtime_quote."""

    def test_success(self, sample_finnhub_quote):
        """Successful quote returns all expected keys with correct values."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_finnhub_quote

        with patch("tools.finnhub_fetcher.requests.get", return_value=mock_response):
            fetcher = FinnhubFetcher()
            fetcher.api_key = "test-key"
            result = fetcher.get_realtime_quote("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["price"] == 150.25
        assert result["change"] == 2.50
        assert result["change_percent"] == 1.69
        assert result["day_high"] == 151.00
        assert result["day_low"] == 148.50
        assert result["open"] == 149.00
        assert result["previous_close"] == 147.75
        assert result["realtime"] is True
        assert "timestamp" in result

    def test_no_api_key_returns_error(self):
        """Returns error dict when FINNHUB_API_KEY is not set."""
        fetcher = FinnhubFetcher()
        fetcher.api_key = None
        result = fetcher.get_realtime_quote("AAPL")

        assert "error" in result
        assert "not configured" in result["error"]

    def test_api_connection_error(self):
        """Returns error dict on requests exception."""
        import requests as req

        with patch("tools.finnhub_fetcher.requests.get", side_effect=req.ConnectionError("timeout")):
            fetcher = FinnhubFetcher()
            fetcher.api_key = "test-key"
            result = fetcher.get_realtime_quote("AAPL")

        assert "error" in result

    def test_bad_json_response(self):
        """Returns error dict when response JSON is malformed."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")

        with patch("tools.finnhub_fetcher.requests.get", return_value=mock_response):
            fetcher = FinnhubFetcher()
            fetcher.api_key = "test-key"
            result = fetcher.get_realtime_quote("AAPL")

        assert "error" in result

    def test_ticker_uppercased(self, sample_finnhub_quote):
        """Lowercase ticker is uppercased in result."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_finnhub_quote

        with patch("tools.finnhub_fetcher.requests.get", return_value=mock_response):
            fetcher = FinnhubFetcher()
            fetcher.api_key = "test-key"
            result = fetcher.get_realtime_quote("aapl")

        assert result["ticker"] == "AAPL"

    @freeze_time("2026-01-15T10:30:00")
    def test_timestamp_matches_current_time(self, sample_finnhub_quote):
        """Timestamp reflects the time of the call."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_finnhub_quote

        with patch("tools.finnhub_fetcher.requests.get", return_value=mock_response):
            fetcher = FinnhubFetcher()
            fetcher.api_key = "test-key"
            result = fetcher.get_realtime_quote("AAPL")

        assert result["timestamp"] == "2026-01-15T10:30:00"

    def test_api_called_with_correct_params(self, sample_finnhub_quote):
        """Requests.get is called with correct URL and params."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_finnhub_quote

        with patch("tools.finnhub_fetcher.requests.get", return_value=mock_response) as mock_get:
            fetcher = FinnhubFetcher()
            fetcher.api_key = "my-api-key"
            fetcher.get_realtime_quote("MSFT")

        mock_get.assert_called_once_with(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": "MSFT", "token": "my-api-key"}
        )
