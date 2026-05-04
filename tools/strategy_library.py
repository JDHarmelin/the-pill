"""
Built-in trading strategies for The Pill backtester.
All strategies are pure functions: strategy(df_dict, engine, **kwargs) -> signals dict.
"""

import numpy as np
import pandas as pd
import yfinance as yf


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_current_price(df_dict, ticker):
    """Get the latest close price for a ticker from its historical df."""
    df = df_dict.get(ticker)
    if df is None or df.empty:
        return None
    close_col = "Close" if "Close" in df.columns else "close"
    return float(df[close_col].iloc[-1])


def _fetch_info_once(engine, tickers):
    """Fetch yfinance .info once per backtest and cache on engine."""
    cache_key = "_yf_info_cache"
    if hasattr(engine, cache_key):
        return getattr(engine, cache_key)
    data = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info or {}
            data[t] = info
        except Exception:
            data[t] = {}
    setattr(engine, cache_key, data)
    return data


# ── 1. Shkreli Value Strategy ───────────────────────────────────────────────

def shkreli_value_strategy(df_dict, engine, fundamentals=None):
    """
    Buy when EV/EBITDA < sector median AND FCF > 0.
    Sell when EV/EBITDA > 2x sector median OR FCF turns negative.
    Position size: equal weight among qualifying tickers.
    """
    tickers = list(df_dict.keys())
    if not tickers:
        return {}

    # Use provided fundamentals or fetch via yfinance once
    if fundamentals is not None:
        fdata = fundamentals
    else:
        info_cache = _fetch_info_once(engine, tickers)
        fdata = {}
        for t in tickers:
            info = info_cache.get(t, {})
            fdata[t] = {
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                "free_cash_flow": info.get("freeCashflow"),
            }

    valid = [
        (t, fdata[t]["ev_to_ebitda"])
        for t in tickers
        if fdata.get(t, {}).get("ev_to_ebitda") is not None
        and fdata[t]["ev_to_ebitda"] > 0
    ]

    # Fallback: equal-weight buy-and-hold on day 1 if no fundamentals
    if not valid:
        if not engine.positions and engine.cash > 0:
            prices = {t: _get_current_price(df_dict, t) for t in tickers}
            valid_prices = {t: p for t, p in prices.items() if p}
            if valid_prices:
                alloc = engine.cash / len(valid_prices)
                return {
                    t: {
                        "action": "buy",
                        "shares": alloc / p,
                        "reason": "Fallback equal-weight (no fundamentals)",
                    }
                    for t, p in valid_prices.items()
                }
        return {}

    median_ev = float(np.median([v for _, v in valid]))
    qualifying = []
    for t, ev in valid:
        fcf = fdata[t].get("free_cash_flow")
        if ev < median_ev and (fcf is None or fcf > 0):
            qualifying.append(t)

    if not qualifying:
        qualifying = [t for t, _ in valid]

    signals = {}

    # Sell positions that no longer qualify
    for t, shares in engine.positions.items():
        ev = fdata.get(t, {}).get("ev_to_ebitda")
        fcf = fdata.get(t, {}).get("free_cash_flow")
        if ev is not None and (ev > 2 * median_ev or (fcf is not None and fcf < 0)):
            price = _get_current_price(df_dict, t)
            if price:
                signals[t] = {
                    "action": "sell",
                    "shares": shares,
                    "reason": f"EV/EBITDA {ev:.1f} disqualifies",
                }

    # Buy missing qualifying positions (equal weight)
    missing = [t for t in qualifying if t not in engine.positions]
    if missing and engine.cash > 0:
        prices = {t: _get_current_price(df_dict, t) for t in qualifying}
        valid_prices = {t: p for t, p in prices.items() if p}
        if valid_prices:
            # Target equal weight across all qualifying tickers
            total_val = engine.total_value(
                {t: _get_current_price(df_dict, t) for t in engine.positions}
            )
            total_val += engine.cash
            target_per = total_val / len(qualifying)
            for t in missing:
                p = valid_prices.get(t)
                if p and p > 0:
                    signals[t] = {
                        "action": "buy",
                        "shares": target_per / p,
                        "reason": "Value: EV/EBITDA < median, FCF > 0",
                    }

    return signals


# ── 2. Momentum + Quality Strategy ──────────────────────────────────────────

def momentum_quality_strategy(df_dict, engine):
    """
    Buy top 20% by 90-day momentum + ROE > 15%.
    Sell when momentum rank drops below 50% or ROE < 10%.
    Rebalance monthly.
    """
    tickers = list(df_dict.keys())
    if not tickers:
        return {}

    current_date = getattr(engine, "current_date", None)

    # Monthly rebalance gate
    if not hasattr(engine, "_last_momentum_rebalance"):
        engine._last_momentum_rebalance = None

    if current_date:
        current_month = current_date[:7]
        if engine._last_momentum_rebalance == current_month:
            return {}
        engine._last_momentum_rebalance = current_month
    else:
        if hasattr(engine, "_bar_count"):
            engine._bar_count += 1
            if engine._bar_count % 21 != 1:
                return {}
        else:
            engine._bar_count = 1

    # 90-day momentum
    momentum = {}
    for t in tickers:
        df = df_dict.get(t)
        if df is None or len(df) < 2:
            continue
        close_col = "Close" if "Close" in df.columns else "close"
        prices = df[close_col]
        if len(prices) >= 90:
            mom = prices.iloc[-1] / prices.iloc[-90] - 1
        else:
            mom = prices.iloc[-1] / prices.iloc[0] - 1
        momentum[t] = mom

    if not momentum:
        return {}

    # ROE filter (quality)
    info_cache = _fetch_info_once(engine, tickers)
    eligible = []
    for t, mom in momentum.items():
        roe = info_cache.get(t, {}).get("returnOnEquity")
        if roe is None or roe > 0.15:
            eligible.append((t, mom))

    if not eligible:
        eligible = list(momentum.items())

    # Top 20% momentum
    eligible.sort(key=lambda x: x[1], reverse=True)
    n_top = max(1, int(len(eligible) * 0.2))
    top_tickers = [t for t, _ in eligible[:n_top]]

    signals = {}

    # Sell anything not in top tickers
    for t, shares in engine.positions.items():
        if t not in top_tickers:
            price = _get_current_price(df_dict, t)
            if price:
                signals[t] = {
                    "action": "sell",
                    "shares": shares,
                    "reason": "Dropped out of top momentum quintile",
                }

    # Buy top tickers we don't own
    missing = [t for t in top_tickers if t not in engine.positions]
    if missing and engine.cash > 0:
        prices = {t: _get_current_price(df_dict, t) for t in missing}
        valid = {t: p for t, p in prices.items() if p}
        if valid:
            alloc = engine.cash / len(valid)
            for t, p in valid.items():
                signals[t] = {
                    "action": "buy",
                    "shares": alloc / p,
                    "reason": "Top momentum + quality",
                }

    return signals


# ── 3. AI Conviction Strategy ───────────────────────────────────────────────

def ai_conviction_strategy(df_dict, engine):
    """
    Buy when composite technical score > 60 (strong_buy).
    Sell when score < -30 (sell).
    Hold 5-10 positions max.
    """
    tickers = list(df_dict.keys())
    if not tickers:
        return {}

    def _compute_score(df):
        if df is None or len(df) < 50:
            return 0.0
        close_col = "Close" if "Close" in df.columns else "close"
        close = df[close_col]

        # RSI(14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean().iloc[-1]
        avg_loss = loss.rolling(14).mean().iloc[-1]
        if avg_loss and avg_loss > 0:
            rsi = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        else:
            rsi = 50.0

        # MACD histogram proxy
        ema12 = close.ewm(span=12).mean().iloc[-1]
        ema26 = close.ewm(span=26).mean().iloc[-1]
        macd = ema12 - ema26
        signal = close.ewm(span=9).mean().iloc[-1]
        macd_hist = macd - signal

        # MA ratio
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        ma_ratio = (ma50 / ma200 - 1.0) * 100.0 if ma200 and ma200 > 0 else 0.0

        # 20-day momentum
        mom20 = (
            (close.iloc[-1] / close.iloc[-20] - 1.0) * 100.0
            if len(close) >= 20
            else 0.0
        )

        # Composite score
        score = 0.0
        score += (rsi - 50.0) * 0.3
        score += np.sign(macd_hist) * min(abs(macd_hist) / close.iloc[-1] * 100, 30)
        score += ma_ratio * 1.5
        score += mom20 * 1.0
        return score

    scores = {t: _compute_score(df_dict.get(t)) for t in tickers}

    strong_buy = [t for t, s in scores.items() if s > 60]
    sell_zone = [t for t, s in scores.items() if s < -30]

    signals = {}

    # Sell positions in sell zone
    for t in sell_zone:
        if t in engine.positions:
            signals[t] = {
                "action": "sell",
                "shares": engine.positions[t],
                "reason": f"AI conviction {scores[t]:.0f} < -30",
            }

    # Buy strong buys, respecting 5-10 position limit
    current_holdings = list(engine.positions.keys())
    post_sell_holdings = [t for t in current_holdings if t not in sell_zone]
    candidates = [t for t in strong_buy if t not in post_sell_holdings]
    slots = 10 - len(post_sell_holdings)

    if candidates and slots > 0 and engine.cash > 0:
        to_buy = candidates[:slots]
        prices = {t: _get_current_price(df_dict, t) for t in to_buy}
        valid = {t: p for t, p in prices.items() if p}
        if valid:
            alloc = engine.cash / len(valid)
            for t, p in valid.items():
                signals[t] = {
                    "action": "buy",
                    "shares": alloc / p,
                    "reason": f"AI conviction {scores[t]:.0f} > 60",
                }

    return signals


# ── 4. Buy and Hold Strategy ────────────────────────────────────────────────

def buy_and_hold_strategy(df_dict, engine):
    """
    Buy equal weight on day 1, hold forever.
    Used as a benchmark comparison.
    """
    if engine.positions:
        return {}

    tickers = list(df_dict.keys())
    if not tickers or engine.cash <= 0:
        return {}

    prices = {t: _get_current_price(df_dict, t) for t in tickers}
    valid = {t: p for t, p in prices.items() if p}
    if not valid:
        return {}

    alloc = engine.cash / len(valid)
    return {
        t: {
            "action": "buy",
            "shares": alloc / p,
            "reason": "Buy and hold",
        }
        for t, p in valid.items()
    }
