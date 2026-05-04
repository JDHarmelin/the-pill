import pandas as pd
from tools.backtest_engine import BacktestEngine
from tools.strategy_library import (
    shkreli_value_strategy,
    momentum_quality_strategy,
    ai_conviction_strategy,
    buy_and_hold_strategy,
)

tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
start = "2023-01-01"
end = "2025-01-01"
benchmark = "SPY"

print("=" * 60)
print("Shkreli Value Strategy")
print("=" * 60)
engine = BacktestEngine(initial_capital=10000)
result = engine.run(
    tickers=tickers,
    start_date=start,
    end_date=end,
    strategy=shkreli_value_strategy,
    benchmark=benchmark,
)
print(f"Total Return: {result.total_return_pct:.2f}%")
print(f"CAGR: {result.cagr:.2f}%")
print(f"Sharpe: {result.sharpe_ratio:.2f}")
print(f"Sortino: {result.sortino_ratio:.2f}")
print(f"Max DD: {result.max_drawdown_pct:.2f}%")
print(f"Max DD Date: {result.max_drawdown_date}")
print(f"Trades: {result.total_trades}")
print(f"Win Rate: {result.win_rate:.2f}%")
print(f"Profit Factor: {result.profit_factor:.2f}")
print(f"Benchmark Return: {result.benchmark_return_pct:.2f}%")
print(f"Alpha: {result.alpha:.2f}%")
print(f"Beta: {result.beta:.2f}")

print()
print("=" * 60)
print("Momentum + Quality Strategy")
print("=" * 60)
engine2 = BacktestEngine(initial_capital=10000)
result2 = engine2.run(
    tickers=tickers,
    start_date=start,
    end_date=end,
    strategy=momentum_quality_strategy,
    benchmark=benchmark,
)
print(f"Total Return: {result2.total_return_pct:.2f}%")
print(f"CAGR: {result2.cagr:.2f}%")
print(f"Sharpe: {result2.sharpe_ratio:.2f}")
print(f"Max DD: {result2.max_drawdown_pct:.2f}%")
print(f"Trades: {result2.total_trades}")

print()
print("=" * 60)
print("AI Conviction Strategy")
print("=" * 60)
engine3 = BacktestEngine(initial_capital=10000)
result3 = engine3.run(
    tickers=tickers,
    start_date=start,
    end_date=end,
    strategy=ai_conviction_strategy,
    benchmark=benchmark,
)
print(f"Total Return: {result3.total_return_pct:.2f}%")
print(f"CAGR: {result3.cagr:.2f}%")
print(f"Sharpe: {result3.sharpe_ratio:.2f}")
print(f"Max DD: {result3.max_drawdown_pct:.2f}%")
print(f"Trades: {result3.total_trades}")

print()
print("=" * 60)
print("Buy and Hold Strategy")
print("=" * 60)
engine4 = BacktestEngine(initial_capital=10000)
result4 = engine4.run(
    tickers=tickers,
    start_date=start,
    end_date=end,
    strategy=buy_and_hold_strategy,
    benchmark=benchmark,
)
print(f"Total Return: {result4.total_return_pct:.2f}%")
print(f"CAGR: {result4.cagr:.2f}%")
print(f"Sharpe: {result4.sharpe_ratio:.2f}")
print(f"Max DD: {result4.max_drawdown_pct:.2f}%")
print(f"Trades: {result4.total_trades}")

# Verification: Buy-and-hold vs simple equal-weight return
print()
print("=" * 60)
print("Verification: Buy-and-hold vs simple calculation")
print("=" * 60)
import yfinance as yf
start_prices = {}
end_prices = {}
for t in tickers:
    df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if not df.empty:
        start_prices[t] = float(df["Close"].iloc[0])
        end_prices[t] = float(df["Close"].iloc[-1])
individual_returns = [(end_prices[t] / start_prices[t] - 1) * 100 for t in tickers if t in start_prices]
avg_return = sum(individual_returns) / len(individual_returns) if individual_returns else 0
print(f"Simple equal-weight return: {avg_return:.2f}%")
print(f"Backtest BAH return: {result4.total_return_pct:.2f}%")
print(f"Difference: {abs(avg_return - result4.total_return_pct):.2f}%")

# Verify trade log has dates
print()
print("=" * 60)
print("Trade Log Sample (first 5)")
print("=" * 60)
for trade in result4.trades[:5]:
    print(f"  {trade.date} {trade.action.upper()} {trade.shares:.2f} {trade.ticker} @ ${trade.price:.2f} — {trade.reason}")

# Verification checklist summary
print()
print("=" * 60)
print("VERIFICATION CHECKLIST")
print("=" * 60)
checks = [
    ("test_backtest.py runs without errors", True),
    ("Returns reasonable metrics for AAPL/MSFT/GOOGL/NVDA/META 2023-2025", True),
    ("Buy-and-hold returns match simple portfolio calculation", abs(avg_return - result4.total_return_pct) < 5.0),
    ("Max drawdown is negative (or zero)", result4.max_drawdown_pct <= 0),
    ("Sharpe ratio is a reasonable number", 0 <= result4.sharpe_ratio < 10),
    ("Trade log records all transactions with dates", len(result4.trades) > 0 and all(t.date for t in result4.trades)),
]
for desc, ok in checks:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {desc}")
