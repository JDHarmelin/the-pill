#!/usr/bin/env python3
"""
Standalone test script for SignalEngine and RebalanceEngine.
"""
import sys

from tools.signal_engine import SignalEngine
from tools.rebalance_engine import RebalanceEngine
from tools.portfolio_manager import PortfolioManager
from tools.watchlist_manager import WatchlistManager
from db import Database


def test_signals():
    print("=" * 60)
    print("TEST 1: SignalEngine.scan_portfolio")
    print("=" * 60)
    pm = PortfolioManager()
    se = SignalEngine()

    portfolios = pm.get_all()
    if not portfolios:
        print("No portfolios found.")
        return False

    portfolio = portfolios[0]
    pid = portfolio["id"]
    print(f"Scanning portfolio: {portfolio['name']} ({pid})")

    signals = se.scan_portfolio(pid, pm)
    print(f"Generated {len(signals)} signals\n")

    if not signals:
        print("No signals generated — possible data fetch issue.")
        return False

    ok = True
    for s in signals[:5]:
        print(f"{s.ticker}: {s.action} (conviction: {s.conviction})")
        print(f"  Trigger: {s.trigger_type}")
        print(f"  Reason: {s.reasoning}")
        print(f"  Price: {s.current_price}")
        if s.suggested_shares:
            print(f"  Suggested shares: {s.suggested_shares}")
        print()

        if not isinstance(s.conviction, int):
            print(f"  ERROR: conviction not int for {s.ticker}")
            ok = False

    return ok


def test_watchlist_signals():
    print("=" * 60)
    print("TEST 2: WatchlistManager + SignalEngine.scan_watchlist")
    print("=" * 60)
    db = Database()
    wm = WatchlistManager(db)

    watchlists = wm.get_watchlists()
    if watchlists:
        wl = watchlists[0]
    else:
        wl = wm.create_watchlist("Test Watchlist")
        wm.add_ticker(wl["id"], "AAPL")
        wm.add_ticker(wl["id"], "MSFT")
        wm.add_ticker(wl["id"], "NVDA")
        wl = wm.get_watchlist(wl["id"])

    tickers = [item["ticker"] for item in wl.get("items", [])]
    print(f"Watchlist '{wl['name']}' has {len(tickers)} tickers: {tickers}")

    se = SignalEngine()
    signals = se.scan_watchlist(tickers)
    print(f"Generated {len(signals)} watchlist signals\n")

    for s in signals:
        print(f"{s.ticker}: {s.action} (conviction: {s.conviction})")
        print(f"  Reason: {s.reasoning}")
        print()

    return True


def test_rebalance():
    print("=" * 60)
    print("TEST 3: RebalanceEngine.equal_weight_rebalance")
    print("=" * 60)
    pm = PortfolioManager()
    re = RebalanceEngine()

    portfolios = pm.get_all()
    if not portfolios:
        print("No portfolios found.")
        return False

    pid = portfolios[0]["id"]
    actions = re.equal_weight_rebalance(pid, pm)
    print(f"Equal-weight rebalance: {len(actions)} actions")

    total_buy = sum(a.estimated_value for a in actions if a.action == "buy")
    total_sell = sum(a.estimated_value for a in actions if a.action == "sell")
    print(f"Total buy value:  ${total_buy:,.2f}")
    print(f"Total sell value: ${total_sell:,.2f}")
    print(f"Net: ${total_buy - total_sell:,.2f}")
    print()

    for a in actions[:5]:
        print(
            f"{a.ticker}: {a.action} {a.delta_shares:+.2f} shares "
            f"(${a.estimated_value:,.2f}) — {a.reason}"
        )
    print()

    if actions:
        weights = []
        positions, cash = pm.get_positions_with_returns(pid)
        total_value = cash + sum(
            p.get("current_value") or p.get("cost_basis", 0) for p in positions
        )
        for a in actions:
            if a.target_shares > 0 and a.estimated_price > 0:
                target_value = a.target_shares * a.estimated_price
                weights.append(target_value / total_value)
        if weights:
            first_w = weights[0]
            all_same = all(abs(w - first_w) < 0.01 for w in weights)
            print(f"All actions target same weight: {all_same}")
            if not all_same:
                print(f"  Weights: {[round(w, 4) for w in weights]}")
            return all_same
    return True


def test_stop_loss_override():
    print("=" * 60)
    print("TEST 4: Stop loss override")
    print("=" * 60)
    pm = PortfolioManager()
    se = SignalEngine()

    portfolios = pm.get_all()
    if not portfolios:
        print("No portfolios found.")
        return False

    pid = portfolios[0]["id"]
    positions, cash = pm.get_positions_with_returns(pid)
    if not positions:
        print("No positions to test.")
        return False

    pos = positions[0]
    ticker = pos["ticker"]
    original_sl = pos.get("stop_loss")
    current_price = pos.get("current_price")

    if current_price is None:
        print(f"No current price for {ticker}")
        return False

    # Set stop loss ABOVE current price to force trigger
    fake_sl = current_price * 1.5
    pm.set_position_targets(pid, ticker, stop_loss=fake_sl)

    try:
        positions, cash = pm.get_positions_with_returns(pid)
        updated_pos = next((p for p in positions if p["ticker"] == ticker), None)

        pos_data = {
            "position": updated_pos,
            "cash": cash,
            "summary": pm.get_summary(pid, positions, cash),
            "portfolio": pm.get_portfolio(pid),
            "all_positions": positions,
        }

        signal = se.generate_signal(ticker, pos_data)
        print(f"{ticker}: {signal.action} (conviction: {signal.conviction})")
        print(f"  Trigger: {signal.trigger_type}")
        print(f"  Reason: {signal.reasoning}")

        if signal.action == "sell" and signal.trigger_type == "stop_loss":
            print("Stop loss override: PASS")
            return True
        else:
            print("Stop loss override: FAIL")
            return False
    finally:
        pm.set_position_targets(pid, ticker, stop_loss=original_sl)


def main():
    results = []
    try:
        results.append(("scan_portfolio", test_signals()))
        results.append(("watchlist_signals", test_watchlist_signals()))
        results.append(("rebalance", test_rebalance()))
        results.append(("stop_loss_override", test_stop_loss_override()))
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("exception", False))

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
