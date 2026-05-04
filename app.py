"""
THE PILL - Shkreli Method Stock Analysis (v2.0)
Real-time prices via Finnhub
"""

import os
import json
import time
import logging
import pandas as pd
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, make_response
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Lazy-initialized clients (defer heavy imports)
_claude_client = None
_sec_fetcher = None
_stock_fetcher = None
_finnhub_fetcher = None
_portfolio_mgr = None
_analysis_cache = {}
_ANALYSIS_CACHE_TTL = 900

def get_claude_client():
    global _claude_client
    if _claude_client is None:
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _claude_client

def get_sec_fetcher():
    global _sec_fetcher
    if _sec_fetcher is None:
        from tools.sec_fetcher import SECFetcher
        _sec_fetcher = SECFetcher()
    return _sec_fetcher

def get_stock_fetcher():
    global _stock_fetcher
    if _stock_fetcher is None:
        from tools.stock_data import StockDataFetcher
        _stock_fetcher = StockDataFetcher()
    return _stock_fetcher

def get_finnhub_fetcher():
    global _finnhub_fetcher
    if _finnhub_fetcher is None:
        from tools.finnhub_fetcher import FinnhubFetcher
        _finnhub_fetcher = FinnhubFetcher()
    return _finnhub_fetcher

def get_portfolio_mgr():
    global _portfolio_mgr
    if _portfolio_mgr is None:
        from tools.portfolio_manager import PortfolioManager
        _portfolio_mgr = PortfolioManager()
    return _portfolio_mgr


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

## Portfolio Context (if available)
If the user has a portfolio, you will be given:
- Current holdings with weights
- Sector allocation
- Cash position
- Risk metrics

Use this to:
- Warn about concentration risk before suggesting additions
- Suggest rebalancing when sector weights drift
- Consider cash drag and deployment opportunities
- Frame position sizing in context of total portfolio

Example: "You already have 28% in semiconductors. Adding NVDA would push you to 35%, which exceeds our 30% tech limit. Consider reducing AMD first."

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
        return get_finnhub_fetcher().get_realtime_quote(ticker)
    elif tool_name == "get_stock_quote":
        return get_stock_fetcher().get_quote(ticker)
    elif tool_name == "get_company_info":
        return get_stock_fetcher().get_company_info(ticker)
    elif tool_name == "get_financial_statements":
        return get_stock_fetcher().get_financials(ticker, tool_input.get("statement_type", "all"))
    elif tool_name == "get_sec_filing":
        return get_sec_fetcher().get_filing(ticker, tool_input.get("filing_type", "10-Q"))
    elif tool_name == "get_key_metrics":
        return get_stock_fetcher().get_key_metrics(ticker)
    return {"error": f"Unknown tool: {tool_name}"}


def _time_call(label, fn, ticker=None):
    started = time.perf_counter()
    result = fn()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    if ticker:
        logger.info("[timing] %s ticker=%s elapsed_ms=%s", label, ticker, elapsed_ms)
    else:
        logger.info("[timing] %s elapsed_ms=%s", label, elapsed_ms)
    return result


def _get_cached_analysis_entry(ticker):
    entry = _analysis_cache.get(ticker.upper())
    if not entry:
        return None
    if (time.time() - entry["timestamp"]) > _ANALYSIS_CACHE_TTL:
        _analysis_cache.pop(ticker.upper(), None)
        return None
    return entry


def _store_analysis_entry(ticker, **kwargs):
    ticker = ticker.upper()
    entry = _analysis_cache.get(ticker, {"timestamp": time.time()})
    entry.update(kwargs)
    entry["timestamp"] = time.time()
    _analysis_cache[ticker] = entry
    return entry


def _extract_statement_series(statement, labels, limit=4):
    if not isinstance(statement, dict) or not statement:
        return []
    dates = sorted(statement.keys(), reverse=True)
    series = []
    for date in dates:
        metrics = statement.get(date, {})
        value = None
        for label in labels:
            if label in metrics and metrics[label] is not None:
                value = metrics[label]
                break
        if value is not None:
            series.append({"date": date, "value": value})
        if len(series) == limit:
            break
    return series


def _build_compact_financial_summary(financials):
    if not isinstance(financials, dict) or financials.get("error"):
        return {"error": financials.get("error", "Financials unavailable")}

    metric_map = {
        "revenue": ("quarterly_income_statement", ["Total Revenue", "Operating Revenue"]),
        "gross_profit": ("quarterly_income_statement", ["Gross Profit"]),
        "operating_income": ("quarterly_income_statement", ["Operating Income"]),
        "net_income": ("quarterly_income_statement", ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"]),
        "cash": ("quarterly_balance_sheet", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
        "assets": ("quarterly_balance_sheet", ["Total Assets"]),
        "liabilities": ("quarterly_balance_sheet", ["Total Liabilities Net Minority Interest", "Total Liabilities"]),
        "operating_cash_flow": ("quarterly_cash_flow", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
        "free_cash_flow": ("quarterly_cash_flow", ["Free Cash Flow"]),
    }
    summary = {"ticker": financials.get("ticker"), "quarterly": {}}
    for field, (statement_name, labels) in metric_map.items():
        summary["quarterly"][field] = _extract_statement_series(financials.get(statement_name), labels, limit=4)

    # Simple trend flags to help the model without sending full statements.
    trend_flags = {}
    for field, series in summary["quarterly"].items():
        if len(series) >= 2 and series[1]["value"] not in (None, 0):
            latest = series[0]["value"]
            prev = series[1]["value"]
            trend_flags[field] = round(((latest - prev) / abs(prev)) * 100, 2)
    summary["sequential_change_pct"] = trend_flags
    return summary


def _get_fast_analysis_bundle(ticker):
    cached = _get_cached_analysis_entry(ticker)
    if cached and "fast_bundle" in cached:
        logger.info("[cache] fast_bundle hit ticker=%s", ticker)
        return cached["fast_bundle"]

    fh = get_finnhub_fetcher()
    sf = get_stock_fetcher()
    sec = get_sec_fetcher()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    tasks = {
        "realtime_quote": lambda: _time_call("finnhub.get_realtime_quote", lambda: fh.get_realtime_quote(ticker), ticker=ticker),
        "stock_quote": lambda: _time_call("stock.get_quote", lambda: sf.get_quote(ticker), ticker=ticker),
        "company_info": lambda: _time_call("stock.get_company_info", lambda: sf.get_company_info(ticker), ticker=ticker),
        "key_metrics": lambda: _time_call("stock.get_key_metrics", lambda: sf.get_key_metrics(ticker), ticker=ticker),
        "sec_filing": lambda: _time_call("sec.get_filing", lambda: sec.get_filing(ticker, "10-Q"), ticker=ticker),
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {"error": str(e)}
    _store_analysis_entry(ticker, fast_bundle=results)
    return results


def _get_compact_financial_bundle(ticker):
    cached = _get_cached_analysis_entry(ticker)
    if cached and "compact_financials" in cached:
        logger.info("[cache] compact_financials hit ticker=%s", ticker)
        return cached["compact_financials"]
    financials = _time_call("stock.get_financials", lambda: get_stock_fetcher().get_financials(ticker, "all"), ticker=ticker)
    compact = _build_compact_financial_summary(financials)
    _store_analysis_entry(ticker, raw_financials=financials, compact_financials=compact)
    return compact


def _get_frontend_snapshot(ticker):
    cached = _get_cached_analysis_entry(ticker)
    if cached and "frontend_snapshot" in cached:
        logger.info("[cache] frontend_snapshot hit ticker=%s", ticker)
        return cached["frontend_snapshot"]

    fast_bundle = _get_fast_analysis_bundle(ticker)
    stock_fetcher = get_stock_fetcher()
    finnhub = get_finnhub_fetcher()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = {
        "overview": lambda: _time_call("stock.get_company_overview", lambda: stock_fetcher.get_company_overview(ticker), ticker=ticker),
        "news": lambda: _time_call("finnhub.get_company_news", lambda: finnhub.get_company_news(ticker), ticker=ticker),
        "earnings": lambda: _time_call("stock.get_earnings_history", lambda: stock_fetcher.get_earnings_history(ticker), ticker=ticker),
        "holders": lambda: _time_call("stock.get_institutional_holders", lambda: stock_fetcher.get_institutional_holders(ticker), ticker=ticker),
        "financials": lambda: _time_call("stock.get_financials", lambda: stock_fetcher.get_financials(ticker, "all"), ticker=ticker),
    }
    snapshot = {"fast_bundle": fast_bundle}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                snapshot[name] = future.result()
            except Exception as e:
                logger.warning("frontend_snapshot %s failed ticker=%s error=%s", name, ticker, e)
                snapshot[name] = {"error": str(e)}

    _store_analysis_entry(
        ticker,
        frontend_snapshot=snapshot,
        raw_financials=snapshot.get("financials"),
        compact_financials=_build_compact_financial_summary(snapshot.get("financials")),
    )
    return snapshot


def _format_money(value):
    if value is None:
        return "N/A"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.2f}K"
    return f"${value:,.2f}"


def _build_fallback_analysis(ticker, fast_bundle, compact_financials=None):
    quote = fast_bundle.get("realtime_quote", {}) or {}
    stock_quote = fast_bundle.get("stock_quote", {}) or {}
    info = fast_bundle.get("company_info", {}) or {}
    metrics = fast_bundle.get("key_metrics", {}) or {}
    sec = fast_bundle.get("sec_filing", {}) or {}

    # Fallback chain for price: Finnhub real-time → Yahoo Finance
    price = quote.get("price") or stock_quote.get("price")

    lines = [
        f"# {ticker} Quick Diagnostic",
        "",
        "## Capital Structure Snapshot",
        f"- Price: {_format_money(price) if price is not None else 'N/A'}",
        f"- Market Cap: {_format_money(metrics.get('valuation', {}).get('market_cap'))}",
        f"- Enterprise Value: {_format_money(metrics.get('valuation', {}).get('enterprise_value'))}",
        f"- Shares Outstanding: {sec.get('shares_outstanding') or quote.get('shares_outstanding') or 'N/A'}",
        f"- Cash: {_format_money(metrics.get('balance_sheet', {}).get('total_cash'))}",
        f"- Debt: {_format_money(metrics.get('balance_sheet', {}).get('total_debt'))}",
        "",
        "## Company Context",
        f"- Name: {info.get('name') or ticker}",
        f"- Sector: {info.get('sector') or 'N/A'}",
        f"- Industry: {info.get('industry') or 'N/A'}",
        f"- Latest SEC filing date: {(sec.get('latest_filing') or {}).get('filing_date') or 'N/A'}",
        "",
        "## Valuation Signals",
        f"- Trailing P/E: {(metrics.get('valuation', {}) or {}).get('trailing_pe') or 'N/A'}",
        f"- EV/EBITDA: {(metrics.get('valuation', {}) or {}).get('ev_to_ebitda') or 'N/A'}",
        f"- Revenue growth: {(metrics.get('growth', {}) or {}).get('revenue_growth') or 'N/A'}",
        f"- Earnings growth: {(metrics.get('growth', {}) or {}).get('earnings_growth') or 'N/A'}",
    ]

    if compact_financials and not compact_financials.get("error"):
        seq = compact_financials.get("sequential_change_pct", {})
        lines.extend([
            "",
            "## Financial Enrichment",
            f"- Revenue sequential change: {seq.get('revenue', 'N/A')}%",
            f"- Gross profit sequential change: {seq.get('gross_profit', 'N/A')}%",
            f"- Operating cash flow sequential change: {seq.get('operating_cash_flow', 'N/A')}%",
            f"- Free cash flow sequential change: {seq.get('free_cash_flow', 'N/A')}%",
        ])

    lines.extend([
        "",
        "## Note",
        "- AI narrative is unavailable because the Anthropic API request failed. This fallback summary is generated from the fetched market and filing data so the app still returns usable output.",
    ])
    return "\n".join(lines)


def run_analysis_streaming(ticker):
    from concurrent.futures import ThreadPoolExecutor

    started = time.perf_counter()
    ticker = ticker.upper()

    yield f"data: {json.dumps({'type': 'status', 'message': '📡 Fetching fast snapshot...'})}\n\n"
    fast_bundle = _get_fast_analysis_bundle(ticker)

    portfolio_context = ""
    try:
        pm = get_portfolio_mgr()
        portfolios = pm.get_all()
        if portfolios:
            p = portfolios[0]
            positions, cash = pm.get_positions_with_returns(p["id"])
            summary = pm.get_summary(p["id"], positions, cash)
            from tools.ai_portfolio_prompts import build_portfolio_context
            portfolio_context = build_portfolio_context({
                "portfolio": p, "positions": positions, "cash": cash, "summary": summary
            })
    except Exception:
        pass

    if not os.getenv("ANTHROPIC_API_KEY"):
        yield f"data: {json.dumps({'type': 'status', 'message': '⚠️ No AI key found, generating structured fallback...'})}\n\n"
        compact_financials = _get_compact_financial_bundle(ticker)
        fallback = _build_fallback_analysis(ticker, fast_bundle, compact_financials)
        yield f"data: {json.dumps({'type': 'content', 'text': fallback})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'status', 'message': '🧠 Starting fast analysis...'})}\n\n"

    with ThreadPoolExecutor(max_workers=1) as pool:
        financials_future = pool.submit(_get_compact_financial_bundle, ticker)

        fast_block = json.dumps(fast_bundle, indent=2, default=str)
        messages = [{"role": "user", "content": f"""Analyze {ticker} using the Shkreli Method.

Start with a FAST first-pass analysis using only this light snapshot:

{fast_block}

Requirements:
- Prioritize capital structure, latest price context, SEC filing summary, and obvious valuation observations.
- Do not invent detailed quarterly trends if they are not present yet.
- End with a short 'Awaiting financial enrichment' note."""}]
        if portfolio_context:
            messages[0]["content"] += f"\n\n{portfolio_context}"
        compact_financials = financials_future.result()
        try:
            with _time_call(
                "claude.fast_stream_setup",
                lambda: get_claude_client().messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SHKRELI_SYSTEM_PROMPT,
                    messages=messages,
                ),
                ticker=ticker,
            ) as stream:
                first_token_seen = False
                for text in stream.text_stream:
                    if not first_token_seen:
                        logger.info(
                            "[timing] claude.first_token ticker=%s elapsed_ms=%s",
                            ticker,
                            round((time.perf_counter() - started) * 1000, 1),
                        )
                        first_token_seen = True
                    yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'message': '📊 Enriching with compact financial summary...'})}\n\n"
            compact_block = json.dumps(compact_financials, indent=2, default=str)
            enrichment_messages = [{"role": "user", "content": f"""You previously wrote a fast first-pass analysis for {ticker}.

Now append only a concise financial enrichment section using this compact normalized summary:

{compact_block}

Requirements:
- Add a header exactly named '## Financial Enrichment'.
- Focus on quarterly trend direction, cash flow quality, liquidity, and any contradictions versus the first pass.
- Be concise and additive. Do not repeat the whole report."""}]

            with _time_call(
                "claude.enrichment_stream_setup",
                lambda: get_claude_client().messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=SHKRELI_SYSTEM_PROMPT,
                    messages=enrichment_messages,
                ),
                ticker=ticker,
            ) as stream:
                yield f"data: {json.dumps({'type': 'content', 'text': '\\n\\n'})}\n\n"
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"
        except Exception as exc:
            logger.exception("Analysis stream fallback for ticker=%s", ticker)
            fallback = _build_fallback_analysis(ticker, fast_bundle, compact_financials)
            yield f"data: {json.dumps({'type': 'status', 'message': '⚠️ AI unavailable, returning fallback analysis...'})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'text': fallback})}\n\n"

    logger.info(
        "[timing] analysis.total ticker=%s elapsed_ms=%s",
        ticker,
        round((time.perf_counter() - started) * 1000, 1),
    )

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


def _cached(payload, max_age=60):
    """Wrap a JSON payload with a short browser cache header to cut redundant fetches."""
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = f"private, max-age={max_age}"
    return resp


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


@app.route("/api/chat", methods=["POST"])
def chat_api():
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip()
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "No message provided"}), 400

    if not os.getenv("ANTHROPIC_API_KEY"):
        return jsonify({"reply": "**Error:** ANTHROPIC_API_KEY not set."})

    system = (
        f"You are an expert financial analyst answering follow-up questions about {ticker}. "
        "Keep answers very concise, highly technical, direct, and focused on the facts."
    )

    messages = []
    for h in history:
        messages.append({
            "role": "assistant" if h.get("role") == "bot" else "user",
            "content": h.get("text", "")
        })
    messages.append({"role": "user", "content": message})

    try:
        response = get_claude_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        reply = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/chart/<ticker>")
def chart_data(ticker):
    range_param = request.args.get("range", "1y")
    data = get_stock_fetcher().get_chart_data(ticker.upper(), range_param)
    # Intraday data changes constantly; daily can cache longer
    max_age = 30 if data.get("intraday") else 300
    return _cached(data, max_age=max_age)


@app.route("/api/data/overview/<ticker>")
def overview_data(ticker):
    data = get_stock_fetcher().get_company_overview(ticker.upper())
    return _cached(data, max_age=300)


@app.route("/api/data/news/<ticker>")
def news_data(ticker):
    data = get_finnhub_fetcher().get_company_news(ticker.upper())
    return _cached(data, max_age=300)


@app.route("/api/data/earnings/<ticker>")
def earnings_data(ticker):
    data = get_stock_fetcher().get_earnings_history(ticker.upper())
    return _cached(data, max_age=900)


@app.route("/api/data/holders/<ticker>")
def holders_data(ticker):
    data = get_stock_fetcher().get_institutional_holders(ticker.upper())
    return _cached(data, max_age=3600)


@app.route("/api/data/sec_filings/<ticker>")
def sec_filings_data(ticker):
    data = get_sec_fetcher().get_recent_filings(ticker.upper(), limit=15)
    return _cached(data, max_age=900)


@app.route("/api/data/peers/<ticker>")
def peers_data(ticker):
    data = get_finnhub_fetcher().get_peers(ticker.upper())
    return _cached(data, max_age=3600)


@app.route("/api/data/financials/<ticker>")
def financials_data(ticker):
    statement_type = request.args.get("type", "all")
    if statement_type == "all":
        data = get_stock_fetcher().get_financials(ticker.upper(), "all")
    else:
        data = get_stock_fetcher().get_financials(ticker.upper(), statement_type)
    return _cached(data, max_age=900)


# ── Search autocomplete ───────────────────────────────────────────────────────

@app.route("/api/search")
def search_symbols():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    results = get_finnhub_fetcher().search_symbols(q, limit=7)
    return _cached({"results": results}, max_age=3600)


@app.route("/api/price/<ticker>")
def quick_price(ticker):
    data = get_finnhub_fetcher().get_realtime_quote(ticker.upper())
    if data.get("price") is None:
        yf_quote = get_stock_fetcher().get_quote(ticker.upper())
        if yf_quote.get("price") is not None:
            data = {
                "ticker": ticker.upper(),
                "price": yf_quote["price"],
                "previous_close": yf_quote.get("previous_close"),
                "change": None,
                "change_percent": None,
                "realtime": False,
                "fallback": "yfinance",
            }
    return _cached(data, max_age=15)


# ── Portfolio routes ──────────────────────────────────────────────────────────

@app.route("/portfolio")
def portfolio_page():
    return render_template("portfolio.html")


@app.route("/api/portfolios", methods=["GET"])
def list_portfolios():
    portfolios = get_portfolio_mgr().get_all()
    return jsonify({"portfolios": portfolios})


@app.route("/api/portfolios", methods=["POST"])
def create_portfolio():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    capital = float(data.get("capital", 10000))
    if not name:
        return jsonify({"error": "Name required"}), 400
    p = get_portfolio_mgr().create(name, capital)
    return jsonify(p), 201


@app.route("/api/portfolios/<pid>", methods=["DELETE"])
def delete_portfolio(pid):
    get_portfolio_mgr().delete(pid)
    return jsonify({"ok": True})


@app.route("/api/portfolios/<pid>/positions", methods=["GET"])
def get_positions(pid):
    mgr = get_portfolio_mgr()
    positions, cash = mgr.get_positions_with_returns(pid)
    summary = mgr.get_summary(pid, positions=positions, cash=cash)
    return jsonify({"positions": positions, "cash": cash, "summary": summary})


@app.route("/api/portfolios/<pid>/positions", methods=["POST"])
def add_position(pid):
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    shares = float(data.get("shares", 1))
    avg_cost = data.get("avg_cost")
    if not avg_cost:
        # Auto-fetch current price
        quote = get_finnhub_fetcher().get_realtime_quote(ticker)
        avg_cost = quote.get("price", 0)
    pos = get_portfolio_mgr().add_position(pid, ticker, shares, float(avg_cost))
    return jsonify(pos or {"error": "Portfolio not found"})


@app.route("/api/portfolios/<pid>/positions/<ticker>", methods=["DELETE"])
def remove_position(pid, ticker):
    get_portfolio_mgr().remove_position(pid, ticker.upper())
    return jsonify({"ok": True})


@app.route("/api/portfolios/<pid>/chart")
def portfolio_chart(pid):
    range_param = request.args.get("range", "1y")
    data = get_portfolio_mgr().get_chart_data(pid, range_param)
    return jsonify(data)


@app.route("/api/portfolios/<pid>/trades", methods=["GET"])
def get_trades(pid):
    ticker = request.args.get("ticker")
    trades = get_portfolio_mgr().get_trade_history(pid, ticker)
    return jsonify({"trades": trades})


@app.route("/api/portfolios/<pid>/targets", methods=["POST"])
def set_targets(pid):
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    ok = get_portfolio_mgr().set_position_targets(
        pid,
        ticker,
        target_weight=data.get("target_weight"),
        stop_loss=data.get("stop_loss"),
        take_profit=data.get("take_profit"),
        tags=data.get("tags"),
        notes=data.get("notes"),
    )
    return jsonify({"ok": bool(ok)})


@app.route("/api/portfolios/<pid>/nav", methods=["GET"])
def get_nav_history(pid):
    days = int(request.args.get("days", 365))
    nav = get_portfolio_mgr().get_nav_history(pid, days)
    return jsonify({"nav": nav})


@app.route("/api/portfolios/<pid>/alerts", methods=["GET"])
def get_alerts(pid):
    dismissed = request.args.get("dismissed", "false").lower() == "true"
    alerts = get_portfolio_mgr().get_alerts(pid, dismissed)
    return jsonify({"alerts": alerts})


@app.route("/api/alerts/<aid>/dismiss", methods=["POST"])
def dismiss_alert(aid):
    ok = get_portfolio_mgr().dismiss_alert(int(aid))
    return jsonify({"ok": bool(ok)})


# ── Technical Analysis routes ─────────────────────────────────────────────────

@app.route("/api/technical/<ticker>")
def technical_data(ticker):
    range_param = request.args.get("range", "1y")
    from tools.stock_data import StockDataFetcher
    from tools.technical_analysis import TechnicalAnalyzer

    sf = StockDataFetcher()
    chart_data = sf.get_chart_data(ticker.upper(), range_param)

    if chart_data.get("error"):
        return jsonify(chart_data), 400

    candles = chart_data["data"]
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)

    ta = TechnicalAnalyzer()
    result = ta.analyze(ticker.upper(), df)
    result["ticker"] = ticker.upper()
    return _cached(result, max_age=300)


@app.route("/api/technical/batch", methods=["POST"])
def technical_batch():
    data = request.get_json(force=True)
    tickers = data.get("tickers", [])
    results = {}
    from tools.stock_data import StockDataFetcher
    from tools.technical_analysis import TechnicalAnalyzer
    sf = StockDataFetcher()
    ta = TechnicalAnalyzer()
    for ticker in tickers:
        try:
            chart_data = sf.get_chart_data(ticker.upper(), "3m")
            if chart_data.get("error"):
                continue
            df = pd.DataFrame(chart_data["data"])
            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
            results[ticker.upper()] = ta.analyze(ticker.upper(), df)
        except Exception:
            continue
    return jsonify({"results": results})


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ── Signals ───────────────────────────────────────────────────────────────────

@app.route("/api/signals/<pid>")
def get_signals(pid):
    from tools.signal_engine import SignalEngine
    se = SignalEngine()
    signals = se.scan_portfolio(pid, get_portfolio_mgr())
    return jsonify({
        "signals": [
            {
                "ticker": s.ticker,
                "action": s.action,
                "conviction": s.conviction,
                "trigger_type": s.trigger_type,
                "reasoning": s.reasoning,
                "suggested_shares": s.suggested_shares,
                "current_price": s.current_price,
                "metadata": s.metadata,
            }
            for s in signals
        ]
    })


@app.route("/api/signals/scan", methods=["POST"])
def scan_tickers():
    data = request.get_json(force=True)
    tickers = data.get("tickers", [])
    from tools.signal_engine import SignalEngine
    se = SignalEngine()
    signals = se.scan_watchlist(tickers)
    return jsonify({
        "signals": [
            {
                "ticker": s.ticker,
                "action": s.action,
                "conviction": s.conviction,
                "trigger_type": s.trigger_type,
                "reasoning": s.reasoning,
            }
            for s in signals
        ]
    })


# ── Backtesting ───────────────────────────────────────────────────────────────

@app.route("/api/backtest", methods=["POST"])
def run_backtest():
    data = request.get_json(force=True)
    tickers = data.get("tickers", ["AAPL", "MSFT", "GOOGL"])
    strategy_name = data.get("strategy", "buy_and_hold")
    start_date = data.get("start_date", "2023-01-01")
    end_date = data.get("end_date", "2025-01-01")
    initial_capital = float(data.get("initial_capital", 10000))

    from tools.backtest_engine import BacktestEngine
    from tools.strategy_library import (
        shkreli_value_strategy,
        momentum_quality_strategy,
        ai_conviction_strategy,
        buy_and_hold_strategy,
    )

    strategies = {
        "shkreli_value": shkreli_value_strategy,
        "momentum_quality": momentum_quality_strategy,
        "ai_conviction": ai_conviction_strategy,
        "buy_and_hold": buy_and_hold_strategy,
    }

    strategy_fn = strategies.get(strategy_name, buy_and_hold_strategy)

    engine = BacktestEngine(initial_capital=initial_capital)
    result = engine.run(tickers, start_date, end_date, strategy_fn)

    return jsonify({
        "initial_capital": result.initial_capital,
        "final_value": result.final_value,
        "total_return_pct": result.total_return_pct,
        "cagr": result.cagr,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "max_drawdown_date": result.max_drawdown_date,
        "win_rate": result.win_rate,
        "avg_winner": result.avg_winner,
        "avg_loser": result.avg_loser,
        "profit_factor": result.profit_factor,
        "total_trades": result.total_trades,
        "benchmark_return_pct": result.benchmark_return_pct,
        "alpha": result.alpha,
        "beta": result.beta,
        "equity_curve": result.equity_curve,
        "trades": [
            {"date": t.date, "ticker": t.ticker, "action": t.action,
             "shares": t.shares, "price": t.price, "value": t.value, "reason": t.reason}
            for t in result.trades
        ],
        "monthly_returns": result.monthly_returns,
    })


# ── Rebalancing ─────────────────────────────────────────────────────────────────

@app.route("/api/rebalance/<pid>", methods=["POST"])
def rebalance_portfolio(pid):
    data = request.get_json(force=True)
    strategy = data.get("strategy", "target_weight")

    from tools.rebalance_engine import RebalanceEngine
    from tools.stock_data import StockDataFetcher

    re = RebalanceEngine()
    pm = get_portfolio_mgr()
    sf = StockDataFetcher()

    def price_source(ticker):
        q = sf.get_quote(ticker)
        return q.get("price", 0)

    if strategy == "target_weight":
        actions = re.target_weight_rebalance(pid, pm, price_source)
    elif strategy == "equal_weight":
        actions = re.equal_weight_rebalance(pid, pm, price_source)
    elif strategy == "conviction":
        from tools.signal_engine import SignalEngine
        se = SignalEngine()
        signals = se.scan_portfolio(pid, pm)
        actions = re.conviction_weighted_rebalance(pid, pm, signals, price_source)
    elif strategy == "risk_parity":
        actions = re.risk_parity_rebalance(pid, pm, price_source)
    else:
        return jsonify({"error": f"Unknown strategy: {strategy}"}), 400

    return jsonify({
        "actions": [
            {
                "ticker": a.ticker,
                "action": a.action,
                "current_shares": a.current_shares,
                "target_shares": a.target_shares,
                "delta_shares": a.delta_shares,
                "estimated_price": a.estimated_price,
                "estimated_value": a.estimated_value,
                "reason": a.reason,
            }
            for a in actions
        ]
    })


# ── Watchlists ────────────────────────────────────────────────────────────────

_watchlist_mgr = None

def get_watchlist_mgr():
    global _watchlist_mgr
    if _watchlist_mgr is None:
        from tools.watchlist_manager import WatchlistManager
        from db import Database
        _watchlist_mgr = WatchlistManager(Database())
    return _watchlist_mgr


@app.route("/api/watchlists", methods=["GET"])
def list_watchlists():
    return jsonify({"watchlists": get_watchlist_mgr().get_watchlists()})


@app.route("/api/watchlists", methods=["POST"])
def create_watchlist():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    w = get_watchlist_mgr().create_watchlist(name)
    return jsonify(w), 201


@app.route("/api/watchlists/<wid>", methods=["DELETE"])
def delete_watchlist(wid):
    get_watchlist_mgr().delete_watchlist(wid)
    return jsonify({"ok": True})


@app.route("/api/watchlists/<wid>/items", methods=["GET"])
def get_watchlist_items(wid):
    items = get_watchlist_mgr().get_items(wid)
    return jsonify({"items": items})


@app.route("/api/watchlists/<wid>/items", methods=["POST"])
def add_watchlist_item(wid):
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    notes = data.get("notes", "")
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    item = get_watchlist_mgr().add_ticker(wid, ticker, notes)
    return jsonify(item), 201


@app.route("/api/watchlists/<wid>/items/<ticker>", methods=["DELETE"])
def remove_watchlist_item(wid, ticker):
    get_watchlist_mgr().remove_ticker(wid, ticker.upper())
    return jsonify({"ok": True})


@app.route("/api/watchlists/<wid>/signals")
def get_watchlist_signals(wid):
    from tools.signal_engine import SignalEngine
    items = get_watchlist_mgr().get_items(wid)
    tickers = [i["ticker"] for i in items]
    se = SignalEngine()
    signals = se.scan_watchlist(tickers)
    return jsonify({
        "signals": [
            {"ticker": s.ticker, "action": s.action, "conviction": s.conviction,
             "reasoning": s.reasoning, "trigger_type": s.trigger_type}
            for s in signals
        ]
    })


# ── Weekly AI Review ──────────────────────────────────────────────────────────

@app.route("/api/weekly-review")
def weekly_review():
    pm = get_portfolio_mgr()
    portfolios = pm.get_all()
    if not portfolios:
        return jsonify({"error": "No portfolios"}), 400

    all_data = []
    for p in portfolios:
        positions, cash = pm.get_positions_with_returns(p["id"])
        summary = pm.get_summary(p["id"], positions, cash)
        all_data.append({"portfolio": p, "positions": positions, "summary": summary})

    from tools.ai_portfolio_prompts import build_weekly_review_prompt
    prompt = build_weekly_review_prompt(all_data, "Market summary placeholder")

    try:
        client = get_claude_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="You are a sharp, no-BS hedge fund manager writing a weekly letter.",
            messages=[{"role": "user", "content": prompt}],
        )
        review = "".join(
            getattr(b, "text", "")
            for b in response.content
            if getattr(b, "type", "") == "text"
        )
        return jsonify({"review": review})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Export routes ─────────────────────────────────────────────────────────────

@app.route("/api/portfolios/<pid>/export/positions")
def export_positions(pid):
    from tools.export_utils import export_positions_csv
    mgr = get_portfolio_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, _ = mgr.get_positions_with_returns(pid)
    csv_data = export_positions_csv(positions, portfolio["name"])
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename = f"{portfolio['name']}_positions.csv".replace(" ", "_")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.route("/api/portfolios/<pid>/export/trades")
def export_trades(pid):
    from tools.export_utils import export_trades_csv
    mgr = get_portfolio_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    trades = mgr.get_trade_history(pid)
    csv_data = export_trades_csv(trades, portfolio["name"])
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename = f"{portfolio['name']}_trades.csv".replace(" ", "_")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.route("/api/portfolios/<pid>/export/performance")
def export_performance(pid):
    from tools.export_utils import export_performance_csv
    mgr = get_portfolio_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    nav = mgr.get_nav_history(pid)
    csv_data = export_performance_csv(nav, portfolio["name"])
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename = f"{portfolio['name']}_performance.csv".replace(" ", "_")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.route("/api/portfolios/<pid>/export/pdf")
def export_pdf(pid):
    from tools.export_utils import generate_portfolio_pdf
    mgr = get_portfolio_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, cash = mgr.get_positions_with_returns(pid)
    summary = mgr.get_summary(pid, positions=positions, cash=cash)
    try:
        pdf_bytes = generate_portfolio_pdf(portfolio, positions, summary)
    except ImportError as e:
        return jsonify({"error": str(e)}), 400
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    filename = f"{portfolio['name']}_report.pdf".replace(" ", "_")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@app.route("/api/portfolios/<pid>/export/taxlots")
def export_taxlots(pid):
    from tools.export_utils import generate_tax_lot_report
    mgr = get_portfolio_mgr()
    portfolio = mgr.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    positions, _ = mgr.get_positions_with_returns(pid)
    trades = mgr.get_trade_history(pid)
    method = request.args.get("method", "FIFO")
    csv_data = generate_tax_lot_report(positions, trades, method)
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename = f"{portfolio['name']}_taxlots.csv".replace(" ", "_")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ── Dashboard API ─────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard_data():
    pm = get_portfolio_mgr()
    portfolios = pm.get_all()

    total_aum = 0.0
    total_gain = 0.0
    total_basis = 0.0
    all_positions = []
    all_signals = []

    for p in portfolios:
        positions, cash = pm.get_positions_with_returns(p["id"])
        summary = pm.get_summary(p["id"], positions, cash)
        total_aum += summary.get("total_value", 0)
        total_gain += summary.get("total_gain", 0)
        total_basis += p.get("capital", 0)
        all_positions.extend(positions)

    # Top movers (by gain_pct)
    movers = sorted(
        [pos for pos in all_positions if pos.get("gain_pct") is not None],
        key=lambda x: x["gain_pct"],
        reverse=True,
    )[:10]

    return jsonify({
        "total_aum": round(total_aum, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round((total_gain / total_basis * 100) if total_basis else 0, 2),
        "portfolio_count": len(portfolios),
        "position_count": len(all_positions),
        "top_movers": [
            {"ticker": m["ticker"], "gain_pct": m.get("gain_pct"), "gain": m.get("gain")}
            for m in movers
        ],
    })


# ── Trading Execution API ─────────────────────────────────────────────────────

_TRADING_PORTFOLIO_ID = None

def get_trading_portfolio_id():
    """Get or create the single trading portfolio."""
    global _TRADING_PORTFOLIO_ID
    if _TRADING_PORTFOLIO_ID:
        return _TRADING_PORTFOLIO_ID
    pm = get_portfolio_mgr()
    portfolios = pm.get_all()
    # Look for existing trading portfolio
    for p in portfolios:
        if p.get("name") == "Trading Account":
            _TRADING_PORTFOLIO_ID = p["id"]
            return _TRADING_PORTFOLIO_ID
    # Create default trading portfolio
    p = pm.create("Trading Account", capital=10000.0)
    _TRADING_PORTFOLIO_ID = p["id"]
    return _TRADING_PORTFOLIO_ID


@app.route("/api/trading/account")
def trading_account():
    """Get the single trading account data."""
    pid = get_trading_portfolio_id()
    pm = get_portfolio_mgr()
    portfolio = pm.get_portfolio(pid)
    if not portfolio:
        return jsonify({"error": "Trading account not found"}), 404
    positions, cash = pm.get_positions_with_returns(pid)
    summary = pm.get_summary(pid, positions, cash)
    risk = pm.calculate_risk_metrics(pid)
    return jsonify({
        "portfolio": portfolio,
        "positions": positions,
        "cash": cash,
        "summary": summary,
        "risk": risk,
    })


@app.route("/api/trading/position-size", methods=["POST"])
def position_size():
    """Calculate optimal position size for a trade."""
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    entry_price = float(data.get("entry_price", 0))
    stop_loss = float(data.get("stop_loss", 0))
    take_profit = float(data.get("take_profit", 0))
    risk_pct = float(data.get("risk_pct", 0.02))

    if not ticker or entry_price <= 0 or stop_loss <= 0:
        return jsonify({"error": "Invalid parameters"}), 400

    pid = get_trading_portfolio_id()
    pm = get_portfolio_mgr()
    positions, _ = pm.get_positions_with_returns(pid)

    # Get sector if we can
    sector = ""
    try:
        info = get_stock_fetcher().get_company_info(ticker)
        sector = info.get("sector", "")
    except Exception:
        pass

    from tools.risk_manager import RiskManager
    rm = RiskManager(total_capital=10000.0)
    result = rm.calculate_position_size(
        ticker=ticker,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_pct=risk_pct,
        current_positions=positions,
        sector=sector,
    )

    return jsonify({
        "ticker": result.ticker,
        "entry_price": result.entry_price,
        "stop_loss": result.stop_loss,
        "take_profit": result.take_profit,
        "risk_per_share": round(result.risk_per_share, 2),
        "reward_per_share": round(result.reward_per_share, 2),
        "risk_reward_ratio": round(result.risk_reward_ratio, 2),
        "suggested_shares": result.suggested_shares,
        "position_value": round(result.position_value, 2),
        "capital_at_risk": round(result.capital_at_risk, 2),
        "capital_at_risk_pct": round(result.capital_at_risk_pct, 2),
        "portfolio_heat_after": round(result.portfolio_heat_after * 100, 1),
        "can_execute": result.can_execute,
        "warning": result.warning,
    })


@app.route("/api/trading/execute", methods=["POST"])
def execute_trade():
    """Execute a buy or sell trade in the trading account."""
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    action = data.get("action", "")  # "buy" or "sell"
    shares = float(data.get("shares", 0))
    price = data.get("price")

    if not ticker or action not in ("buy", "sell") or shares <= 0:
        return jsonify({"error": "Invalid trade parameters"}), 400

    pid = get_trading_portfolio_id()
    pm = get_portfolio_mgr()

    # Auto-fetch price if not provided
    if price is None:
        quote = get_finnhub_fetcher().get_realtime_quote(ticker)
        price = quote.get("price", 0)
    price = float(price)

    if action == "buy":
        pos = pm.add_position(pid, ticker, shares, price)
        # Set default stop/target if provided
        stop = data.get("stop_loss")
        target = data.get("take_profit")
        if stop or target:
            pm.set_position_targets(
                pid, ticker,
                stop_loss=float(stop) if stop else None,
                take_profit=float(target) if target else None,
            )
        return jsonify({"ok": True, "position": pos, "action": "buy", "ticker": ticker, "shares": shares, "price": price})
    else:
        pm.remove_position(pid, ticker.upper())
        return jsonify({"ok": True, "action": "sell", "ticker": ticker, "shares": shares, "price": price})


@app.route("/api/trading/close", methods=["POST"])
def close_position():
    """Close (sell all shares of) a position."""
    data = request.get_json(force=True)
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400

    pid = get_trading_portfolio_id()
    pm = get_portfolio_mgr()
    pm.remove_position(pid, ticker)
    return jsonify({"ok": True, "ticker": ticker, "action": "close"})


@app.route("/api/trading/signal/<ticker>")
def trading_signal(ticker):
    """Get AI signal + technical data for a ticker in one call."""
    from tools.signal_engine import SignalEngine
    from tools.technical_analysis import TechnicalAnalyzer
    from tools.stock_data import StockDataFetcher

    se = SignalEngine()
    sf = StockDataFetcher()

    # Get signal
    signals = se.scan_watchlist([ticker.upper()])
    signal = signals[0] if signals else None

    # Get technicals
    chart_data = sf.get_chart_data(ticker.upper(), "3m")
    technical = {}
    if not chart_data.get("error"):
        import pandas as pd
        df = pd.DataFrame(chart_data["data"])
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
        ta = TechnicalAnalyzer()
        technical = ta.analyze(ticker.upper(), df)

    return jsonify({
        "ticker": ticker.upper(),
        "signal": {
            "action": signal.action if signal else "hold",
            "conviction": signal.conviction if signal else 0,
            "reasoning": signal.reasoning if signal else "No signal generated",
            "trigger_type": signal.trigger_type if signal else "none",
        } if signal else None,
        "technical": {
            "rsi": technical.get("rsi_14"),
            "macd_signal": technical.get("macd_signal"),
            "trend": technical.get("trend"),
            "sma_signal": technical.get("sma_signal"),
            "overall": technical.get("overall_signal"),
        } if technical else {},
        "price": get_finnhub_fetcher().get_realtime_quote(ticker.upper()),
    })


@app.route("/api/trading/risk-check")
def risk_check():
    """Check overall portfolio risk state."""
    pid = get_trading_portfolio_id()
    pm = get_portfolio_mgr()
    positions, _ = pm.get_positions_with_returns(pid)

    # Build sector map
    sector_map = {}
    for p in positions:
        try:
            info = get_stock_fetcher().get_company_info(p["ticker"])
            sector_map[p["ticker"]] = info.get("sector", "Unknown")
        except Exception:
            sector_map[p["ticker"]] = "Unknown"

    from tools.risk_manager import RiskManager
    rm = RiskManager(total_capital=10000.0)
    check = rm.check_portfolio_risk(positions, sector_map)

    return jsonify({
        "can_trade": check.can_trade,
        "reason": check.reason,
        "current_heat": round(check.current_heat * 100, 1),
        "max_heat": round(check.max_heat * 100, 1),
        "sector_exposure": check.sector_exposure,
    })


# ── Background Price Refresh ──────────────────────────────────────────────────

def _refresh_prices():
    """Background thread: refresh price cache every 60s."""
    import threading
    import time

    def loop():
        while True:
            try:
                pm = get_portfolio_mgr()
                portfolios = pm.get_all()
                tickers = set()
                for p in portfolios:
                    for pos in p.get("positions", []):
                        tickers.add(pos["ticker"].upper())
                if not tickers:
                    time.sleep(60)
                    continue

                from tools.price_cache import get_price_cache
                from tools.finnhub_fetcher import FinnhubFetcher
                import yfinance as yf

                cache = get_price_cache()
                prices = {}
                ticker_list = sorted(tickers)

                # Batch yfinance
                try:
                    raw = yf.download(ticker_list, period="5d", interval="1d",
                                     progress=False, auto_adjust=True, threads=False)["Close"]
                    if isinstance(raw, pd.Series):
                        raw = raw.to_frame(name=ticker_list[0])
                    for t in ticker_list:
                        if t in raw.columns:
                            series = raw[t].dropna()
                            if not series.empty:
                                prices[t] = {"price": float(series.iloc[-1])}
                except Exception:
                    pass

                # Finnhub for missing
                missing = [t for t in ticker_list if t not in prices]
                if missing:
                    try:
                        fh = FinnhubFetcher()
                        for t in missing:
                            try:
                                q = fh.get_realtime_quote(t)
                                if q.get("price") and q["price"] > 0:
                                    prices[t] = {
                                        "price": float(q["price"]),
                                        "change": q.get("change"),
                                        "change_percent": q.get("change_percent"),
                                    }
                            except Exception:
                                pass
                    except Exception:
                        pass

                if prices:
                    cache.set_batch(prices)
            except Exception as e:
                print(f"[price-refresh] error: {e}")
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True, name="price-refresh")
    t.start()
    print("[price-refresh] background thread started")


# Start background price refresh (runs once per worker process)
_refresh_prices()


# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_finnhub = bool(os.getenv("FINNHUB_API_KEY"))
    print("\n" + "="*50)
    print("  THE PILL v2.0 - Shkreli Method Stock Analysis")
    print("="*50)
    if not has_anthropic:
        print("\n  Note: No ANTHROPIC_API_KEY found.")
        print("        AI analysis will use a structured fallback.")
    if not has_finnhub:
        print("\n  Note: No FINNHUB_API_KEY found.")
        print("        Real-time prices will use Yahoo Finance (slight delay).")
    print("\n  http://localhost:8080\n")
    app.run(debug=True, host="0.0.0.0", port=8080, threaded=True)
