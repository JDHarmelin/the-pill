"""
AI prompt templates for portfolio-aware analysis.
"""

from datetime import datetime
from typing import Optional

# ── Sector cache (module-level to avoid repeated yfinance calls) ──────────────
_sector_cache: dict[str, str] = {}


def _get_sector(ticker: str) -> str:
    """Lightweight sector lookup via yfinance (cached)."""
    if ticker in _sector_cache:
        return _sector_cache[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        sector = info.get("sector", "Unknown") or "Unknown"
    except Exception:
        sector = "Unknown"
    _sector_cache[ticker] = sector
    return sector


def _build_positions_table(positions: list[dict]) -> str:
    lines = ["| Ticker | Shares | Avg Cost | Current | Value | Gain |", "|--------|--------|----------|---------|-------|------|"]
    for pos in positions:
        lines.append(
            f"| {pos['ticker']} | {pos.get('shares', 'N/A')} | "
            f"${pos.get('avg_cost', 'N/A')} | ${pos.get('current_price', 'N/A')} | "
            f"${pos.get('current_value', 'N/A')} | {pos.get('gain_pct', 'N/A')}% |"
        )
    return "\n".join(lines)


def _build_sector_table(positions: list[dict]) -> str:
    if not positions:
        return "No positions."
    sector_map: dict[str, float] = {}
    total_value = sum(p.get("current_value") or p.get("cost_basis", 0) for p in positions)
    if total_value <= 0:
        return "No position values available."
    for pos in positions:
        sector = _get_sector(pos["ticker"])
        value = pos.get("current_value") or pos.get("cost_basis", 0)
        sector_map[sector] = sector_map.get(sector, 0) + value
    lines = ["| Sector | Value | Weight |", "|--------|-------|--------|"]
    for sector, value in sorted(sector_map.items(), key=lambda x: x[1], reverse=True):
        weight = round(value / total_value * 100, 2)
        lines.append(f"| {sector} | ${round(value, 2)} | {weight}% |")
    return "\n".join(lines)


def _compute_tech_weight(positions: list[dict]) -> float:
    total_value = sum(p.get("current_value") or p.get("cost_basis", 0) for p in positions)
    if total_value <= 0:
        return 0.0
    tech_value = sum(
        (p.get("current_value") or p.get("cost_basis", 0))
        for p in positions
        if _get_sector(p["ticker"]) == "Technology"
    )
    return round(tech_value / total_value * 100, 2)


def _compute_max_drawdown(summary: dict) -> str:
    # Max drawdown not currently computed in PortfolioManager; placeholder
    return "N/A"


# ── Prompt Templates ──────────────────────────────────────────────────────────

PORTFOLIO_CONTEXT_TEMPLATE = """## Portfolio Context (if available)

Total AUM: ${total_value}
Cash Available: ${cash}
Number of Positions: {position_count}

Current Holdings:
{positions_table}

Risk Profile:
- Portfolio Volatility: {volatility}%
- Beta vs S&P 500: {beta}
- Sharpe Ratio: {sharpe}
- Max Drawdown (current): {max_drawdown}%

Sector Concentration:
{sector_table}

### Constraints & Rules
- You already have {tech_weight}% in Technology. Adding more tech would exceed your 30% sector limit.
- Your risk tolerance is {risk_tolerance}. Max single position: {max_position_pct}%.
- Cash drag target: Keep cash below 10% of AUM.
"""

WEEKLY_REVIEW_PROMPT = """You are the Portfolio Manager AI for "The Pill." Write a weekly letter to the investor.

Date: {date}

## Portfolio Performance This Week
{performance_summary}

## Key Metrics
{metrics}

## Positions That Moved
{movers}

## Risk Flags
{risk_flags}

## Market Context
{market_summary}

Write in the voice of a sharp, no-BS hedge fund manager. Be specific about what worked, what didn't, and what actions to take. Include:
1. Executive Summary (3 bullets)
2. Performance Attribution (what drove returns)
3. Risk Review (any concentration or drawdown concerns)
4. Action Items for Next Week (specific tickers and actions)
5. New Ideas (1-2 opportunities with conviction)

Format in clean Markdown. No fluff.
"""

BACKTEST_INTERPRETATION_PROMPT = """Interpret these backtest results for a non-technical investor:

Strategy: {strategy_name}
Period: {start_date} to {end_date}
Initial Capital: ${initial_capital}

Results:
- Total Return: {total_return_pct}%
- CAGR: {cagr}
- Sharpe Ratio: {sharpe}
- Max Drawdown: {max_drawdown_pct}%
- Win Rate: {win_rate}
- Profit Factor: {profit_factor}
- Total Trades: {total_trades}
- Benchmark Return: {benchmark_return_pct}%
- Alpha: {alpha}
- Beta: {beta}

Top 5 Trades:
{top_trades}

Write 3 short paragraphs:
1. "The bottom line" — would you recommend this strategy?
2. "The good and bad" — what worked and what hurt
3. "The verdict" — who is this strategy for?
"""

TRADE_IDEA_PROMPT = """You are evaluating a new trade idea for "The Pill" portfolio.

Ticker: {ticker}

Portfolio Context:
{portfolio_context}

Technical Data:
{technical_data}

Analyze:
1. Does this fit the portfolio's current risk profile and sector constraints?
2. What position size would be appropriate given cash and concentration limits?
3. Any red flags or catalysts to watch?
4. Verdict: Buy, Pass, or Watch — with specific price levels if applicable.

Be concise and data-driven.
"""


# ── Builder Functions ───────────────────────────────────────────────────────

def build_portfolio_context(portfolio_data: dict) -> str:
    """
    Given portfolio data from PortfolioManager.get_summary() + positions,
    build a context block the AI can use.
    """
    portfolio = portfolio_data.get("portfolio", {})
    positions = portfolio_data.get("positions", [])
    cash = portfolio_data.get("cash", 0)
    summary = portfolio_data.get("summary", {})
    risk = summary.get("risk", {})

    total_value = summary.get("total_value", portfolio.get("capital", 0))
    position_count = len(positions)
    positions_table = _build_positions_table(positions)
    sector_table = _build_sector_table(positions)
    tech_weight = _compute_tech_weight(positions)

    # Estimate max position weight
    max_position_pct = 0.0
    if total_value > 0 and positions:
        max_position_pct = max(
            ((p.get("current_value") or p.get("cost_basis", 0)) / total_value * 100)
            for p in positions
        )
        max_position_pct = round(max_position_pct, 2)

    return PORTFOLIO_CONTEXT_TEMPLATE.format(
        total_value=round(total_value, 2),
        cash=round(cash, 2),
        position_count=position_count,
        positions_table=positions_table,
        volatility=risk.get("volatility", "N/A"),
        beta=risk.get("beta", "N/A"),
        sharpe=risk.get("sharpe", "N/A"),
        max_drawdown=_compute_max_drawdown(summary),
        sector_table=sector_table,
        tech_weight=tech_weight,
        risk_tolerance="moderate",
        max_position_pct=max_position_pct,
    )


def build_weekly_review_prompt(portfolios: list[dict], market_summary: str) -> str:
    """Generate the prompt for the weekly AI portfolio review."""
    performance_lines = []
    metrics_lines = []
    movers_lines = []
    risk_lines = []

    for data in portfolios:
        p = data.get("portfolio", {})
        positions = data.get("positions", [])
        summary = data.get("summary", {})
        risk = summary.get("risk", {})

        name = p.get("name", p.get("id", "Unnamed"))
        performance_lines.append(
            f"- **{name}**: ${summary.get('total_value', 'N/A')} total value, "
            f"{summary.get('total_gain_pct', 'N/A')}% total return, "
            f"${summary.get('cash', 'N/A')} cash"
        )

        metrics_lines.append(
            f"- {name}: Vol {risk.get('volatility', 'N/A')}%, Beta {risk.get('beta', 'N/A')}, "
            f"Sharpe {risk.get('sharpe', 'N/A')}"
        )

        # Movers: top 3 gainers and losers by gain_pct
        sorted_positions = sorted(
            [pos for pos in positions if pos.get("gain_pct") is not None],
            key=lambda x: x.get("gain_pct", 0),
            reverse=True,
        )
        if sorted_positions:
            top = sorted_positions[:3]
            bottom = sorted_positions[-3:]
            for pos in top:
                movers_lines.append(
                    f"- {pos['ticker']}: +{pos['gain_pct']}% (${pos.get('current_value', 'N/A')})"
                )
            for pos in bottom:
                movers_lines.append(
                    f"- {pos['ticker']}: {pos['gain_pct']}% (${pos.get('current_value', 'N/A')})"
                )

        # Risk flags
        total_value = summary.get("total_value", 1)
        cash = summary.get("cash", 0)
        cash_pct = (cash / total_value * 100) if total_value else 0
        if cash_pct > 10:
            risk_lines.append(f"- {name}: Cash drag at {round(cash_pct, 1)}% (target <10%)")
        tech_weight = _compute_tech_weight(positions)
        if tech_weight > 30:
            risk_lines.append(f"- {name}: Tech concentration at {tech_weight}% (limit 30%)")
        if risk.get("volatility", 0) > 30:
            risk_lines.append(f"- {name}: High volatility at {risk['volatility']}%")
        if risk.get("sharpe", 0) < 0.5 and risk.get("sharpe") is not None:
            risk_lines.append(f"- {name}: Low Sharpe ratio at {risk['sharpe']}")

    if not performance_lines:
        performance_lines = ["No portfolio data available."]
    if not metrics_lines:
        metrics_lines = ["No metrics available."]
    if not movers_lines:
        movers_lines = ["No significant movers."]
    if not risk_lines:
        risk_lines = ["No major risk flags."]

    return WEEKLY_REVIEW_PROMPT.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        performance_summary="\n".join(performance_lines),
        metrics="\n".join(metrics_lines),
        movers="\n".join(movers_lines),
        risk_flags="\n".join(risk_lines),
        market_summary=market_summary or "No market summary provided.",
    )


def build_backtest_interpretation_prompt(backtest_result: dict) -> str:
    """Generate prompt for Claude to interpret backtest results in plain English."""
    top_trades = backtest_result.get("top_trades", [])
    if top_trades:
        trade_lines = []
        for trade in top_trades[:5]:
            trade_lines.append(
                f"- {trade.get('ticker', 'N/A')}: {trade.get('action', 'N/A')} "
                f"${trade.get('pnl', 'N/A')} ({trade.get('return_pct', 'N/A')}%)")
        top_trades_str = "\n".join(trade_lines)
    else:
        top_trades_str = "No trade details available."

    return BACKTEST_INTERPRETATION_PROMPT.format(
        strategy_name=backtest_result.get("strategy_name", "Unknown"),
        start_date=backtest_result.get("start_date", "N/A"),
        end_date=backtest_result.get("end_date", "N/A"),
        initial_capital=backtest_result.get("initial_capital", "N/A"),
        total_return_pct=backtest_result.get("total_return_pct", "N/A"),
        cagr=backtest_result.get("cagr", "N/A"),
        sharpe=backtest_result.get("sharpe", "N/A"),
        max_drawdown_pct=backtest_result.get("max_drawdown_pct", "N/A"),
        win_rate=backtest_result.get("win_rate", "N/A"),
        profit_factor=backtest_result.get("profit_factor", "N/A"),
        total_trades=backtest_result.get("total_trades", "N/A"),
        benchmark_return_pct=backtest_result.get("benchmark_return_pct", "N/A"),
        alpha=backtest_result.get("alpha", "N/A"),
        beta=backtest_result.get("beta", "N/A"),
        top_trades=top_trades_str,
    )


def build_trade_idea_prompt(ticker: str, portfolio_context: str, technical_data: dict) -> str:
    """Generate prompt for evaluating a new trade idea in portfolio context."""
    tech_block = ""
    if technical_data:
        for key, value in technical_data.items():
            tech_block += f"- {key}: {value}\n"
    else:
        tech_block = "No technical data provided."

    return TRADE_IDEA_PROMPT.format(
        ticker=ticker.upper(),
        portfolio_context=portfolio_context or "No portfolio context provided.",
        technical_data=tech_block,
    )


# ── Interpretation Helper ─────────────────────────────────────────────────────

def interpret_backtest(backtest_result: dict, client: Optional[object] = None) -> str:
    """Send backtest results to Claude for natural language summary."""
    prompt = build_backtest_interpretation_prompt(backtest_result)

    if client is None:
        try:
            import os
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        except Exception:
            return "[Backtest interpretation unavailable: Claude client not configured.]"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system="You are a sharp, no-BS hedge fund manager explaining backtest results.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "")
            for b in response.content
            if getattr(b, "type", "") == "text"
        )
    except Exception as exc:
        return f"[Backtest interpretation failed: {exc}]"
