"""Tests for PortfolioManager (SQLite backend)."""

import os
import pytest
import pandas as pd
from unittest.mock import patch
from tools.portfolio_manager import PortfolioManager


@pytest.fixture
def mgr(tmp_path):
    """Fixture providing a PortfolioManager with isolated temp SQLite DB."""
    db_path = str(tmp_path / "test.db")

    def mock_db_init(self, path=None):
        self.db_path = db_path
        self._init_tables()

    with patch("db.Database.__init__", mock_db_init):
        if os.path.exists(db_path):
            os.remove(db_path)
        # Isolate from any persisted price cache
        try:
            from tools.price_cache import get_price_cache
            get_price_cache()._data = {}
        except Exception:
            pass
        yield PortfolioManager()


# ── CRUD ───────────────────────────────────────────────────────────────────


def test_get_all_returns_seeded_defaults(mgr):
    """PortfolioManager seeds default sector portfolios on init."""
    portfolios = mgr.get_all()
    assert len(portfolios) > 0
    names = {p["name"] for p in portfolios}
    assert "Space & Satellites" in names


def test_create_portfolio(mgr):
    """create adds a new portfolio to SQLite."""
    initial_count = len(mgr.get_all())
    new_p = mgr.create("Test Portfolio", 5000)

    assert new_p["name"] == "Test Portfolio"
    assert new_p["capital"] == 5000.0
    assert len(mgr.get_all()) == initial_count + 1


def test_get_portfolio(mgr):
    """get_portfolio returns a portfolio by ID."""
    p = mgr.create("Get Test")
    fetched = mgr.get_portfolio(p["id"])
    assert fetched is not None
    assert fetched["name"] == "Get Test"


def test_delete_portfolio(mgr):
    """delete removes a portfolio by ID."""
    p = mgr.create("To Delete")
    pid = p["id"]

    mgr.delete(pid)
    assert mgr.get_portfolio(pid) is None


def test_update_capital(mgr):
    """update_capital changes the capital of a portfolio."""
    p = mgr.create("Cap Update", 1000)
    pid = p["id"]

    mgr.update_capital(pid, 2000)
    updated = mgr.get_portfolio(pid)
    assert updated["capital"] == 2000.0


# ── Positions ──────────────────────────────────────────────────────────────


def test_add_position(mgr):
    """add_position adds or updates a stock position (DCA)."""
    p = mgr.create("Position Test")
    pid = p["id"]

    # New position
    mgr.add_position(pid, "AAPL", 10, 150)
    p_updated = mgr.get_portfolio(pid)
    assert len(p_updated["positions"]) == 1
    assert p_updated["positions"][0]["ticker"] == "AAPL"
    assert p_updated["positions"][0]["shares"] == 10

    # Update existing position (DCA)
    mgr.add_position(pid, "AAPL", 10, 160)
    p_updated = mgr.get_portfolio(pid)
    assert len(p_updated["positions"]) == 1
    assert p_updated["positions"][0]["shares"] == 20
    assert p_updated["positions"][0]["avg_cost"] == 155.0


def test_remove_position(mgr):
    """remove_position deletes a ticker from a portfolio."""
    p = mgr.create("Remove Test")
    pid = p["id"]
    mgr.add_position(pid, "AAPL", 10, 150)

    mgr.remove_position(pid, "AAPL")
    p_updated = mgr.get_portfolio(pid)
    assert len(p_updated["positions"]) == 0


# ── Live Data & Summary ──────────────────────────────────────────────────


@patch("yfinance.download")
def test_get_summary(mock_yf_download, mgr):
    """get_summary computes total value and gains correctly."""
    p = mgr.create("Summary Test", 10000)
    pid = p["id"]
    mgr.add_position(pid, "AAPL", 10, 150)  # Cost 1500

    df = pd.DataFrame({"AAPL": [155.0, 160.0]})
    mock_yf_download.return_value = {"Close": df}

    summary = mgr.get_summary(pid)
    assert summary["cash"] == 8500.0  # 10000 - 1500
    assert summary["position_value"] == 1600.0  # 10 * 160
    assert summary["total_value"] == 10100.0
    assert summary["total_gain"] == 100.0
    assert summary["total_gain_pct"] == 1.0


@patch("yfinance.download")
def test_risk_metrics_cache_reuses_download(mock_yf_download, mgr):
    """calculate_risk_metrics caches expensive historical downloads per holdings state."""
    p = mgr.create("Risk Cache Test", 10000)
    pid = p["id"]
    mgr.add_position(pid, "AAPL", 10, 150)

    close_df = pd.DataFrame(
        {
            "AAPL": [100.0, 102.0, 101.0, 103.0],
            "SPY": [400.0, 404.0, 402.0, 406.0],
        }
    )
    mock_yf_download.return_value = {"Close": close_df}

    first = mgr.calculate_risk_metrics(pid)
    second = mgr.calculate_risk_metrics(pid)

    assert first == second
    assert mock_yf_download.call_count == 1


# ── Cache ──────────────────────────────────────────────────────────────────


def test_positions_cache_reuses_result(mgr):
    """Repeated get_positions_with_returns calls stay cached."""
    p = mgr.create("Cache Test", 10000)
    pid = p["id"]
    mgr.add_position(pid, "AAPL", 10, 150)

    # First call populates cache
    first = mgr.get_positions_with_returns(pid)

    # Second call should hit cache (no yfinance download)
    second = mgr.get_positions_with_returns(pid)
    assert first == second
    # Verify cache exists
    assert len(mgr._positions_cache) > 0
