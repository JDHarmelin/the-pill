"""Tests for SECFetcher."""

import pytest
import responses
import requests

from tools.sec_fetcher import SECFetcher

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


class TestGetCik:
    """Tests for SECFetcher._get_cik."""

    @responses.activate
    def test_found(self, sample_sec_tickers):
        """Returns zero-padded CIK when ticker is found."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        fetcher = SECFetcher()
        result = fetcher._get_cik("AAPL")
        assert result == "0000320193"

    @responses.activate
    def test_not_found(self, sample_sec_tickers):
        """Returns None when ticker is not in the mapping."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        fetcher = SECFetcher()
        result = fetcher._get_cik("ZZZZ")
        assert result is None

    @responses.activate
    def test_case_insensitive(self, sample_sec_tickers):
        """Lowercase ticker still matches."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        fetcher = SECFetcher()
        result = fetcher._get_cik("aapl")
        assert result == "0000320193"

    @responses.activate
    def test_network_error(self):
        """Returns None on connection error."""
        responses.add(responses.GET, SEC_TICKERS_URL, body=requests.ConnectionError("timeout"))
        fetcher = SECFetcher()
        result = fetcher._get_cik("AAPL")
        assert result is None

    @responses.activate
    def test_bad_json(self):
        """Returns None on malformed response."""
        responses.add(responses.GET, SEC_TICKERS_URL, body="not json", status=200)
        fetcher = SECFetcher()
        result = fetcher._get_cik("AAPL")
        assert result is None


class TestGetFiling:
    """Tests for SECFetcher.get_filing."""

    @responses.activate
    def test_success(self, sample_sec_tickers, sample_sec_submissions, sample_sec_company_facts):
        """Returns all expected fields on successful fetch."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, json=sample_sec_submissions)
        responses.add(responses.GET, COMPANY_FACTS_URL, json=sample_sec_company_facts)

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert result["ticker"] == "AAPL"
        assert result["company_name"] == "Apple Inc."
        assert result["cik"] == "0000320193"
        assert result["latest_filing"]["form"] == "10-Q"
        assert result["latest_filing"]["filing_date"] == "2025-10-31"
        assert result["shares_outstanding"] == 15500000000
        assert result["total_assets"] == 350000000000
        assert result["total_liabilities"] == 290000000000
        assert result["stockholders_equity"] == 60000000000
        assert "sec_url" in result

    @responses.activate
    def test_cik_not_found(self, sample_sec_tickers):
        """Returns error when ticker CIK lookup fails."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)

        fetcher = SECFetcher()
        result = fetcher.get_filing("ZZZZ", "10-Q")

        assert "error" in result
        assert "CIK" in result["error"]

    @responses.activate
    def test_no_matching_form(self, sample_sec_tickers, sample_sec_company_facts):
        """latest_filing is None when no filings match the requested type."""
        submissions_no_10q = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["8-K", "8-K"],
                    "filingDate": ["2025-10-15", "2025-01-10"],
                    "accessionNumber": ["acc-1", "acc-2"],
                    "primaryDocument": ["doc1.htm", "doc2.htm"],
                }
            }
        }
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, json=submissions_no_10q)
        responses.add(responses.GET, COMPANY_FACTS_URL, json=sample_sec_company_facts)

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert result["latest_filing"] is None
        assert result["ticker"] == "AAPL"

    @responses.activate
    def test_facts_unavailable_404(self, sample_sec_tickers, sample_sec_submissions):
        """Financial facts are None when the facts endpoint returns 404."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, json=sample_sec_submissions)
        responses.add(responses.GET, COMPANY_FACTS_URL, status=404)

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert result["shares_outstanding"] is None
        assert result["total_assets"] is None
        assert result["total_liabilities"] is None
        assert result["stockholders_equity"] is None
        # Other fields should still be populated
        assert result["ticker"] == "AAPL"
        assert result["latest_filing"]["form"] == "10-Q"

    @responses.activate
    def test_request_exception(self, sample_sec_tickers):
        """Returns error dict on RequestException."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, body=requests.ConnectionError("timeout"))

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert "error" in result
        assert "Failed to fetch SEC data" in result["error"]

    @responses.activate
    def test_xbrl_sorting_picks_most_recent(self, sample_sec_tickers, sample_sec_submissions):
        """The most recent XBRL value is selected based on end date sorting."""
        facts_out_of_order = {
            "facts": {
                "us-gaap": {
                    "CommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2025-03-31", "val": 15700000000},
                                {"end": "2025-09-30", "val": 15500000000},  # most recent
                                {"end": "2025-06-30", "val": 15600000000},
                            ]
                        }
                    },
                    "Assets": {"units": {"USD": []}},
                    "Liabilities": {"units": {"USD": []}},
                    "StockholdersEquity": {"units": {"USD": []}},
                }
            }
        }
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, json=sample_sec_submissions)
        responses.add(responses.GET, COMPANY_FACTS_URL, json=facts_out_of_order)

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert result["shares_outstanding"] == 15500000000

    @responses.activate
    def test_empty_facts_fields(self, sample_sec_tickers, sample_sec_submissions):
        """Empty XBRL arrays result in None values."""
        empty_facts = {
            "facts": {
                "us-gaap": {
                    "CommonStockSharesOutstanding": {"units": {"shares": []}},
                    "Assets": {"units": {"USD": []}},
                    "Liabilities": {"units": {"USD": []}},
                    "StockholdersEquity": {"units": {"USD": []}},
                }
            }
        }
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, SUBMISSIONS_URL, json=sample_sec_submissions)
        responses.add(responses.GET, COMPANY_FACTS_URL, json=empty_facts)

        fetcher = SECFetcher()
        result = fetcher.get_filing("AAPL", "10-Q")

        assert result["shares_outstanding"] is None
        assert result["total_assets"] is None


class TestGetCompanyFacts:
    """Tests for SECFetcher.get_company_facts."""

    @responses.activate
    def test_success(self, sample_sec_tickers, sample_sec_company_facts):
        """Returns raw JSON from the facts endpoint."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, COMPANY_FACTS_URL, json=sample_sec_company_facts)

        fetcher = SECFetcher()
        result = fetcher.get_company_facts("AAPL")

        assert "facts" in result
        assert "us-gaap" in result["facts"]

    @responses.activate
    def test_cik_not_found(self, sample_sec_tickers):
        """Returns error dict when CIK lookup fails."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)

        fetcher = SECFetcher()
        result = fetcher.get_company_facts("ZZZZ")

        assert "error" in result
        assert "CIK" in result["error"]

    @responses.activate
    def test_request_failure(self, sample_sec_tickers):
        """Returns error dict on request failure."""
        responses.add(responses.GET, SEC_TICKERS_URL, json=sample_sec_tickers)
        responses.add(responses.GET, COMPANY_FACTS_URL, body=requests.ConnectionError("fail"))

        fetcher = SECFetcher()
        result = fetcher.get_company_facts("AAPL")

        assert "error" in result
