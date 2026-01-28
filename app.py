"""
THE PILL - Shkreli Method Stock Analysis
A local web app that runs fundamental analysis on any publicly traded company
"""

import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import anthropic
from tools.sec_fetcher import SECFetcher
from tools.stock_data import StockDataFetcher

load_dotenv()

app = Flask(__name__)

# Initialize clients
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
sec_fetcher = SECFetcher()
stock_fetcher = StockDataFetcher()

# The Shkreli Method System Prompt
SHKRELI_SYSTEM_PROMPT = """You are an expert Fundamental Financial Analyst AI modeled after the methodology of Martin Shkreli. Your goal is to construct a "ground-up" financial model for a given company, prioritizing raw data extraction from SEC filings (10-K/10-Q) over aggregated news sources. You are skeptical, precise, and focused on cash flow over GAAP earnings.

Tone: Highly technical, direct, slightly irreverent, and educational. You prefer "plugging and chugging" raw numbers to build conviction.

You have access to tools to fetch SEC filings and stock data. Use them to gather all necessary information.

When analyzing a company, follow these phases:

## Phase 1: The "Six Important Things" (Capital Structure)
1. Stock Price: Get the last sale price
2. Shares Outstanding: Extract from the latest 10-Q or 10-K cover page
3. Market Cap: Calculate Price × Shares Outstanding
4. Cash: Extract "Cash and Cash Equivalents" + Marketable Securities from Balance Sheet
5. Debt: Extract Total Debt (Short-term + Long-term) from Balance Sheet
6. Enterprise Value (EV): Calculate Market Cap + Debt - Cash

## Phase 2: Income Statement Analysis (Longitudinal)
Build a quarterly model looking back 4-8 quarters. Extract:
- Revenue, COGS, Gross Profit, Gross Margin
- R&D, SG&A, Operating Income, Operating Margin
- Interest Expense, Net Income

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
- Organic vs Inorganic Growth (check for acquisitions)
- Segment Analysis (revenue by product line)
- Valuation: Compare Cash Flow to Enterprise Value

## Output Format
Present the data in clean tables with a "Shkreli Commentary" section that interprets the data, calls out anomalies, and gives a verdict on whether the company is "investable."

Format your response in Markdown with clear headers, tables, and bold text for emphasis.
"""

# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_stock_quote",
        "description": "Get the current stock price, market cap, and basic quote data for a ticker symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g., AAPL, GOOGL, AMZN)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_company_info",
        "description": "Get basic company information including name, sector, industry, and description",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_financial_statements",
        "description": "Get income statement, balance sheet, and cash flow statement data for a company. Returns quarterly and annual data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol"
                },
                "statement_type": {
                    "type": "string",
                    "enum": ["income", "balance", "cashflow", "all"],
                    "description": "Type of financial statement to retrieve"
                }
            },
            "required": ["ticker", "statement_type"]
        }
    },
    {
        "name": "get_sec_filing",
        "description": "Get the latest SEC filing (10-K or 10-Q) for a company including shares outstanding and key financial data",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol"
                },
                "filing_type": {
                    "type": "string",
                    "enum": ["10-K", "10-Q"],
                    "description": "Type of SEC filing"
                }
            },
            "required": ["ticker", "filing_type"]
        }
    },
    {
        "name": "get_key_metrics",
        "description": "Get key financial metrics and ratios for a company including P/E, EV/EBITDA, margins, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    }
]


def process_tool_call(tool_name, tool_input):
    """Process a tool call and return the result"""
    ticker = tool_input.get("ticker", "").upper()
    
    if tool_name == "get_stock_quote":
        return stock_fetcher.get_quote(ticker)
    elif tool_name == "get_company_info":
        return stock_fetcher.get_company_info(ticker)
    elif tool_name == "get_financial_statements":
        statement_type = tool_input.get("statement_type", "all")
        return stock_fetcher.get_financials(ticker, statement_type)
    elif tool_name == "get_sec_filing":
        filing_type = tool_input.get("filing_type", "10-Q")
        return sec_fetcher.get_filing(ticker, filing_type)
    elif tool_name == "get_key_metrics":
        return stock_fetcher.get_key_metrics(ticker)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def run_analysis(ticker):
    """Run the full Shkreli Method analysis using Claude with tools"""
    
    messages = [
        {
            "role": "user",
            "content": f"""Analyze {ticker.upper()} using the Shkreli Method.

First, gather all necessary data using the available tools:
1. Get the current stock quote
2. Get company info
3. Get all financial statements (income, balance, cashflow)
4. Get the latest SEC filing (10-Q) for shares outstanding
5. Get key metrics

Then perform the full analysis following all 5 phases and provide your verdict.

Be thorough and use real numbers from the data. If any data is missing, note it and work with what you have."""
        }
    ]
    
    # Agentic loop - keep going until Claude is done
    while True:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SHKRELI_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        # Check if we need to process tool calls
        if response.stop_reason == "tool_use":
            # Process all tool calls in the response
            tool_results = []
            assistant_content = response.content
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_result = process_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_result, indent=2)
                    })
            
            # Add assistant message and tool results to conversation
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            
        else:
            # Claude is done, extract the final text response
            final_response = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_response += block.text
            return final_response


def run_analysis_streaming(ticker):
    """Run analysis with streaming output"""
    
    messages = [
        {
            "role": "user",
            "content": f"""Analyze {ticker.upper()} using the Shkreli Method.

First, gather all necessary data using the available tools:
1. Get the current stock quote
2. Get company info  
3. Get all financial statements (income, balance, cashflow)
4. Get the latest SEC filing (10-Q) for shares outstanding
5. Get key metrics

Then perform the full analysis following all 5 phases and provide your verdict.

Be thorough and use real numbers from the data. If any data is missing, note it and work with what you have."""
        }
    ]
    
    # First, do the tool-calling phase (non-streaming)
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
            assistant_content = response.content
            
            for block in response.content:
                if block.type == "tool_use":
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Fetching {block.name}...'})}\n\n"
                    tool_result = process_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_result, indent=2)
                    })
            
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Extract final response
            for block in response.content:
                if hasattr(block, "text"):
                    yield f"data: {json.dumps({'type': 'content', 'text': block.text})}\n\n"
            break
    
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """API endpoint to run analysis"""
    data = request.json
    ticker = data.get("ticker", "").strip().upper()
    
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    
    try:
        result = run_analysis(ticker)
        return jsonify({"success": True, "analysis": result, "ticker": ticker})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze/stream", methods=["GET"])
def analyze_stream():
    """SSE endpoint for streaming analysis"""
    ticker = request.args.get("ticker", "").strip().upper()
    
    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400
    
    return Response(
        stream_with_context(run_analysis_streaming(ticker)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  THE PILL - Shkreli Method Stock Analysis")
    print("="*50)
    print("\n  Starting server at http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
