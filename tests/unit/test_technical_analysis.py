import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
import numpy as np
from tools.technical_analysis import TechnicalAnalyzer


def test_all_keys_present():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(100) * 0.5)
    high = close + np.abs(np.random.randn(100)) * 0.5
    low = close - np.abs(np.random.randn(100)) * 0.5
    open_p = close + np.random.randn(100) * 0.3
    volume = np.random.randint(1_000_000, 10_000_000, 100)

    df = pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("TEST", df)

    expected_keys = [
        "sma_20", "sma_50", "sma_200", "sma_signal",
        "rsi_14", "rsi_signal",
        "macd", "macd_signal", "macd_histogram",
        "bb_position", "bb_width",
        "volume_sma_20", "volume_trend", "obv",
        "higher_highs", "higher_lows", "trend",
        "support", "resistance",
        "atr_14",
        "composite_score", "overall_signal",
    ]

    for key in expected_keys:
        assert key in result, f"Missing key: {key}"

    assert 0 <= result["rsi_14"] <= 100
    assert -100 <= result["composite_score"] <= 100
    assert result["overall_signal"] in ["strong_buy", "buy", "hold", "sell", "strong_sell"]


def test_rsi_oversold():
    """RSI should be very low when price drops consistently."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    close = 100 - np.arange(30) * 2  # steady decline
    df = pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.full(30, 1_000_000),
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("DROP", df)
    assert result["rsi_14"] < 30
    assert result["rsi_signal"] == "oversold"


def test_rsi_overbought():
    """RSI should be very high when price rises consistently."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    close = 100 + np.arange(30) * 2  # steady rise
    df = pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.full(30, 1_000_000),
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("RISE", df)
    assert result["rsi_14"] > 70
    assert result["rsi_signal"] == "overbought"


def test_trend_uptrend():
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    close = 100 + np.arange(10) * 2
    df = pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 0.5,
        "Close": close,
        "Volume": np.full(10, 1_000_000),
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("UP", df)
    assert result["trend"] == "uptrend"
    assert result["higher_highs"] is True
    assert result["higher_lows"] is True


def test_trend_downtrend():
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    close = 100 - np.arange(10) * 2
    df = pd.DataFrame({
        "Open": close,
        "High": close + 0.5,
        "Low": close - 1,
        "Close": close,
        "Volume": np.full(10, 1_000_000),
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("DOWN", df)
    assert result["trend"] == "downtrend"


def test_composite_score_range():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    np.random.seed(0)
    close = 100 + np.cumsum(np.random.randn(100))
    df = pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.random.randint(1_000_000, 5_000_000, 100),
    }, index=dates)

    ta = TechnicalAnalyzer()
    result = ta.analyze("RAND", df)
    assert -100 <= result["composite_score"] <= 100
