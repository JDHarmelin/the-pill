"""
Backtesting Engine for The Pill.
Simulates trading strategies over historical price data.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf


@dataclass
class Trade:
    date: str
    ticker: str
    action: str  # "buy" | "sell"
    shares: float
    price: float
    value: float
    reason: str = ""


@dataclass
class BacktestResult:
    initial_capital: float
    final_value: float
    total_return_pct: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    max_drawdown_date: str
    win_rate: float
    avg_winner: float
    avg_loser: float
    profit_factor: float
    total_trades: int
    equity_curve: list[dict]  # [{date, value, benchmark}]
    trades: list[Trade]
    monthly_returns: list[dict]
    benchmark_return_pct: float
    alpha: float
    beta: float


class BacktestEngine:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, float] = {}  # ticker -> shares
        self.trade_log: list[Trade] = []
        self.equity_curve: list[dict] = []
        self._trade_pnl: list[dict] = []
        self._position_cost: dict[str, float] = {}
        self.current_date: Optional[str] = None

    def run(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        strategy: Callable,
        benchmark: str = "SPY",
        **strategy_kwargs,
    ) -> BacktestResult:
        """
        Run a strategy over historical data.

        strategy(df_dict, engine, **kwargs) -> signals dict
        df_dict: {ticker: DataFrame with OHLCV}
        engine: BacktestEngine instance (call engine.buy/sell)
        Returns: {ticker: {"action": "buy"/"sell", "shares": N, "reason": str}}
        """
        self.cash = self.initial_capital
        self.positions = {}
        self.trade_log = []
        self.equity_curve = []
        self._trade_pnl = []
        self._position_cost = {}
        self.current_date = None

        # ── Fetch ticker data ──────────────────────────────────────────────
        df_dict = {}
        for t in tickers:
            try:
                df = yf.download(
                    t,
                    start=start_date,
                    end=end_date,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df_dict[t] = df
            except Exception:
                continue

        if not df_dict:
            raise ValueError("No historical data fetched for any tickers")

        # ── Fetch benchmark ────────────────────────────────────────────────
        bench_df = None
        try:
            bench_df = yf.download(
                benchmark,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if not bench_df.empty and isinstance(bench_df.columns, pd.MultiIndex):
                bench_df.columns = bench_df.columns.get_level_values(0)
        except Exception:
            pass

        if bench_df is None or bench_df.empty:
            bench_df = pd.DataFrame(
                index=pd.date_range(start=start_date, end=end_date, freq="D")
            )
            bench_df["Close"] = 1.0

        # ── Common trading dates ─────────────────────────────────────────
        all_dates = set(bench_df.index)
        for df in df_dict.values():
            all_dates &= set(df.index)

        trading_dates = sorted(all_dates)
        if not trading_dates:
            raise ValueError(
                "No common trading dates between tickers and benchmark"
            )

        bench_col = "Close" if "Close" in bench_df.columns else "close"
        bench_first = float(bench_df[bench_col].iloc[0])
        bench_norm = self.initial_capital / bench_first if bench_first > 0 else 1.0

        # ── Simulation loop ──────────────────────────────────────────────
        for date in trading_dates:
            self.current_date = date.strftime("%Y-%m-%d")

            # Slice data up to current date
            current_dfs = {}
            prices = {}
            for t, df in df_dict.items():
                mask = df.index <= date
                sliced = df.loc[mask].copy()
                current_dfs[t] = sliced
                if not sliced.empty:
                    close_col = (
                        "Close" if "Close" in sliced.columns else "close"
                    )
                    prices[t] = float(sliced[close_col].iloc[-1])

            # Ensure prices for existing positions
            for t in self.positions:
                if t not in prices and t in df_dict:
                    df = df_dict[t]
                    mask = df.index <= date
                    sliced = df.loc[mask]
                    if not sliced.empty:
                        close_col = (
                            "Close"
                            if "Close" in sliced.columns
                            else "close"
                        )
                        prices[t] = float(sliced[close_col].iloc[-1])

            # Strategy signal generation
            signals = strategy(current_dfs, self, **strategy_kwargs)

            if isinstance(signals, dict):
                for t, sig in signals.items():
                    if sig.get("action") == "buy":
                        price = prices.get(t, sig.get("price", 0))
                        if price and price > 0:
                            self.buy(
                                self.current_date,
                                t,
                                sig.get("shares", 0),
                                price,
                                sig.get("reason", ""),
                            )
                    elif sig.get("action") == "sell":
                        price = prices.get(t, sig.get("price", 0))
                        if price and price > 0:
                            self.sell(
                                self.current_date,
                                t,
                                sig.get("shares", 0),
                                price,
                                sig.get("reason", ""),
                            )

            # Record equity
            total_val = self.total_value(prices)
            bench_close = float(bench_df.loc[date, bench_col])
            bench_val = bench_close * bench_norm
            self.equity_curve.append(
                {
                    "date": self.current_date,
                    "value": round(total_val, 2),
                    "benchmark": round(bench_val, 2),
                }
            )

        return self._calculate_result()

    def buy(
        self,
        date: str,
        ticker: str,
        shares: float,
        price: float,
        reason: str = "",
    ):
        cost = shares * price
        if cost > self.cash:
            shares = self.cash / price  # Partial fill
            cost = shares * price
        if shares <= 0:
            return
        self.cash -= cost
        self.positions[ticker] = self.positions.get(ticker, 0) + shares
        self._position_cost[ticker] = (
            self._position_cost.get(ticker, 0) + cost
        )
        self.trade_log.append(
            Trade(date, ticker, "buy", shares, price, cost, reason)
        )

    def sell(
        self,
        date: str,
        ticker: str,
        shares: float,
        price: float,
        reason: str = "",
    ):
        current = self.positions.get(ticker, 0)
        if current <= 0:
            return
        shares = min(shares, current)
        proceeds = shares * price
        avg_cost = (
            self._position_cost.get(ticker, 0) / current
            if current > 0
            else 0
        )
        cost_basis = shares * avg_cost
        pnl = proceeds - cost_basis
        self._trade_pnl.append(
            {
                "date": date,
                "ticker": ticker,
                "pnl": pnl,
                "proceeds": proceeds,
                "cost_basis": cost_basis,
            }
        )

        self.cash += proceeds
        self.positions[ticker] = current - shares
        self._position_cost[ticker] = (
            self._position_cost.get(ticker, 0) - cost_basis
        )
        if self.positions[ticker] <= 0:
            del self.positions[ticker]
            if ticker in self._position_cost:
                del self._position_cost[ticker]
        self.trade_log.append(
            Trade(date, ticker, "sell", shares, price, proceeds, reason)
        )

    def total_value(self, prices: dict[str, float]) -> float:
        position_value = sum(
            self.positions.get(t, 0) * p for t, p in prices.items()
        )
        return self.cash + position_value

    def _calculate_result(self) -> BacktestResult:
        if not self.equity_curve:
            raise ValueError("No equity curve data")

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df["date"] = pd.to_datetime(equity_df["date"])
        equity_df = equity_df.sort_values("date").reset_index(drop=True)

        # Daily returns
        equity_df["daily_return"] = equity_df["value"].pct_change()
        daily_returns = equity_df["daily_return"].dropna()

        # Basic metrics
        initial = self.initial_capital
        final = float(equity_df["value"].iloc[-1])
        total_return_pct = (final / initial - 1) * 100

        days = (equity_df["date"].iloc[-1] - equity_df["date"].iloc[0]).days
        if days <= 0:
            cagr = 0.0
        else:
            cagr = ((final / initial) ** (365.0 / days) - 1) * 100

        # Sharpe
        if daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(
                252
            )
        else:
            sharpe = 0.0

        # Sortino
        negative_returns = daily_returns[daily_returns < 0]
        if negative_returns.std() > 0:
            sortino = (
                daily_returns.mean() / negative_returns.std()
            ) * np.sqrt(252)
        else:
            sortino = 0.0

        # Max drawdown
        rolling_max = equity_df["value"].cummax()
        drawdown = (equity_df["value"] - rolling_max) / rolling_max
        max_drawdown_pct = drawdown.min() * 100
        max_dd_idx = drawdown.idxmin()
        max_drawdown_date = (
            equity_df.loc[max_dd_idx, "date"].strftime("%Y-%m-%d")
            if max_dd_idx is not None
            else ""
        )

        # Trade stats
        total_trades = len(self.trade_log)
        sell_trades = self._trade_pnl
        win_count = sum(1 for t in sell_trades if t["pnl"] > 0)
        loss_count = sum(1 for t in sell_trades if t["pnl"] <= 0)
        win_rate = (win_count / len(sell_trades) * 100) if sell_trades else 0.0

        gross_profit = sum(t["pnl"] for t in sell_trades if t["pnl"] > 0)
        gross_loss = abs(
            sum(t["pnl"] for t in sell_trades if t["pnl"] <= 0)
        )
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 0.0)
        )

        avg_winner = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loser = (-gross_loss / loss_count) if loss_count > 0 else 0.0

        # Benchmark return
        bench_initial = float(equity_df["benchmark"].iloc[0])
        bench_final = float(equity_df["benchmark"].iloc[-1])
        benchmark_return_pct = (
            (bench_final / bench_initial - 1) * 100 if bench_initial > 0 else 0.0
        )

        # Alpha / Beta
        bench_returns = equity_df["benchmark"].pct_change().dropna()
        aligned = pd.DataFrame(
            {"port": daily_returns, "bench": bench_returns}
        ).dropna()

        if len(aligned) > 1 and aligned["bench"].var() > 0:
            beta = aligned["port"].cov(aligned["bench"]) / aligned[
                "bench"
            ].var()
            alpha_daily = (
                aligned["port"].mean() - beta * aligned["bench"].mean()
            )
            alpha = alpha_daily * 252 * 100  # annualized percentage
        else:
            beta = 0.0
            alpha = 0.0

        # Monthly returns
        equity_df["year_month"] = equity_df["date"].dt.to_period("M")
        monthly = (
            equity_df.groupby("year_month")
            .agg(start_value=("value", "first"), end_value=("value", "last"))
            .reset_index()
        )
        monthly["return_pct"] = (
            monthly["end_value"] / monthly["start_value"] - 1
        ) * 100
        monthly_returns = [
            {
                "month": str(row["year_month"]),
                "return_pct": round(row["return_pct"], 2),
            }
            for _, row in monthly.iterrows()
        ]

        return BacktestResult(
            initial_capital=round(initial, 2),
            final_value=round(final, 2),
            total_return_pct=round(total_return_pct, 2),
            cagr=round(cagr, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            max_drawdown_date=max_drawdown_date,
            win_rate=round(win_rate, 2),
            avg_winner=round(avg_winner, 2),
            avg_loser=round(avg_loser, 2),
            profit_factor=round(profit_factor, 2),
            total_trades=total_trades,
            equity_curve=self.equity_curve,
            trades=self.trade_log,
            monthly_returns=monthly_returns,
            benchmark_return_pct=round(benchmark_return_pct, 2),
            alpha=round(alpha, 2),
            beta=round(beta, 2),
        )
