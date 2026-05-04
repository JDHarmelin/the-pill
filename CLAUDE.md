# The Pill — Shkreli Method Stock Analysis

## What This Is
A local Flask web app that runs AI-powered fundamental stock analysis using the Martin Shkreli methodology. Users enter a ticker, and Claude fetches live data and produces a 5-phase analysis (capital structure, income statement, cash flow truth, balance sheet, qualitative checks).

## Architecture
- `app.py` — Flask app, SSE streaming, tool dispatch, `SHKRELI_SYSTEM_PROMPT`, chart endpoint
- `tools/finnhub_fetcher.py` — Real-time prices via Finnhub API
- `tools/sec_fetcher.py` — SEC EDGAR 10-K/10-Q fetching (XBRL facts)
- `tools/stock_data.py` — Yahoo Finance via yfinance (financials, chart data)
- `templates/index.html` — Single-page frontend (search + chart + streaming analysis)
- `The Pill.command` — macOS double-click launcher

## Running Locally
```bash
# Double-click "The Pill.command" in Finder (recommended)
# Or manually:
source venv/bin/activate
python app.py
# Opens at http://localhost:5000
```

## Environment
Requires `.env` (copy from `.env.example`):
- `ANTHROPIC_API_KEY` — from console.anthropic.com
- `FINNHUB_API_KEY` — from finnhub.io (free tier works)

## Key Patterns
- Analysis uses SSE streaming via `/analyze/stream?ticker=AAPL`
- Chart data served from `/api/chart/<ticker>?range=1y`
- TradingView Lightweight Charts renders the interactive price chart in the frontend
- Claude model: `claude-sonnet-4-20250514` with 8192 max_tokens and tool use
- Python venv in `venv/` — never modify system Python
