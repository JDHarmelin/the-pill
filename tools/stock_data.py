"""
Stock Data Fetcher
Fetches stock prices, company info, and financial statements using yfinance
"""

import yfinance as yf
from datetime import datetime
import pandas as pd
import time
import logging


class StockDataFetcher:
    """Fetches stock data using Yahoo Finance"""
    
    _INFO_TTL = 300  # 5 minutes
    _DATA_TTLS = {
        "financials": 900,
        "earnings_history": 900,
        "institutional_holders": 3600,
        "chart": 300,
    }
    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._ticker_cache = {}   # {symbol: (yf.Ticker, timestamp)}
        self._info_cache = {}     # {symbol: (info_dict, timestamp)}
        self._data_cache = {}     # {(kind, symbol, extra): (payload, timestamp)}

    def _get_ticker(self, symbol):
        """Get a cached yf.Ticker object (reused for 5 minutes)."""
        import time
        symbol = symbol.upper()
        now = time.time()
        cached = self._ticker_cache.get(symbol)
        if cached and (now - cached[1]) < self._INFO_TTL:
            return cached[0]
        t = yf.Ticker(symbol)
        self._ticker_cache[symbol] = (t, now)
        return t

    def _get_info(self, symbol):
        """Cache the expensive .info call (HTTP fetch) per symbol for 5 minutes."""
        symbol = symbol.upper()
        now = time.time()
        cached = self._info_cache.get(symbol)
        if cached and (now - cached[1]) < self._INFO_TTL:
            return cached[0]
        info = self._get_ticker(symbol).info or {}
        self._info_cache[symbol] = (info, now)
        return info

    def _get_cached_payload(self, kind, symbol, extra=None):
        key = (kind, symbol.upper(), extra)
        cached = self._data_cache.get(key)
        ttl = self._DATA_TTLS.get(kind, self._INFO_TTL)
        if cached and (time.time() - cached[1]) < ttl:
            return cached[0]
        return None

    def _store_cached_payload(self, kind, symbol, payload, extra=None):
        key = (kind, symbol.upper(), extra)
        self._data_cache[key] = (payload, time.time())
        return payload
    
    def get_quote(self, ticker):
        """Get current stock quote and basic info"""
        try:
            info = self._get_info(ticker)

            # Extract key quote data
            return {
                "ticker": ticker.upper(),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "previous_close": info.get("previousClose") or info.get("regularMarketPreviousClose"),
                "open": info.get("open") or info.get("regularMarketOpen"),
                "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                "volume": info.get("volume") or info.get("regularMarketVolume"),
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "float_shares": info.get("floatShares"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange"),
                "quote_type": info.get("quoteType"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"Failed to get quote for {ticker}: {str(e)}"}
    
    def get_company_info(self, ticker):
        """Get company information"""
        try:
            info = self._get_info(ticker)

            return {
                "ticker": ticker.upper(),
                "name": info.get("longName") or info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "description": info.get("longBusinessSummary"),
                "website": info.get("website"),
                "employees": info.get("fullTimeEmployees"),
                "headquarters": {
                    "city": info.get("city"),
                    "state": info.get("state"),
                    "country": info.get("country")
                },
                "officers": info.get("companyOfficers", [])[:5]  # Top 5 officers
            }
        except Exception as e:
            return {"error": f"Failed to get company info for {ticker}: {str(e)}"}
            
    def get_company_overview(self, ticker):
        """Get enhanced company overview for the new UI Grid"""
        try:
            info = self._get_info(ticker)

            return {
                "ticker": ticker.upper(),
                "shortName": info.get("shortName"),
                "longBusinessSummary": info.get("longBusinessSummary"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "marketCap": info.get("marketCap"),
                "trailingPE": info.get("trailingPE"),
                "dividendYield": info.get("dividendYield"),
                "fullTimeEmployees": info.get("fullTimeEmployees"),
                "companyOfficers": info.get("companyOfficers", []),
                "exchange": info.get("exchange"),
                "country": info.get("country"),
                "firstTradeDateMilliseconds": info.get("firstTradeDateMilliseconds")
            }
        except Exception as e:
            return {"error": f"Failed to get company overview for {ticker}: {str(e)}"}
            
    def get_earnings_history(self, ticker):
        """Get earnings history (estimates vs actuals)"""
        started = time.perf_counter()
        try:
            cached = self._get_cached_payload("earnings_history", ticker)
            if cached is not None:
                self._logger.info("[timing] stock.get_earnings_history cache_hit ticker=%s elapsed_ms=%s", ticker.upper(), round((time.perf_counter() - started) * 1000, 1))
                return cached

            stock = self._get_ticker(ticker)
            earnings = stock.earnings_dates
            
            if earnings is None or earnings.empty:
                return {"error": "No earnings history available"}
                
            history = []
            # pandas timestamp index
            for date, row in earnings.iterrows():
                # only keep historical or near future bounds
                history.append({
                    "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
                    "epsEstimate": row.get("EPS Estimate") if not pd.isna(row.get("EPS Estimate")) else None,
                    "epsActual": row.get("Reported EPS") if not pd.isna(row.get("Reported EPS")) else None,
                    "surprisePercent": row.get("Surprise(%)") if not pd.isna(row.get("Surprise(%)")) else None
                })
                
            # Cap at last 20 quarters
            return self._store_cached_payload(
                "earnings_history",
                ticker,
                {"ticker": ticker.upper(), "history": history[:20]},
            )
        except Exception as e:
            return {"error": f"Failed to get earnings history for {ticker}: {str(e)}"}
        finally:
            self._logger.info("[timing] stock.get_earnings_history ticker=%s elapsed_ms=%s", ticker.upper(), round((time.perf_counter() - started) * 1000, 1))
            
    def get_institutional_holders(self, ticker):
        """Get top institutional holders"""
        started = time.perf_counter()
        try:
            cached = self._get_cached_payload("institutional_holders", ticker)
            if cached is not None:
                self._logger.info("[timing] stock.get_institutional_holders cache_hit ticker=%s elapsed_ms=%s", ticker.upper(), round((time.perf_counter() - started) * 1000, 1))
                return cached

            stock = self._get_ticker(ticker)
            holders = stock.institutional_holders
            
            if holders is None or holders.empty:
                return {"error": "No institutional holders available"}
                
            inst_list = []
            for _, row in holders.iterrows():
                inst_list.append({
                    "holder": row.get("Holder"),
                    "shares": row.get("Shares"),
                    "dateReported": row.get("Date Reported").strftime("%Y-%m-%d") if hasattr(row.get("Date Reported"), "strftime") else str(row.get("Date Reported")),
                    "pctHeld": row.get("% Out"),
                    "value": row.get("Value")
                })
                
            return self._store_cached_payload(
                "institutional_holders",
                ticker,
                {"ticker": ticker.upper(), "institutional": inst_list},
            )
        except Exception as e:
            return {"error": f"Failed to get institutional holders for {ticker}: {str(e)}"}
        finally:
            self._logger.info("[timing] stock.get_institutional_holders ticker=%s elapsed_ms=%s", ticker.upper(), round((time.perf_counter() - started) * 1000, 1))
    
    def get_financials(self, ticker, statement_type="all"):
        """Get financial statements"""
        started = time.perf_counter()
        try:
            cached = self._get_cached_payload("financials", ticker, statement_type)
            if cached is not None:
                self._logger.info(
                    "[timing] stock.get_financials cache_hit ticker=%s statement_type=%s elapsed_ms=%s",
                    ticker.upper(),
                    statement_type,
                    round((time.perf_counter() - started) * 1000, 1),
                )
                return cached

            stock = self._get_ticker(ticker)
            result = {"ticker": ticker.upper()}
            
            if statement_type in ["income", "all"]:
                # Quarterly income statement
                quarterly_income = stock.quarterly_income_stmt
                if quarterly_income is not None and not quarterly_income.empty:
                    result["quarterly_income_statement"] = self._dataframe_to_dict(quarterly_income)
                
                # Annual income statement
                annual_income = stock.income_stmt
                if annual_income is not None and not annual_income.empty:
                    result["annual_income_statement"] = self._dataframe_to_dict(annual_income)
            
            if statement_type in ["balance", "all"]:
                # Quarterly balance sheet
                quarterly_balance = stock.quarterly_balance_sheet
                if quarterly_balance is not None and not quarterly_balance.empty:
                    result["quarterly_balance_sheet"] = self._dataframe_to_dict(quarterly_balance)
                
                # Annual balance sheet
                annual_balance = stock.balance_sheet
                if annual_balance is not None and not annual_balance.empty:
                    result["annual_balance_sheet"] = self._dataframe_to_dict(annual_balance)
            
            if statement_type in ["cashflow", "all"]:
                # Quarterly cash flow
                quarterly_cf = stock.quarterly_cashflow
                if quarterly_cf is not None and not quarterly_cf.empty:
                    result["quarterly_cash_flow"] = self._dataframe_to_dict(quarterly_cf)
                
                # Annual cash flow
                annual_cf = stock.cashflow
                if annual_cf is not None and not annual_cf.empty:
                    result["annual_cash_flow"] = self._dataframe_to_dict(annual_cf)
            
            return self._store_cached_payload("financials", ticker, result, statement_type)
        except Exception as e:
            return {"error": f"Failed to get financials for {ticker}: {str(e)}"}
        finally:
            self._logger.info(
                "[timing] stock.get_financials ticker=%s statement_type=%s elapsed_ms=%s",
                ticker.upper(),
                statement_type,
                round((time.perf_counter() - started) * 1000, 1),
            )
    
    def get_key_metrics(self, ticker):
        """Get key financial metrics and ratios"""
        try:
            info = self._get_info(ticker)

            return {
                "ticker": ticker.upper(),
                "valuation": {
                    "market_cap": info.get("marketCap"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "trailing_pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "peg_ratio": info.get("pegRatio"),
                    "price_to_book": info.get("priceToBook"),
                    "price_to_sales": info.get("priceToSalesTrailing12Months"),
                    "ev_to_revenue": info.get("enterpriseToRevenue"),
                    "ev_to_ebitda": info.get("enterpriseToEbitda")
                },
                "profitability": {
                    "profit_margin": info.get("profitMargins"),
                    "operating_margin": info.get("operatingMargins"),
                    "gross_margin": info.get("grossMargins"),
                    "return_on_assets": info.get("returnOnAssets"),
                    "return_on_equity": info.get("returnOnEquity")
                },
                "income_statement": {
                    "revenue": info.get("totalRevenue"),
                    "revenue_per_share": info.get("revenuePerShare"),
                    "gross_profit": info.get("grossProfits"),
                    "ebitda": info.get("ebitda"),
                    "net_income": info.get("netIncomeToCommon"),
                    "eps_trailing": info.get("trailingEps"),
                    "eps_forward": info.get("forwardEps")
                },
                "balance_sheet": {
                    "total_cash": info.get("totalCash"),
                    "total_cash_per_share": info.get("totalCashPerShare"),
                    "total_debt": info.get("totalDebt"),
                    "debt_to_equity": info.get("debtToEquity"),
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                    "book_value": info.get("bookValue")
                },
                "cash_flow": {
                    "operating_cash_flow": info.get("operatingCashflow"),
                    "free_cash_flow": info.get("freeCashflow"),
                    "levered_free_cash_flow": info.get("leveredFreeCashflow", info.get("freeCashflow"))
                },
                "dividends": {
                    "dividend_rate": info.get("dividendRate"),
                    "dividend_yield": info.get("dividendYield"),
                    "payout_ratio": info.get("payoutRatio"),
                    "ex_dividend_date": info.get("exDividendDate")
                },
                "growth": {
                    "revenue_growth": info.get("revenueGrowth"),
                    "earnings_growth": info.get("earningsGrowth"),
                    "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth")
                }
            }
        except Exception as e:
            return {"error": f"Failed to get key metrics for {ticker}: {str(e)}"}
    
    # Maps range param → (yfinance period, interval, intraday flag)
    RANGE_CONFIG = {
        "1d":  ("1d",   "5m",  True),
        "1w":  ("5d",   "60m", True),
        "1m":  ("1mo",  "1d",  False),
        "3m":  ("3mo",  "1d",  False),
        "6m":  ("6mo",  "1d",  False),
        "ytd": ("ytd",  "1d",  False),
        "1y":  ("1y",   "1d",  False),
    }

    def get_chart_data(self, ticker, range_param="1y"):
        """Get OHLCV data for charting. Returns Unix timestamps for intraday, date strings for daily."""
        try:
            stock = self._get_ticker(ticker)
            period, interval, intraday = self.RANGE_CONFIG.get(range_param, self.RANGE_CONFIG["1y"])
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                return {"error": f"No chart data for {ticker}"}

            candles = []
            for date, row in hist.iterrows():
                if pd.isna(row["Close"]):
                    continue
                time_val = int(date.timestamp()) if intraday else date.strftime("%Y-%m-%d")
                candles.append({
                    "time": time_val,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                })

            first_close = candles[0]["close"] if candles else None
            last_close = candles[-1]["close"] if candles else None

            try:
                fi = stock.fast_info
                current_price = getattr(fi, "last_price", None) or last_close
            except Exception:
                current_price = last_close

            period_change = round(last_close - first_close, 2) if first_close and last_close else None
            period_change_pct = round((last_close - first_close) / first_close * 100, 2) if first_close and last_close else None

            return {
                "ticker": ticker,
                "data": candles,
                "intraday": intraday,
                "current_price": round(current_price, 2) if current_price else None,
                "period_change": period_change,
                "period_change_pct": period_change_pct,
            }
        except Exception as e:
            return {"error": str(e)}

    def _dataframe_to_dict(self, df):
        """Convert a pandas DataFrame to a dictionary with proper date handling"""
        result = {}
        for column in df.columns:
            # Convert column name (usually a Timestamp) to string
            col_name = column.strftime("%Y-%m-%d") if hasattr(column, "strftime") else str(column)
            result[col_name] = {}
            for index, value in df[column].items():
                # Convert numpy types to Python types
                if hasattr(value, "item"):
                    value = value.item()
                # Handle NaN values
                if value != value:  # NaN check
                    value = None
                result[col_name][str(index)] = value
        return result


# Test the fetcher
if __name__ == "__main__":
    fetcher = StockDataFetcher()
    
    print("Testing Stock Data Fetcher with AAPL...")
    
    print("\n1. Quote:")
    quote = fetcher.get_quote("AAPL")
    print(f"  Price: ${quote.get('price')}")
    print(f"  Market Cap: ${quote.get('market_cap'):,}")
    
    print("\n2. Company Info:")
    info = fetcher.get_company_info("AAPL")
    print(f"  Name: {info.get('name')}")
    print(f"  Sector: {info.get('sector')}")
    
    print("\n3. Key Metrics:")
    metrics = fetcher.get_key_metrics("AAPL")
    print(f"  P/E Ratio: {metrics.get('valuation', {}).get('trailing_pe')}")
    print(f"  EV/EBITDA: {metrics.get('valuation', {}).get('ev_to_ebitda')}")
