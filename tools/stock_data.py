"""
Stock Data Fetcher
Fetches stock prices, company info, and financial statements using yfinance
"""

import yfinance as yf
from datetime import datetime
import json


class StockDataFetcher:
    """Fetches stock data using Yahoo Finance"""
    
    def __init__(self):
        pass
    
    def get_quote(self, ticker):
        """Get current stock quote and basic info"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
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
            stock = yf.Ticker(ticker)
            info = stock.info
            
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
    
    def get_financials(self, ticker, statement_type="all"):
        """Get financial statements"""
        try:
            stock = yf.Ticker(ticker)
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
            
            return result
        except Exception as e:
            return {"error": f"Failed to get financials for {ticker}: {str(e)}"}
    
    def get_key_metrics(self, ticker):
        """Get key financial metrics and ratios"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
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
