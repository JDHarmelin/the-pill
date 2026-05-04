"""Tests for analysis pipeline helpers."""

from app import _build_compact_financial_summary


def test_build_compact_financial_summary_extracts_recent_metrics():
    financials = {
        "ticker": "ACME",
        "quarterly_income_statement": {
            "2025-06-30": {"Total Revenue": 1200, "Gross Profit": 500, "Operating Income": 150, "Net Income": 90},
            "2025-03-31": {"Total Revenue": 1000, "Gross Profit": 450, "Operating Income": 120, "Net Income": 70},
        },
        "quarterly_balance_sheet": {
            "2025-06-30": {"Cash And Cash Equivalents": 300, "Total Assets": 5000, "Total Liabilities": 2100},
            "2025-03-31": {"Cash And Cash Equivalents": 280, "Total Assets": 4900, "Total Liabilities": 2050},
        },
        "quarterly_cash_flow": {
            "2025-06-30": {"Operating Cash Flow": 200, "Free Cash Flow": 150},
            "2025-03-31": {"Operating Cash Flow": 170, "Free Cash Flow": 120},
        },
    }

    summary = _build_compact_financial_summary(financials)

    assert summary["ticker"] == "ACME"
    assert summary["quarterly"]["revenue"][0] == {"date": "2025-06-30", "value": 1200}
    assert summary["quarterly"]["cash"][0] == {"date": "2025-06-30", "value": 300}
    assert summary["quarterly"]["operating_cash_flow"][0] == {"date": "2025-06-30", "value": 200}
    assert summary["sequential_change_pct"]["revenue"] == 20.0


def test_build_compact_financial_summary_handles_errors():
    summary = _build_compact_financial_summary({"error": "boom"})
    assert summary == {"error": "boom"}
