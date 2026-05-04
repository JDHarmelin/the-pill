"""
Portfolio Manager — Paper trading tracker.
Data persists in JSON files via tools.json_store.JsonStore.
"""

import os
import time
import json
from copy import deepcopy
from datetime import datetime
import yfinance as yf
import pandas as pd

from tools.json_store import JsonStore


class PortfolioManager:
    def __init__(self):
        self.db = JsonStore()
        self._positions_cache = {}
        self._risk_cache = {}
        self._chart_cache = {}
        self._precomputed_risk = self._load_precomputed_risk()

    def _load_precomputed_risk(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "..", "data", "risk_metrics.json")
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _invalidate_runtime_caches(self, pid):
        self._positions_cache = {k: v for k, v in self._positions_cache.items() if k[0] != pid}
        self._risk_cache = {k: v for k, v in self._risk_cache.items() if k[0] != pid}
        self._chart_cache = {k: v for k, v in self._chart_cache.items() if k[0] != pid}

    def _portfolio_signature(self, portfolio):
        return json.dumps(
            {
                "capital": round(float(portfolio.get("capital", 0)), 6),
                "positions": [
                    {
                        "ticker": pos["ticker"],
                        "shares": round(float(pos["shares"]), 6),
                        "avg_cost": round(float(pos["avg_cost"]), 6),
                    }
                    for pos in portfolio.get("positions", [])
                ],
            },
            sort_keys=True,
        )

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def get_all(self):
        return self.db.get_portfolios()

    def get_portfolio(self, portfolio_id):
        return self.db.get_portfolio(portfolio_id)

    def create(self, name, capital=10000.0):
        return self.db.create_portfolio({"name": name, "capital": float(capital)})

    def delete(self, portfolio_id):
        self.db.delete_portfolio(portfolio_id)

    def update_capital(self, portfolio_id, capital):
        return self.db.update_portfolio_capital(portfolio_id, capital)

    def add_position(self, portfolio_id, ticker, shares, avg_cost):
        ticker = ticker.upper()
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return None

        for pos in portfolio.get("positions", []):
            if pos["ticker"] == ticker:
                total_shares = float(pos["shares"]) + float(shares)
                total_cost = float(pos["shares"]) * float(pos["avg_cost"]) + float(shares) * float(avg_cost)
                new_avg = round(total_cost / total_shares, 6) if total_shares else float(pos["avg_cost"])
                self.db.update_position(portfolio_id, ticker, {"shares": round(total_shares, 6), "avg_cost": new_avg})
                self._invalidate_runtime_caches(portfolio_id)
                self.record_trade(portfolio_id, ticker, "add", float(shares), float(avg_cost))
                return {**pos, "shares": round(total_shares, 6), "avg_cost": new_avg}

        pos = {
            "ticker": ticker,
            "shares": round(float(shares), 6),
            "avg_cost": round(float(avg_cost), 6),
            "added_date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.db.add_position(portfolio_id, pos)
        self._invalidate_runtime_caches(portfolio_id)
        self.record_trade(portfolio_id, ticker, "buy", float(shares), float(avg_cost))
        return pos

    def remove_position(self, portfolio_id, ticker):
        ticker = ticker.upper()
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False
        for pos in portfolio.get("positions", []):
            if pos["ticker"] == ticker:
                self.record_trade(portfolio_id, ticker, "sell", float(pos["shares"]), float(pos.get("avg_cost", 0)))
                break
        ok = self.db.remove_position(portfolio_id, ticker)
        if ok:
            self._invalidate_runtime_caches(portfolio_id)
        return ok

    def set_positions(self, portfolio_id, new_positions):
        """Atomically replace all positions (used by rebalance)."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False

        for pos in portfolio.get("positions", []):
            self.db.remove_position(portfolio_id, pos["ticker"])

        for pos in new_positions:
            if float(pos.get("shares", 0)) > 0:
                self.db.add_position(
                    portfolio_id,
                    {
                        "ticker": str(pos["ticker"]).upper(),
                        "shares": round(float(pos["shares"]), 6),
                        "avg_cost": round(float(pos["avg_cost"]), 6),
                        "added_date": datetime.now().strftime("%Y-%m-%d"),
                    },
                )
        self._invalidate_runtime_caches(portfolio_id)
        return True

    # ── Live data ─────────────────────────────────────────────────────────────

    def get_positions_with_returns(self, portfolio_id):
        """Return positions enriched with current price and gain/loss."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return [], 0.0

        now = time.time()
        cache_key = (portfolio_id, self._portfolio_signature(portfolio))
        cached = self._positions_cache.get(cache_key)
        if cached and (now - cached["timestamp"]) < 300:
            return deepcopy(cached["value"])

        positions = portfolio.get("positions", [])
        if not positions:
            return [], portfolio.get("capital", 0.0)

        tickers = [p["ticker"] for p in positions]
        prices = {}

        # 1. Try price cache first (instant)
        try:
            from tools.price_cache import get_price_cache
            cache = get_price_cache()
            for t in tickers:
                cp = cache.get_price(t)
                if cp:
                    prices[t] = cp
        except Exception:
            pass

        # 2. Fallback: batch download from yfinance for cache misses
        missing = [t for t in tickers if t not in prices]
        if missing:
            try:
                raw = yf.download(missing, period="5d", interval="1d",
                                  progress=False, auto_adjust=True, threads=False)["Close"]
                if isinstance(raw, pd.Series):
                    raw = raw.to_frame(name=missing[0])
                for t in missing:
                    if t in raw.columns:
                        series = raw[t].dropna()
                        if not series.empty:
                            prices[t] = float(series.iloc[-1])
            except Exception:
                pass

        # 3. Final fallback: Finnhub for any still missing
        still_missing = [t for t in tickers if t not in prices]
        if still_missing:
            try:
                from tools.finnhub_fetcher import FinnhubFetcher
                fh = FinnhubFetcher()
                for t in still_missing:
                    try:
                        quote = fh.get_realtime_quote(t)
                        if quote.get("price") and quote["price"] > 0:
                            prices[t] = float(quote["price"])
                    except Exception:
                        pass
            except Exception:
                pass

        results = []
        total_cost = 0.0
        for pos in positions:
            cost = float(pos["shares"]) * float(pos["avg_cost"])
            total_cost += cost
            cp = prices.get(pos["ticker"])
            if cp:
                cv = float(pos["shares"]) * cp
                gain = cv - cost
                gain_pct = (gain / cost * 100) if cost else 0
                results.append({
                    **pos,
                    "current_price": round(cp, 6),
                    "current_value": round(cv, 2),
                    "cost_basis": round(cost, 2),
                    "gain": round(gain, 2),
                    "gain_pct": round(gain_pct, 2),
                })
            else:
                results.append({**pos, "current_price": None,
                                "current_value": None, "cost_basis": round(cost, 2),
                                "gain": None, "gain_pct": None})

        cash = round(portfolio.get("capital", 0.0) - total_cost, 2)

        out = (results, cash)
        self._positions_cache = {k: v for k, v in self._positions_cache.items() if k[0] != portfolio_id}
        self._positions_cache[cache_key] = {"value": deepcopy(out), "timestamp": time.time()}
        return out

    def get_summary(self, portfolio_id, positions=None, cash=None, include_risk=False):
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        if positions is None or cash is None:
            positions, cash = self.get_positions_with_returns(portfolio_id)
        position_value = sum(p["current_value"] or p["cost_basis"] for p in positions)
        total_value = max(0.0, cash) + position_value
        total_gain = total_value - portfolio.get("capital", 0.0)
        total_gain_pct = (total_gain / portfolio["capital"] * 100) if portfolio.get("capital") else 0

        result = {
            "total_value": round(total_value, 2),
            "cash": round(max(0.0, cash), 2),
            "position_value": round(position_value, 2),
            "total_gain": round(total_gain, 2),
            "total_gain_pct": round(total_gain_pct, 2),
        }
        if include_risk:
            result["risk"] = self.calculate_risk_metrics(portfolio_id)
        return result

    def calculate_risk_metrics(self, portfolio_id):
        """Calculate Volatility, Beta, and Sharpe Ratio using 1Y of historical data."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio or not portfolio.get("positions"):
            return {"volatility": 0, "beta": 0, "sharpe": 0}

        # 1. Check pre-computed file (instant for default portfolios)
        if portfolio_id in self._precomputed_risk:
            return deepcopy(self._precomputed_risk[portfolio_id])

        # 2. Check runtime cache
        cache_key = (portfolio_id, self._portfolio_signature(portfolio))
        cached = self._risk_cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < 900:
            return deepcopy(cached["value"])

        tickers = [p["ticker"] for p in portfolio["positions"]]
        benchmark = portfolio.get("benchmark", "SPY")
        all_tickers = tickers + [benchmark]

        try:
            data = yf.download(all_tickers, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)["Close"]
            if isinstance(data, pd.Series):
                data = data.to_frame(name=tickers[0])

            returns = data.pct_change().dropna()

            available_tickers = [t for t in tickers if t in returns.columns]
            if not available_tickers or benchmark not in returns.columns:
                risk = {"volatility": 0, "beta": 0, "sharpe": 0}
                self._risk_cache[cache_key] = {"value": deepcopy(risk), "timestamp": time.time()}
                return risk

            available_positions = [p for p in portfolio["positions"] if p["ticker"] in available_tickers]

            weights = []
            total_cost = sum(float(p["shares"]) * float(p["avg_cost"]) for p in available_positions)
            for p in available_positions:
                weight = (float(p["shares"]) * float(p["avg_cost"])) / total_cost if total_cost else 0
                weights.append(weight)

            port_returns = (returns[available_tickers] * weights).sum(axis=1)
            bench_returns = returns[benchmark]

            vol = port_returns.std() * (252**0.5) * 100

            covariance = port_returns.cov(bench_returns)
            variance = bench_returns.var()
            beta = covariance / variance if variance else 0

            rf = 0.04
            excess_return = port_returns.mean() * 252 - rf
            sharpe = excess_return / (port_returns.std() * (252**0.5)) if port_returns.std() else 0

            risk = {
                "volatility": round(float(vol), 2),
                "beta": round(float(beta), 2),
                "sharpe": round(float(sharpe), 2)
            }
            self._risk_cache = {k: v for k, v in self._risk_cache.items() if k[0] != portfolio_id}
            self._risk_cache[cache_key] = {"value": deepcopy(risk), "timestamp": time.time()}
            return risk
        except Exception as e:
            print(f"Risk calculation error: {e}")
            return {"volatility": 0, "beta": 0, "sharpe": 0}

    def get_chart_data(self, portfolio_id, range_param="1y"):
        """Compute total portfolio value as a time series."""
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return {"error": "Portfolio not found"}

        positions = portfolio.get("positions", [])
        capital = portfolio.get("capital", 0.0)

        if not positions:
            return {"error": "No positions in portfolio"}

        RANGES = {
            "1d":  ("1d",   "5m",  True),
            "1w":  ("5d",   "60m", True),
            "1m":  ("1mo",  "1d",  False),
            "3m":  ("3mo",  "1d",  False),
            "6m":  ("6mo",  "1d",  False),
            "ytd": ("ytd",  "1d",  False),
            "1y":  ("1y",   "1d",  False),
        }
        period, interval, intraday = RANGES.get(range_param, RANGES["1y"])
        tickers = [p["ticker"] for p in positions]
        cache_key = (portfolio_id, range_param, self._portfolio_signature(portfolio))
        cached = self._chart_cache.get(cache_key)
        chart_ttl = 30 if intraday else 300
        if cached and (time.time() - cached["timestamp"]) < chart_ttl:
            return deepcopy(cached["value"])

        try:
            raw = yf.download(tickers, period=period, interval=interval,
                              progress=False, auto_adjust=True, threads=False)["Close"]
            if isinstance(raw, pd.Series):
                raw = raw.to_frame(name=tickers[0])
        except Exception as e:
            return {"error": f"Data fetch failed: {e}"}

        if raw.empty:
            return {"error": "No historical data"}

        total_cost = sum(float(p["shares"]) * float(p["avg_cost"]) for p in positions)
        cash = capital - total_cost

        chart_data = []
        for ts, row in raw.iterrows():
            pos_value = 0.0
            for pos in positions:
                price = row.get(pos["ticker"])
                if price is not None and not pd.isna(price):
                    pos_value += float(pos["shares"]) * float(price)
            total = max(0.0, cash) + pos_value
            time_val = int(ts.timestamp()) if intraday else ts.strftime("%Y-%m-%d")
            chart_data.append({"time": time_val, "value": round(total, 2)})

        if not chart_data:
            return {"error": "No chart data computed"}

        start_val = chart_data[0]["value"]
        end_val = chart_data[-1]["value"]
        period_change = round(end_val - start_val, 2)
        period_change_pct = round((end_val - start_val) / start_val * 100, 2) if start_val else 0
        total_gain = round(end_val - capital, 2)
        total_gain_pct = round((end_val - capital) / capital * 100, 2) if capital else 0

        payload = {
            "data": chart_data,
            "intraday": intraday,
            "current_value": end_val,
            "capital": capital,
            "period_change": period_change,
            "period_change_pct": period_change_pct,
            "total_gain": total_gain,
            "total_gain_pct": total_gain_pct,
        }
        self._chart_cache = {k: v for k, v in self._chart_cache.items() if k[0] != portfolio_id or k[1] != range_param}
        self._chart_cache[cache_key] = {"value": deepcopy(payload), "timestamp": time.time()}
        return payload

    # ── Trade / target / nav / alert methods ─────────────────────────────────

    def record_trade(self, portfolio_id, ticker, action, shares, price, date=None, notes=""):
        trade = {
            "ticker": ticker.upper(),
            "action": action,
            "shares": float(shares),
            "price": float(price),
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "notes": notes,
        }
        return self.db.record_trade(portfolio_id, trade)

    def get_trade_history(self, portfolio_id, ticker=None):
        return self.db.get_trades(portfolio_id, ticker)

    def set_position_targets(self, portfolio_id, ticker, target_weight=None, stop_loss=None, take_profit=None, tags=None, notes=None):
        updates = {}
        if target_weight is not None:
            updates["target_weight"] = float(target_weight)
        if stop_loss is not None:
            updates["stop_loss"] = float(stop_loss)
        if take_profit is not None:
            updates["take_profit"] = float(take_profit)
        if tags is not None:
            updates["tags"] = tags if isinstance(tags, list) else [tags]
        if notes is not None:
            updates["notes"] = str(notes)
        if not updates:
            return False
        ok = self.db.update_position(portfolio_id, ticker.upper(), updates)
        if ok:
            self._invalidate_runtime_caches(portfolio_id)
        return ok

    def get_nav_history(self, portfolio_id, days=365):
        return self.db.get_nav_history(portfolio_id, days)

    def record_daily_nav(self, portfolio_id):
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return False
        positions, cash = self.get_positions_with_returns(portfolio_id)
        position_value = sum(p["current_value"] or p["cost_basis"] for p in positions)
        total_value = max(0.0, cash) + position_value
        today = datetime.now().strftime("%Y-%m-%d")
        self.db.record_nav(portfolio_id, today, total_value, cash)
        return True

    def get_alerts(self, portfolio_id, dismissed=False):
        return self.db.get_alerts(portfolio_id, dismissed)

    def add_alert(self, portfolio_id, alert):
        return self.db.add_alert(portfolio_id, alert)

    def dismiss_alert(self, alert_id):
        return self.db.dismiss_alert(alert_id)
