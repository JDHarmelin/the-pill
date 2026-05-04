"""
Signal Engine — generates buy/sell/hold signals for portfolio positions.
"""

from dataclasses import dataclass, field
from typing import Optional
import yfinance as yf
import pandas as pd

from tools.technical_analysis import TechnicalAnalyzer
from tools.stock_data import StockDataFetcher


@dataclass
class Signal:
    ticker: str
    action: str  # "strong_buy" | "buy" | "hold" | "reduce" | "sell" | "strong_sell"
    conviction: int  # 0-100 (can be negative for strong sells)
    trigger_type: str  # "technical" | "fundamental" | "risk" | "rebalance" | "stop_loss" | "take_profit"
    reasoning: str
    suggested_shares: Optional[float] = None
    current_price: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class SignalEngine:
    def __init__(self):
        self.technical_analyzer = TechnicalAnalyzer()
        self.stock_fetcher = StockDataFetcher()

    def scan_portfolio(self, portfolio_id: str, portfolio_mgr) -> list[Signal]:
        """Scan all positions in a portfolio and generate signals."""
        portfolio = portfolio_mgr.get_portfolio(portfolio_id)
        if not portfolio:
            return []

        positions, cash = portfolio_mgr.get_positions_with_returns(portfolio_id)
        summary = portfolio_mgr.get_summary(portfolio_id, positions, cash)

        signals = []
        for pos in positions:
            pos_data = {
                "position": pos,
                "cash": cash,
                "summary": summary,
                "portfolio": portfolio,
                "all_positions": positions,
            }
            signal = self.generate_signal(pos["ticker"], pos_data)
            signals.append(signal)
        return signals

    def scan_watchlist(self, tickers: list[str]) -> list[Signal]:
        """Scan watchlist tickers for entry signals."""
        signals = []
        for ticker in tickers:
            signals.append(self.generate_signal(ticker))
        return signals

    def generate_signal(self, ticker: str, position_data: dict = None) -> Signal:
        """Generate a single signal for a ticker."""
        ticker = ticker.upper()

        # Fetch price history once and reuse
        hist = self._fetch_history(ticker)

        # Technical analysis
        technical_data = {}
        if hist is not None and len(hist) >= 20:
            try:
                ta_result = self.technical_analyzer.analyze(ticker, hist)
                if "error" not in ta_result:
                    technical_data = ta_result
            except Exception:
                technical_data = {}

        # Fundamental data
        fundamental_data = self.stock_fetcher.get_key_metrics(ticker)
        if "error" in fundamental_data:
            fundamental_data = {}

        # Risk data
        risk_data = self._calculate_risk_data(ticker, hist)

        # Calculate conviction
        conviction, action, reasoning, trigger_type = self._calculate_conviction(
            technical_data, fundamental_data, risk_data, position_data
        )

        # Get current price
        current_price = None
        if position_data and position_data.get("position"):
            current_price = position_data["position"].get("current_price")
        if current_price is None and hist is not None and not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
        if current_price is None:
            quote = self.stock_fetcher.get_quote(ticker)
            current_price = quote.get("price")

        # Suggested shares
        suggested_shares = None
        if position_data and position_data.get("position") and current_price and current_price > 0:
            pos = position_data["position"]
            summary = position_data.get("summary", {})
            total_value = summary.get("total_value", 0)
            if total_value and total_value > 0:
                if action in ("strong_buy", "buy"):
                    target_value = total_value * 0.02
                    suggested_shares = round(target_value / current_price, 4)
                elif action in ("reduce", "sell", "strong_sell"):
                    current_shares = float(pos.get("shares", 0))
                    if action in ("sell", "strong_sell"):
                        suggested_shares = round(current_shares, 4)
                    else:
                        suggested_shares = round(current_shares * 0.5, 4)

        return Signal(
            ticker=ticker,
            action=action,
            conviction=conviction,
            trigger_type=trigger_type,
            reasoning=reasoning,
            suggested_shares=suggested_shares,
            current_price=round(current_price, 2) if current_price else None,
        )

    def _fetch_history(self, ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        try:
            hist = yf.Ticker(ticker).history(period=period, interval="1d")
            if hist.empty:
                return None
            return hist
        except Exception:
            return None

    def _calculate_risk_data(self, ticker: str, hist: pd.DataFrame = None) -> dict:
        risk = {}
        if hist is None:
            hist = self._fetch_history(ticker, period="1y")
        if hist is not None and not hist.empty and len(hist) > 20:
            try:
                returns = hist["Close"].pct_change().dropna()
                risk["volatility"] = round(float(returns.std() * (252**0.5) * 100), 2)
            except Exception:
                pass

            try:
                spy_hist = yf.Ticker("SPY").history(period="1y", interval="1d")
                if not spy_hist.empty:
                    spy_returns = spy_hist["Close"].pct_change().dropna()
                    aligned = pd.concat([returns, spy_returns], axis=1).dropna()
                    if len(aligned) > 20:
                        cov = float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]))
                        var = float(aligned.iloc[:, 1].var())
                        if var and var != 0:
                            risk["beta"] = round(cov / var, 2)
            except Exception:
                pass
        return risk

    def _calculate_conviction(
        self,
        technical_data: dict,
        fundamental_data: dict,
        risk_data: dict,
        position_data: dict = None,
    ) -> tuple[int, str, str, str]:
        """
        Calculate conviction score (0-100) and action.
        Returns: (conviction, action, reasoning, trigger_type)
        """
        score = 0
        reasons = []
        triggers = set()
        overweight_trigger = False

        # ── 1. Technical signals (weight 30) ──────────────────────────────────
        tech_score = 0
        overall = technical_data.get("overall_signal", "hold")
        if overall == "strong_buy":
            tech_score += 30
            triggers.add("technical")
            reasons.append("Technical: strong buy signal")
        elif overall == "buy":
            tech_score += 20
            triggers.add("technical")
            reasons.append("Technical: buy signal")
        elif overall == "sell":
            tech_score -= 20
            triggers.add("technical")
            reasons.append("Technical: sell signal")
        elif overall == "strong_sell":
            tech_score -= 30
            triggers.add("technical")
            reasons.append("Technical: strong sell signal")

        rsi = technical_data.get("rsi_14")
        if rsi is not None:
            if rsi < 20:
                tech_score += 10
                reasons.append(f"RSI deeply oversold ({rsi:.1f})")
            elif rsi < 30:
                tech_score += 5
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 80:
                tech_score -= 10
                reasons.append(f"RSI deeply overbought ({rsi:.1f})")
            elif rsi > 70:
                tech_score -= 5
                reasons.append(f"RSI overbought ({rsi:.1f})")

        score += tech_score

        # ── 2. Fundamental signals (weight 30) ─────────────────────────────────
        fund_score = 0
        val = fundamental_data.get("valuation", {})
        cf = fundamental_data.get("cash_flow", {})
        bs = fundamental_data.get("balance_sheet", {})
        growth = fundamental_data.get("growth", {})

        pe = val.get("trailing_pe")
        if pe is not None and isinstance(pe, (int, float)):
            if pe < 15:
                fund_score += 10
                reasons.append(f"Attractive P/E ({pe:.1f})")
            elif pe < 20:
                fund_score += 5
                reasons.append(f"Reasonable P/E ({pe:.1f})")
            elif pe > 40:
                fund_score -= 10
                reasons.append(f"High P/E ({pe:.1f})")
            elif pe > 30:
                fund_score -= 5
                reasons.append(f"Elevated P/E ({pe:.1f})")

        rev_growth = growth.get("revenue_growth")
        if rev_growth is not None and isinstance(rev_growth, (int, float)):
            if rev_growth > 0.20:
                fund_score += 10
                reasons.append(f"Strong revenue growth ({rev_growth:.1%})")
            elif rev_growth > 0.15:
                fund_score += 7
                reasons.append(f"Good revenue growth ({rev_growth:.1%})")
            elif rev_growth > 0.05:
                fund_score += 3
                reasons.append(f"Modest revenue growth ({rev_growth:.1%})")
            elif rev_growth < 0:
                fund_score -= 10
                reasons.append(f"Negative revenue growth ({rev_growth:.1%})")

        fcf = cf.get("free_cash_flow")
        if fcf is not None and isinstance(fcf, (int, float)):
            if fcf > 0:
                fund_score += 10
                reasons.append("Positive free cash flow")
            else:
                fund_score -= 10
                reasons.append("Negative free cash flow")

        ev_ebitda = val.get("ev_to_ebitda")
        if ev_ebitda is not None and isinstance(ev_ebitda, (int, float)):
            if ev_ebitda < 10:
                fund_score += 10
                reasons.append(f"Low EV/EBITDA ({ev_ebitda:.1f})")
            elif ev_ebitda < 15:
                fund_score += 5
                reasons.append(f"Reasonable EV/EBITDA ({ev_ebitda:.1f})")
            elif ev_ebitda > 30:
                fund_score -= 10
                reasons.append(f"High EV/EBITDA ({ev_ebitda:.1f})")
            elif ev_ebitda > 20:
                fund_score -= 5
                reasons.append(f"Elevated EV/EBITDA ({ev_ebitda:.1f})")

        de = bs.get("debt_to_equity")
        if de is not None and isinstance(de, (int, float)):
            if de < 0.3:
                fund_score += 5
                reasons.append(f"Low debt/equity ({de:.2f})")
            elif de > 2.0:
                fund_score -= 5
                reasons.append(f"High debt/equity ({de:.2f})")

        peg = val.get("peg_ratio")
        if peg is not None and isinstance(peg, (int, float)):
            if peg < 1.0:
                fund_score += 5
                reasons.append(f"Attractive PEG ({peg:.2f})")
            elif peg < 1.5:
                fund_score += 3
                reasons.append(f"Reasonable PEG ({peg:.2f})")
            elif peg > 3.0:
                fund_score -= 5
                reasons.append(f"High PEG ({peg:.2f})")

        score += fund_score

        # ── 3. Risk signals (weight 20) ──────────────────────────────────────
        risk_score = 0

        if position_data and position_data.get("position"):
            pos = position_data["position"]
            summary = position_data.get("summary", {})
            total_value = summary.get("total_value", 0)
            pos_value = pos.get("current_value") or pos.get("cost_basis", 0)

            if total_value and total_value > 0:
                weight = pos_value / total_value
                if weight > 0.15:
                    risk_score -= 20
                    overweight_trigger = True
                    triggers.add("rebalance")
                    reasons.append(f"Position overweight ({weight:.1%} of portfolio)")

        vol = risk_data.get("volatility")
        if vol is not None and vol > 40:
            risk_score -= 10
            reasons.append(f"High volatility ({vol:.1f}%)")
        elif vol is not None and vol > 30:
            risk_score -= 5
            reasons.append(f"Elevated volatility ({vol:.1f}%)")

        beta = risk_data.get("beta")
        if beta is not None and beta > 1.5:
            risk_score -= 5
            reasons.append(f"High beta ({beta:.2f})")

        score += risk_score

        # ── 4. Portfolio context (weight 20) ────────────────────────────────────
        port_score = 0

        if position_data:
            pos = position_data.get("position", {})
            summary = position_data.get("summary", {})

            current_price = pos.get("current_price")
            stop_loss = pos.get("stop_loss")
            take_profit = pos.get("take_profit")

            # Stop loss override — immediate sell regardless of other signals
            if (
                current_price is not None
                and stop_loss is not None
                and stop_loss > 0
                and current_price <= stop_loss
            ):
                triggers.add("stop_loss")
                return (
                    -100,
                    "sell",
                    f"Stop loss triggered at ${current_price:.2f} (limit ${stop_loss:.2f})",
                    "stop_loss",
                )

            # Take profit
            if (
                current_price is not None
                and take_profit is not None
                and take_profit > 0
            ):
                if current_price >= take_profit * 1.2:
                    triggers.add("take_profit")
                    return (
                        -50,
                        "sell",
                        f"Take profit exceeded by 20%+ at ${current_price:.2f} (target ${take_profit:.2f})",
                        "take_profit",
                    )
                elif current_price >= take_profit:
                    triggers.add("take_profit")
                    return (
                        -30,
                        "reduce",
                        f"Take profit hit at ${current_price:.2f} (target ${take_profit:.2f})",
                        "take_profit",
                    )

            # Cash drag
            cash = summary.get("cash", 0)
            total_value = summary.get("total_value", 0)
            if total_value and total_value > 0 and cash / total_value > 0.15:
                port_score += 10
                reasons.append("Cash drag — excess cash available for deployment")

        score += port_score

        # ── Action thresholds ──────────────────────────────────────────────────
        if score >= 80:
            action = "strong_buy"
        elif score >= 60:
            action = "buy"
        elif score >= 40:
            action = "hold"
        elif score >= 20:
            action = "reduce"
        elif score >= 0:
            action = "sell"
        else:
            action = "strong_sell"

        # Overweight override: if position > 15%, downgrade buy signals to reduce
        if overweight_trigger and action in ("strong_buy", "buy"):
            action = "reduce"
            triggers.add("rebalance")
            reasons.append("Overweight position — rebalance required")

        if not reasons:
            reasons.append("No significant signals detected")

        trigger_type = "|".join(sorted(triggers)) if triggers else "technical|fundamental"
        return score, action, "; ".join(reasons), trigger_type
