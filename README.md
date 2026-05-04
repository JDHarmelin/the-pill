# THE PILL

**Shkreli Method Stock Analysis — v2.0**

A local web application that runs rigorous fundamental analysis on any publicly traded company using the "Shkreli Method" — a ground-up financial modeling approach that prioritizes raw SEC data and cash flow over GAAP earnings.

---

## Features

- **Clean, Minimal UI** — Black screen with a simple search bar. Type any ticker.
- **Interactive Price Chart** — TradingView-style area chart with 1M / 3M / 6M / 1Y ranges
- **Real-Time Prices** — Live quotes via Finnhub API (falls back to Yahoo Finance)
- **Fundamental Data Engine** — Income statement, balance sheet, cash flow (cards + raw tables)
- **Earnings Calendar** — Historical EPS estimates vs actuals with surprise %
- **Institutional Holders** — Top holders with position sizes and values
- **Technical Analysis** — RSI, MACD, Bollinger, SMA, ATR, trend detection, composite signal
- **SEC Filings** — Recent 10-K, 10-Q, 8-K with direct EDGAR links
- **Peers** — Sector/industry peer comparison
- **Portfolio Management** — SQLite-backed portfolios with positions, trades, NAV tracking
- **AI-Powered Analysis** — Claude-powered 5-phase Shkreli Method (structured fallback without key)
- **Mac Launcher** — Double-click `The Pill.command` to start instantly

---

## The Shkreli Method

1. **The Six Important Things** — Stock price, shares outstanding, market cap, cash, debt, enterprise value
2. **Income Statement Analysis** — Longitudinal quarterly data, margins, operating income
3. **Cash Flow Truth** — Reconcile GAAP to actual cash flow (D&A, SBC, deferred taxes)
4. **Balance Sheet Liquidity** — Assets by liquidity, goodwill check, fundamental equation
5. **Qualitative Checks** — Organic vs inorganic growth, segment analysis, valuation

---

## Quick Start (Mac)

**Double-click `The Pill.command`** — it handles everything automatically.

Or run manually:

```bash
source venv/bin/activate
python app.py
# Open http://localhost:5000
```

---

## Setup

### Prerequisites
- Python 3.9+
- (Optional) Anthropic API key — [console.anthropic.com](https://console.anthropic.com/)
- (Optional) Finnhub API key — [finnhub.io](https://finnhub.io/) (free tier works)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your API keys (optional — app works without them)
```

---

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | No — falls back to structured diagnostic |
| `FINNHUB_API_KEY` | Your Finnhub API key | No — falls back to Yahoo Finance |
| `DATABASE_URL` | SQLite DB path for portfolios | No — defaults to `portfolios.db` |

---

## Deployment

The app ships with a `Procfile` configured for **gunicorn + gevent** workers.

### Heroku / Railway / Render

```bash
# Set environment variables on your platform
database_url: sqlite:///data/portfolios.db   # Use a persistent disk mount
anthropic_api_key: sk-ant-...
finnhub_api_key: c...

# Deploy
git push heroku main   # or equivalent for your platform
```

> **Note:** Heroku's filesystem is ephemeral. Use a persistent volume for `DATABASE_URL` or accept that portfolio data resets on dyno restart.

### Self-Hosted (VPS / Raspberry Pi)

```bash
pip install -r requirements.txt
gunicorn app:app --worker-class gevent --timeout 300 --workers 2 --bind 0.0.0.0:5000
```

---

## Project Structure

```
the-pill/
├── app.py                      # Main Flask application + SSE streaming
├── db.py                       # SQLite portfolio database
├── The Pill.command            # macOS double-click launcher
├── requirements.txt            # Python dependencies
├── Procfile                    # Deployment config (gunicorn + gevent)
├── .env.example                # Environment template
├── .env                        # Your API keys (create from .env.example)
├── templates/
│   ├── index.html              # Ticker page (9 tabs)
│   ├── dashboard.html          # Portfolio dashboard
│   └── portfolio.html          # Portfolio manager
├── tools/
│   ├── finnhub_fetcher.py      # Finnhub real-time prices
│   ├── sec_fetcher.py          # SEC EDGAR filings
│   ├── stock_data.py           # Yahoo Finance data
│   ├── technical_analysis.py   # Pure-Python TA engine
│   ├── portfolio_manager.py    # SQLite portfolio CRUD
│   └── signal_engine.py        # Rebalance / alert engine
└── tests/
    └── unit/                   # pytest suite
```

---

## Disclaimers

- **Not Financial Advice** — Educational purposes only
- **Data Sources** — Finnhub (real-time), Yahoo Finance, and SEC EDGAR
- **API Costs** — Running analyses uses your Anthropic API credits
- **Rate Limits** — SEC EDGAR has rate limits; don't spam requests

---

## Credits

- Methodology inspired by Martin Shkreli's financial analysis approach
- Built with [Flask](https://flask.palletsprojects.com/), [Anthropic Claude](https://anthropic.com/), [yfinance](https://github.com/ranaroussi/yfinance), [Finnhub](https://finnhub.io/), [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts)
- SEC data from [EDGAR](https://www.sec.gov/edgar)

---

**Made for better investment decisions. Not financial advice.**
