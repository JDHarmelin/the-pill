"""
SEC EDGAR Data Fetcher
Fetches 10-K and 10-Q filings from SEC EDGAR
"""

import requests
import time
import logging


class SECFetcher:
    """Fetches SEC filing data from EDGAR"""
    
    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = f"{BASE_URL}/submissions"
    COMPANY_FACTS_URL = f"{BASE_URL}/api/xbrl/companyfacts"
    
    HEADERS = {
        "User-Agent": "ThePill/1.0 (contact@thepill.app)",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json"
    }
    
    _CIK_TTL = 24 * 3600  # SEC mapping rarely changes — cache for 24h
    _logger = logging.getLogger(__name__)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._cik_map = None         # {TICKER: "0000320193"}
        self._cik_map_loaded_at = 0
        self._facts_cache = {}       # {cik: (facts_json, timestamp)}

    def _load_cik_map(self):
        """Download and cache the SEC ticker→CIK map (~1MB, rarely changes)."""
        import time
        now = time.time()
        if self._cik_map and (now - self._cik_map_loaded_at) < self._CIK_TTL:
            return self._cik_map
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._cik_map = {
                entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
                for entry in data.values()
                if entry.get("ticker")
            }
            self._cik_map_loaded_at = now
        except Exception:
            self._cik_map = self._cik_map or {}
        return self._cik_map

    def _get_cik(self, ticker):
        """Get CIK number from ticker symbol (cached lookup)."""
        return self._load_cik_map().get(ticker.upper())
    
    def get_filing(self, ticker, filing_type="10-Q"):
        """Get the latest SEC filing for a company"""
        started = time.perf_counter()
        try:
            cik = self._get_cik(ticker)
            if not cik:
                return {"error": f"Could not find CIK for {ticker}"}
            
            # Get company submissions
            submissions_url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
            response = self.session.get(submissions_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract company info
            company_name = data.get("name", ticker)
            
            # Find the latest filing of the requested type
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_docs = filings.get("primaryDocument", [])
            
            latest_filing = None
            for i, form in enumerate(forms):
                if form == filing_type:
                    latest_filing = {
                        "form": form,
                        "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                        "accession_number": accession_numbers[i] if i < len(accession_numbers) else None,
                        "primary_document": primary_docs[i] if i < len(primary_docs) else None
                    }
                    break
            
            # Get company facts (XBRL data) for financial metrics — cached per CIK
            shares_outstanding = None
            assets = None
            liabilities = None
            equity = None

            now = time.time()
            cached = self._facts_cache.get(cik)
            if cached and (now - cached[1]) < 3600:
                facts = cached[0]
                self._logger.info("[timing] sec.get_filing facts_cache_hit ticker=%s elapsed_ms=%s", ticker.upper(), round((time.perf_counter() - started) * 1000, 1))
            else:
                facts_url = f"{self.COMPANY_FACTS_URL}/CIK{cik}.json"
                facts_response = self.session.get(facts_url, timeout=15)
                facts = facts_response.json() if facts_response.status_code == 200 else None
                if facts:
                    self._facts_cache[cik] = (facts, now)

            if facts:
                us_gaap = facts.get("facts", {}).get("us-gaap", {})
                
                # Try to get shares outstanding
                shares_data = us_gaap.get("CommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
                if shares_data:
                    # Get the most recent value
                    sorted_shares = sorted(shares_data, key=lambda x: x.get("end", ""), reverse=True)
                    if sorted_shares:
                        shares_outstanding = sorted_shares[0].get("val")
                
                # Try to get total assets
                assets_data = us_gaap.get("Assets", {}).get("units", {}).get("USD", [])
                if assets_data:
                    sorted_assets = sorted(assets_data, key=lambda x: x.get("end", ""), reverse=True)
                    if sorted_assets:
                        assets = sorted_assets[0].get("val")
                
                # Try to get total liabilities
                liabilities_data = us_gaap.get("Liabilities", {}).get("units", {}).get("USD", [])
                if liabilities_data:
                    sorted_liab = sorted(liabilities_data, key=lambda x: x.get("end", ""), reverse=True)
                    if sorted_liab:
                        liabilities = sorted_liab[0].get("val")
                
                # Try to get stockholders equity
                equity_data = us_gaap.get("StockholdersEquity", {}).get("units", {}).get("USD", [])
                if equity_data:
                    sorted_equity = sorted(equity_data, key=lambda x: x.get("end", ""), reverse=True)
                    if sorted_equity:
                        equity = sorted_equity[0].get("val")
            
            return {
                "ticker": ticker.upper(),
                "company_name": company_name,
                "cik": cik,
                "latest_filing": latest_filing,
                "shares_outstanding": shares_outstanding,
                "total_assets": assets,
                "total_liabilities": liabilities,
                "stockholders_equity": equity,
                "sec_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing_type}"
            }
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to fetch SEC data: {str(e)}"}
        except Exception as e:
            return {"error": f"Error processing SEC data: {str(e)}"}
        finally:
            self._logger.info(
                "[timing] sec.get_filing ticker=%s filing_type=%s elapsed_ms=%s",
                ticker.upper(),
                filing_type,
                round((time.perf_counter() - started) * 1000, 1),
            )
    
    def get_recent_filings(self, ticker, limit=10):
        """Get recent SEC filings for a company"""
        try:
            cik = self._get_cik(ticker)
            if not cik:
                return {"error": f"Could not find CIK for {ticker}"}

            submissions_url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
            response = self.session.get(submissions_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_docs = filings.get("primaryDocument", [])
            descriptions = filings.get("primaryDocDescription", [])

            results = []
            for i in range(min(limit, len(forms))):
                acc_num = accession_numbers[i] if i < len(accession_numbers) else None
                # Build EDGAR viewer URL
                edgar_url = None
                if acc_num:
                    acc_clean = acc_num.replace("-", "")
                    edgar_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{primary_docs[i]}" if i < len(primary_docs) and primary_docs[i] else None

                results.append({
                    "form": forms[i],
                    "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                    "accession_number": acc_num,
                    "description": descriptions[i] if i < len(descriptions) else None,
                    "edgar_url": edgar_url,
                })

            return {
                "ticker": ticker.upper(),
                "cik": cik,
                "company_name": data.get("name", ticker),
                "filings": results,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_company_facts(self, ticker):
        """Get all XBRL facts for a company"""
        try:
            cik = self._get_cik(ticker)
            if not cik:
                return {"error": f"Could not find CIK for {ticker}"}
            
            facts_url = f"{self.COMPANY_FACTS_URL}/CIK{cik}.json"
            response = self.session.get(facts_url, timeout=15)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}


# Test the fetcher
if __name__ == "__main__":
    fetcher = SECFetcher()
    
    # Test with Apple
    print("Testing SEC Fetcher with AAPL...")
    result = fetcher.get_filing("AAPL", "10-Q")
    print(f"Result: {result}")
