"""Tests for StockDataFetcher._dataframe_to_dict."""

import pytest
import pandas as pd
import numpy as np

from tools.stock_data import StockDataFetcher


@pytest.fixture
def fetcher():
    return StockDataFetcher()


class TestDataframeToDict:
    """Tests for the _dataframe_to_dict helper method."""

    def test_timestamp_columns_formatted(self, fetcher):
        """Timestamp column names are converted to YYYY-MM-DD strings."""
        dates = pd.to_datetime(["2025-12-31", "2025-09-30"])
        df = pd.DataFrame({d: [100, 200] for d in dates}, index=["Revenue", "Profit"])

        result = fetcher._dataframe_to_dict(df)

        assert "2025-12-31" in result
        assert "2025-09-30" in result

    def test_string_columns_passthrough(self, fetcher):
        """String column names pass through unchanged."""
        df = pd.DataFrame({"Q4": [100], "Q3": [200]}, index=["Revenue"])

        result = fetcher._dataframe_to_dict(df)

        assert "Q4" in result
        assert "Q3" in result

    def test_numpy_int64_converted(self, fetcher):
        """numpy.int64 values are converted to native Python int."""
        df = pd.DataFrame({"col": [np.int64(42)]}, index=["row"])

        result = fetcher._dataframe_to_dict(df)

        val = result["col"]["row"]
        assert val == 42
        assert type(val) is int

    def test_numpy_float64_converted(self, fetcher):
        """numpy.float64 values are converted to native Python float."""
        df = pd.DataFrame({"col": [np.float64(3.14)]}, index=["row"])

        result = fetcher._dataframe_to_dict(df)

        val = result["col"]["row"]
        assert val == pytest.approx(3.14)
        assert type(val) is float

    def test_nan_converted_to_none(self, fetcher):
        """NaN values are converted to None."""
        df = pd.DataFrame({"col": [np.nan]}, index=["row"])

        result = fetcher._dataframe_to_dict(df)

        assert result["col"]["row"] is None

    def test_none_values_preserved(self, fetcher):
        """Python None values stay as None."""
        df = pd.DataFrame({"col": pd.array([None], dtype=object)}, index=["row"])

        result = fetcher._dataframe_to_dict(df)

        assert result["col"]["row"] is None

    def test_mixed_types(self, fetcher):
        """Mixed numpy types, NaN, and strings all convert correctly."""
        df = pd.DataFrame(
            {"col": pd.array([np.int64(1), np.float64(2.5), np.nan], dtype=object)},
            index=["a", "b", "c"]
        )

        result = fetcher._dataframe_to_dict(df)

        assert result["col"]["a"] == 1
        assert result["col"]["b"] == pytest.approx(2.5)
        assert result["col"]["c"] is None

    def test_empty_dataframe(self, fetcher):
        """Empty DataFrame returns empty dict."""
        df = pd.DataFrame()

        result = fetcher._dataframe_to_dict(df)

        assert result == {}

    def test_index_labels_as_string_keys(self, fetcher):
        """Row index labels become string keys in the inner dict."""
        df = pd.DataFrame({"col": [100, 200]}, index=["Total Revenue", "Net Income"])

        result = fetcher._dataframe_to_dict(df)

        assert "Total Revenue" in result["col"]
        assert "Net Income" in result["col"]
        assert result["col"]["Total Revenue"] == 100
        assert result["col"]["Net Income"] == 200
