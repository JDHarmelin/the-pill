"""
THE PILL - Shkreli Method Stock Analysis (v2.0)
Real-time prices via Finnhub
"""

import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import anthropic
from tools.sec_fetcher import SECFetcher
from tools.stock_data import StockDataFetcher
from tools.finnhub_fetcher import FinnhubFetcher

load_dotenv()

app = Flask(__name__)

# Initialize clients
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
sec_fetcher = SECFetcher()
stock_fetcher = StockDataFetcher()
finnhub_fetcher = FinnhubFetcher()

SHKRELI_SYSTEM_PROMPT = """You are an expert Fundamental Financial Analyst AI modeled after the methodology of Martin Shkreli. Your goal is to construct a "ground-up" financial model for a given company, prioritizing raw data extraction from SEC filings (10-K/10-Q) over aggregated news sources. You are skeptical, precise, and focused on cash flow over GAAP earnings.

Tone: Highly technical, direct, slightly irreverent, and educational.

When analyzing a company, follow these phases:

## Phase 1: The "Six Important Things" (Capital Structure)
Use the MOST RECENT available data. Always state the date/quarter of the data you're using.
1. Stock Price: Use the REAL-TIME price from Finnhub
2. Shares Outstanding: Extract from the latest 10-Q or 10-K cover page
3. Market Cap: Calculate Price x Shares Outstanding
4. Cash: Extract Cash and Cash Equivalents + Marketable Securities from the MOST RECENT Balance Sheet
5. Debt: Extract Total Debt (Short-term + Long-term) from the MOST RECENT Balance Sheet
6. Enterprise Value (EV): Calculate Market Cap + Debt - Cash

## Phase 2: Income Statement Analysis (Longitudinal)
Build a quarterly model using the MOST RECENT 4-8 quarters by CALENDAR DATE.
IMPORTANT: Use actual dates (e.g., 2025-12-31, 2025-09-30) and label as Q4 2025, Q3 2025, etc.
Extract: Revenue, COGS, Gross Profit, Gross Margin, R&D, SG&A, Operating Income, Operating Margin, Net Income

## Phase 3: The "Cash Flow Truth" (GAAP vs. Cash)
Reconcile GAAP Net Income to actual Cash Flow:
- Start with GAAP Net Income
- Add back: D&A, Stock-Based Compensation, Deferred Taxes
- Calculate Proxy Cash Flow and compare to GAAP
- Flag massive divergences

## Phase 4: Balance Sheet Liquidity Check
- List assets in order of liquidity
- Flag Goodwill as "meaningless" for tangible book value
- Verify Assets = Liabilities + Equity

## Phase 5: Qualitative & Heuristic Checks
- Organic vs Inorganic Growth
- Segment Analysis
- Valuation: Compare Cash Flow to Enterprise Value

Format your response in Markdown with clear headers and tables.

CRITICAL: Always use the MOST RECENT data by CALENDAR DATE. Feature Q4 2025 and Q3 2025 prominently.
"""

TOOLS = [
    {
        "name": "get_realtime_quote",
        "description": "Get REAL-TIME stock price from Finnhub (not delayed). Returns current price, change, percent change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL)"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_stock_quote",
        "description": "Get stock quote data from Yahoo Finance including market cap and volume",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_company_info",
        "description": "Get company information including name, sector, industry, and description",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_financial_statements",
        "description": "Get income statement, balance sheet, and cash flow data. Returns quarterly and annual data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "statement_type": {"type": "string", "enum": ["income", "balance", "cashflow", "all"], "description": "Type of statement"}
            },
            "required": ["ticker", "statement_type"]
        }
    },
    {
        "name": "get_sec_filing",
        "description": "Get the latest SEC filing (10-K or 10-Q) including shares outstanding",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "filing_type": {"type": "string", "enum": ["10-K", "10-Q"], "description": "Filing type"}
            },
            "required": ["ticker", "filing_type"]
        }
    },
    {
        "name": "get_key_metrics",
        "description": "Get key financial metrics and ratios including P/E, EV/EBITDA, margins",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"]
        }
    }
]


def process_tool_call(tool_name, tool_input):
    ticker = tool_input.get("ticker", "").upper()
    if tool_name == "get_realtime_quote":
        return finnhub_fetcher.get_realtime_quote(ticker)
    elif tool_name == "get_stock_quote":
        return stock_fetcher.get_quote(ticker)
    elif tool_name == "get_company_info":
        return stock_fetcher.get_company_info(ticker)
    elif tool_name == "get_financial_statements":
        return stock_fetcher.get_financials(ticker, tool_input.get("statement_type", "all"))
    elif tool_name == "get_sec_filing":
        return sec_fetcher.get_filing(ticker, tool_input.get("filing_type", "10-Q"))
    elif tool_name == "get_key_metrics":
        return stock_fetcher.get_key_metrics(ticker)
    return {"error": f"Unknown tool: {tool_name}"}


def run_analysis_streaming(ticker):
    messages = [{"role": "user", "content": f"""Analyze {ticker.upper()} using the Shkreli Method.

1. Get the REAL-TIME quote from Finnhub first
2. Get company info
3. Get all financial statements
4. Get the latest SEC filing (10-Q)
5. Get key metrics

Use the MOST RECENT quarters (Q4 2025, Q3 2025, etc.) in your analysis."""}]

    while True:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SHKRELI_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    status_names = {
                        "get_realtime_quote": "📈 Getting real-time price",
                        "get_stock_quote": "📊 Fetching stock data",
                        "get_company_info": "🏢 Getting company info",
                        "get_financial_statements": "📑 Loading financials",
                        "get_sec_filing": "📋 Fetching SEC filing",
                        "get_key_metrics": "📐 Getting metrics"
                    }
                    yield f"data: {json.dumps({'type': 'status', 'message': status_names.get(block.name, 'Working...')})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(process_tool_call(block.name, block.input), indent=2)
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            for block in response.content:
                if hasattr(block, "text"):
                    yield f"data: {json.dumps({'type': 'content', 'text': block.text})}\n\n"
            break
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze/stream", methods=["GET"])
def analyze_stream():
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    return Response(
        stream_with_context(run_analysis_streaming(ticker)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set")
    if not os.getenv("FINNHUB_API_KEY"):
        print("WARNING: FINNHUB_API_KEY not set - get free key at finnhub.io")
    print("\n" + "="*50)
    print("  THE PILL v2.0 - Shkreli Method Stock Analysis")
    print("="*50)
    print("\n  http://localhost:5000\n")
    app.run(debug=True, port=5000)
