# The Pill — AI Trading Agent Optimization Plan
## From Stock Analyzer → Personal AI Fund Manager

---

## Executive Summary

Transform The Pill from a single-ticker fundamental analyzer into a fully-fledged personal AI trading agent and portfolio management system. The core "Shkreli Method" DNA (capital structure first, cash flow truth, skeptical fundamental analysis) remains central, but the system gains:

- **Multi-asset portfolio intelligence** with real-time P&L, risk metrics, and rebalancing
- **Technical + Fundamental fusion analysis** with automated signal generation
- **AI-driven trade recommendations** with conviction scoring
- **Backtesting engine** for strategy validation
- **Professional trading dashboard** with sector allocation, drawdown analysis, and correlation matrices
- **Watchlist & alert system** for systematic idea generation

---

## Phase 1: Core Portfolio Data Model (Week 1)

### 1.1 Enhanced Position Model
**Current:** Simple `{ticker, shares, avg_cost, added_date}`
**Upgrade to:**
```python
{
  "ticker": "AAPL",
  "shares": 100.0,
  "avg_cost": 175.50,
  "added_date": "2025-01-15",
  "tags": ["core", "dividend"],           # Custom tags for grouping
  "target_weight": 0.15,                   # Target portfolio allocation
  "stop_loss": 160.00,                     # Auto-calculated or user-set
  "take_profit": 220.00,                   # Profit target
  "notes": "AI thesis: services growth",
  "trade_history": [                       # Full audit trail
    {"date": "2025-01-15", "action": "buy", "shares": 50, "price": 170.00},
    {"date": "2025-02-20", "action": "buy", "shares": 50, "price": 181.00}
  ]
}
```

### 1.2 Portfolio-Level Metadata
- **Strategy type:** `thematic` | `factor` | `dividend` | `momentum` | `value` | `custom`
- **Rebalance schedule:** Manual, weekly, monthly, quarterly
- **Benchmark:** SPY, QQQ, or custom (default: SPY)
- **Risk tolerance:** Conservative (max 10% drawdown), Moderate (20%), Aggressive (35%)
- **Cash drag threshold:** Auto-invest cash above $X

### 1.3 Data Persistence Upgrade
**Current:** JSON file (`portfolios.json`)
**Upgrade options:**
- **SQLite** for local durability, queryability, and historical tracking
- Keep JSON as export/import format
- Schema: `portfolios`, `positions`, `trades`, `snapshots` (daily NAV), `alerts`

### 1.4 Historical NAV Tracking
- Store daily portfolio value snapshots for true performance attribution
- Enable drawdown analysis, rolling returns, and benchmark comparison
- Track cash flows (deposits/withdrawals) for accurate IRR calculation

---

## Phase 2: Dashboard UI/UX Overhaul (Week 1-2)

### 2.1 Global Dashboard (`/dashboard`)
New landing page replacing the search-only homepage:

```
┌─────────────────────────────────────────────────────────────┐
│  THE PILL.                              [Search] [Alerts]   │
├─────────────────────────────────────────────────────────────┤
│  TOTAL AUM    DAY P&L    UNREALIZED    REALIZED    CASH     │
│  $284,532    +$1,240      +$12,400     +$3,200   $24,100   │
├─────────────────────────────────────────────────────────────┤
│  [Portfolio Performance Chart — vs SPY benchmark]          │
├──────────────────┬──────────────────────────────────────────┤
│  ALLOCATION      │  SECTOR BREAKDOWN                        │
│  [Pie chart]     │  [Horizontal bars]                       │
├──────────────────┼──────────────────────────────────────────┤
│  TOP MOVERS      │  RISK METRICS                            │
│  [Today]         │  Vol: 14.2%  Beta: 1.08  Sharpe: 1.24   │
│  [This Week]     │  Max DD: -8.3%  Var95: -2.1%             │
├──────────────────┴──────────────────────────────────────────┤
│  ACTIVE POSITIONS          │  WATCHLIST / AI SIGNALS         │
│  [Sortable table]            │  [Signal cards]                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Position Table Enhancements
- Sortable by: P&L %, weight, sector, conviction score
- Inline actions: Edit, close position, view analysis
- Color-coded health: Green (on thesis), Yellow (watch), Red (stop loss breached)
- Quick-add from watchlist with 1-click

### 2.3 Sector & Factor Exposure
- Automatic sector classification via yfinance/Finnhub
- Factor exposure estimation (value, growth, momentum, quality)
- Concentration alerts (e.g., "Tech exposure > 40%")

### 2.4 Mobile-Responsive Grid
- Collapsible cards for small screens
- Swipe actions on positions
- Quick-view bottom sheet for signal details

---

## Phase 3: Advanced Analysis Integration (Week 2-3)

### 3.1 Technical Indicator Engine (`tools/technical_analysis.py`)
New module computing standard signals:

```python
class TechnicalAnalyzer:
    def analyze(self, ticker, prices_df) -> dict:
        return {
            "sma_20_50_cross": "bullish",      # Golden cross / death cross
            "rsi_14": 62.5,                     # Overbought >70, Oversold <30
            "macd": {"signal": "buy", "histogram": 0.45},
            "bollinger": {"position": "upper", "bandwidth": 0.12},
            "volume_trend": "increasing",      # Accumulation/distribution
            "support_resistance": {"support": 168, "resistance": 195},
            "trend": "uptrend"                  # Higher highs, higher lows
        }
```

**Libraries:** `pandas-ta` or `ta-lib` via lightweight pure-Python implementations

### 3.2 Fundamental + Technical Fusion Score
For each position, compute a **Conviction Score** (0-100):

| Component | Weight | Source |
|-----------|--------|--------|
| Shkreli Method Grade | 30% | AI analysis output (A-F) |
| Technical Momentum | 25% | RSI, MACD, trend alignment |
| Valuation Gap | 20% | P/E vs sector, DCF implied |
| Earnings Quality | 15% | Cash flow / Net income ratio |
| Risk Adjusted Return | 10% | Sharpe, max drawdown |

**Signal generation:**
- **Strong Buy:** Score ≥ 80, technical + fundamental aligned
- **Buy:** Score 60-79
- **Hold:** Score 40-59
- **Reduce:** Score 20-39
- **Sell:** Score < 20 or stop loss triggered

### 3.3 Correlation & Diversification Analysis
- Portfolio correlation matrix (heatmap)
- Beta-adjusted position sizing recommendations
- "Overlap detector" — warn if two positions are >0.85 correlated
- Diversification score vs benchmark

### 3.4 AI-Enhanced Watchlist (`/api/watchlist`)
- User-defined and AI-suggested watchlists
- Each watchlist entry carries: ticker, added_date, signal_status, conviction, notes
- Auto-crawl: "Stocks with improving cash flow + bullish technicals"

---

## Phase 4: Trading Strategy & Automation Module (Week 3-4)

### 4.1 Signal Engine (`tools/signal_engine.py`)
Continuously evaluates all positions + watchlist:

```python
class SignalEngine:
    def generate_signals(self, portfolio_id) -> list[Signal]:
        # Runs daily or on-demand
        # Returns actionable signals with reasoning
        pass

@dataclass
class Signal:
    ticker: str
    action: "buy" | "sell" | "reduce" | "add"
    conviction: int           # 0-100
    trigger_type: "technical" | "fundamental" | "risk" | "rebalance"
    reasoning: str            # Human-readable explanation
    suggested_shares: float     # Position size recommendation
    metadata: dict            # Raw indicator values
```

### 4.2 Rebalancing Engine
- **Target-weight rebalance:** Bring positions back to target allocation
- **Risk-parity rebalance:** Equal risk contribution across positions
- **AI-suggested rebalance:** Based on conviction score changes
- Generates a "Rebalance Plan" with specific buy/sell orders

### 4.3 Backtesting Framework (`tools/backtest_engine.py`)
```python
class BacktestEngine:
    def run(self, strategy, start_date, end_date, initial_capital) -> BacktestResult:
        # Strategy: dict of rules (entry/exit conditions)
        # Returns: equity curve, trades, metrics
        pass
```

**Built-in strategies to backtest:**
1. **Shkreli Value:** Buy when EV/EBITDA < sector median + positive FCF
2. **Momentum + Quality:** Buy top quintile momentum + ROE > 15%
3. **AI Conviction:** Only enter positions with conviction ≥ 70
4. **Custom:** User-defined rule builder

**Metrics:** CAGR, Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor

### 4.4 Paper Trading Simulation
- Track hypothetical trades in a separate "paper portfolio"
- Compare live portfolio vs paper strategy vs benchmark
- A/B test different strategies before committing capital

---

## Phase 5: Infrastructure & API Enhancements (Week 2-4)

### 5.1 New API Endpoints

```
GET  /api/dashboard                  → Global summary + recent signals
GET  /api/watchlist                  → All watchlists + signals
POST /api/watchlist                  → Add ticker to watchlist
GET  /api/signals?portfolio_id=xxx   → Active signals for portfolio
POST /api/rebalance/{pid}            → Generate rebalance plan
POST /api/backtest                   → Run strategy backtest
GET  /api/correlation/{pid}            → Position correlation matrix
GET  /api/performance/{pid}          → Detailed performance attribution
```

### 5.2 Scheduled Jobs (using APScheduler or cron)
- **Daily 9 AM:** Refresh all positions, recalculate risk metrics
- **Daily 4:30 PM:** Store NAV snapshot, check for signals
- **Weekly Sunday:** Generate weekly performance report, rebalance suggestions
- **Monthly:** Full AI portfolio review (like a quarterly letter)

### 5.3 Alert System
- WebSocket or SSE stream for real-time alerts
- Alert types: Price target hit, stop loss, signal generated, earnings date, concentration risk
- Configurable: Push via browser notification, email, or just in-app

### 5.4 Caching & Performance
- Redis or in-memory cache for price data (currently using yfinance cache)
- Batch API calls to Finnhub for multi-ticker quotes
- Background prefetch for watchlist prices

---

## Phase 6: AI Agent Upgrades (Week 3-4)

### 6.1 Portfolio-Aware Analysis
When analyzing a ticker, the AI knows:
- "You already own 5% of your portfolio in NVDA"
- "Adding TSM would increase your semiconductor exposure to 28%"
- "This would violate your target weight for tech (25%)"

### 6.2 Weekly AI Portfolio Review
Auto-generated every Sunday:
- Performance vs benchmark
- What worked, what didn't (attribution)
- New signals and opportunities
- Risk concentration warnings
- Action items for the week

### 6.3 Strategy Backtest Summarization
Feed backtest results to Claude for natural language interpretation:
- "This strategy had a 14% CAGR but a brutal 35% drawdown in March 2024"
- "The win rate is only 42%, but the average winner is 3x the average loser"

---

## Phase 7: UI/UX Polish & Theming (Week 4)

### 7.1 "Pill" Branding Consistency
- Dark theme with the existing black/white/neon green palette
- Pill-shaped buttons and badges
- Subtle pill iconography in empty states and loaders
- "Swallow the pill" onboarding flow for new users

### 7.2 Keyboard Shortcuts
- `/` — Focus search
- `Esc` — Close modal/chart
- `1-5` — Switch dashboard tabs
- `B` — Buy modal on selected position
- `S` — Sell modal

### 7.3 Export & Reporting
- PDF portfolio report generation
- CSV export of trades, positions, performance
- Tax lot reporting (FIFO/LIFO)

---

## Implementation Priority

### MVP (Week 1-2) — Must Have
1. Enhanced position model with tags, targets, stop losses
2. SQLite migration for portfolios
3. Global dashboard with AUM, P&L, allocation pie
4. Technical indicator engine (RSI, MACD, SMA)
5. Conviction score calculation
6. New API endpoints: `/dashboard`, `/watchlist`, `/signals`

### V1.5 (Week 2-3) — Should Have
7. Correlation matrix and diversification analysis
8. Rebalancing engine with target-weight logic
9. Signal engine with daily scanning
10. Backtesting framework with 3 built-in strategies
11. Weekly AI portfolio review
12. Alert system (in-app notifications)

### V2.0 (Week 3-4) — Nice to Have
13. Paper trading simulation
14. Mobile-responsive dashboard overhaul
15. PDF reporting and CSV export
16. WebSocket real-time price streaming
17. Custom strategy builder UI
18. AI portfolio-aware analysis context

---

## Technical Dependencies

| Library | Purpose |
|---------|---------|
| `sqlite3` (stdlib) | Local database |
| `pandas-ta` | Technical indicators |
| `APScheduler` | Scheduled jobs |
| `flask-sock` or `flask-sse` | Real-time alerts |
| `reportlab` or `weasyprint` | PDF generation |
| `pytest` | Test suite (currently missing) |

---

## Success Metrics

- **Analysis depth:** Can explain WHY a position should be reduced, not just that it should
- **Signal accuracy:** Backtested win rate > 55% for conviction ≥ 70 signals
- **Risk management:** Max portfolio drawdown stays within configured tolerance 90% of days
- **User efficiency:** Can review entire portfolio health in < 60 seconds
- **Data freshness:** All prices < 5 minutes old during market hours

---

## Anti-Patterns to Avoid

1. **Don't** build a real brokerage API integration (out of scope, compliance nightmare)
2. **Don't** store real money or execute real trades — paper tracking only
3. **Don't** invent technical indicators — use established `ta-lib` equivalents
4. **Don't** over-engineer the database — SQLite is sufficient for personal use
5. **Don't** lose the "Shkreli Method" identity — fundamentals remain primary

---

*Plan version: 1.0*
*Last updated: 2026-05-03*
