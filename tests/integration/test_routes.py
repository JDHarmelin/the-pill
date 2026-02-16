"""Tests for Flask route handlers."""

import json
import pytest
from unittest.mock import patch


class TestIndexRoute:
    """Tests for GET /."""

    def test_returns_200(self, client):
        """Index page returns 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_renders_html(self, client):
        """Response contains expected HTML content."""
        response = client.get("/")
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data


class TestAnalyzeStreamRoute:
    """Tests for GET /analyze/stream."""

    def test_no_ticker_returns_400(self, client):
        """Missing ticker query param returns 400 with error JSON."""
        response = client.get("/analyze/stream")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_empty_ticker_returns_400(self, client):
        """Empty ticker string returns 400."""
        response = client.get("/analyze/stream?ticker=")
        assert response.status_code == 400

    def test_whitespace_ticker_returns_400(self, client):
        """Whitespace-only ticker returns 400 after strip."""
        response = client.get("/analyze/stream?ticker=%20%20")
        assert response.status_code == 400

    @patch("app.run_analysis_streaming")
    def test_valid_ticker_returns_event_stream(self, mock_stream, client):
        """Valid ticker returns text/event-stream response."""
        mock_stream.return_value = iter([
            f"data: {json.dumps({'type': 'done'})}\n\n"
        ])
        response = client.get("/analyze/stream?ticker=AAPL")

        assert response.status_code == 200
        assert "text/event-stream" in response.content_type
        assert response.headers.get("Cache-Control") == "no-cache"

    @patch("app.run_analysis_streaming")
    def test_ticker_uppercased_in_call(self, mock_stream, client):
        """Lowercase ticker is uppercased before passing to streaming function."""
        mock_stream.return_value = iter([
            f"data: {json.dumps({'type': 'done'})}\n\n"
        ])
        client.get("/analyze/stream?ticker=aapl")

        mock_stream.assert_called_once_with("AAPL")

    @patch("app.run_analysis_streaming")
    def test_sse_response_has_no_buffering_header(self, mock_stream, client):
        """Response includes X-Accel-Buffering: no for proxy compatibility."""
        mock_stream.return_value = iter([
            f"data: {json.dumps({'type': 'done'})}\n\n"
        ])
        response = client.get("/analyze/stream?ticker=AAPL")

        assert response.headers.get("X-Accel-Buffering") == "no"
