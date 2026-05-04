"""
Rebalancing Engine — generates rebalancing plans for portfolios.
"""

from dataclasses import dataclass
from typing import List

import yfinance as yf


@dataclass
class RebalanceAction:
    ticker: str
    action: str  # "buy" | "sell"
    current_shares: float
    target_shares: float
    delta_shares: float
    estimated_price: float
    estimated_value: float
    reason: str


class RebalanceEngine:
    def _get_positions_and_prices(self, portfolio_id, portfolio_mgr):
        positions, cash = portfolio_mgr.get_positions_with_returns(portfolio_id)
        portfolio = portfolio_mgr.get_portfolio(portfolio_id)
        position_value = sum(
            p.get("current_value") or p.get("cost_basis", 0) for p in positions
        )
        total_value = max(0.0, cash) + position_value
        return positions, cash, portfolio, total_value

    def target_weight_rebalance(
        self, portfolio_id, portfolio_mgr, price_source=None
    ) -> List[RebalanceAction]:
        """
        Bring positions back to their target_weight.
        If total target weights exceed 100%, scales all down proportionally.
        """
        positions, cash, portfolio, total_value = self._get_positions_and_prices(
            portfolio_id, portfolio_mgr
        )
        if not positions or total_value <= 0:
            return []

        target_positions = [p for p in positions if p.get("target_weight") is not None]
        if not target_positions:
            return []

        total_target_weight = sum(p.get("target_weight", 0) for p in target_positions)
        scale = 1.0 / total_target_weight if total_target_weight > 1.0 else 1.0

        actions = []
        for pos in target_positions:
            target_weight = pos.get("target_weight", 0) * scale
            price = pos.get("current_price")
            if price is None or price <= 0:
                continue

            current_shares = float(pos.get("shares", 0))
            current_value = pos.get("current_value") or pos.get("cost_basis", 0)
            target_value = total_value * target_weight
            target_shares = target_value / price
            delta = target_shares - current_shares

            if abs(delta) < 0.01:
                continue

            action = "buy" if delta > 0 else "sell"
            actions.append(
                RebalanceAction(
                    ticker=pos["ticker"],
                    action=action,
                    current_shares=round(current_shares, 4),
                    target_shares=round(target_shares, 4),
                    delta_shares=round(delta, 4),
                    estimated_price=round(price, 2),
                    estimated_value=round(abs(delta) * price, 2),
                    reason=f"Target weight {target_weight:.1%} vs current {current_value/total_value:.1%}",
                )
            )

        actions.sort(key=lambda a: 0 if a.action == "sell" else 1)
        return actions

    def equal_weight_rebalance(
        self, portfolio_id, portfolio_mgr, price_source=None
    ) -> List[RebalanceAction]:
        """
        Equal-weight all positions. Cash gets distributed across positions.
        """
        positions, cash, portfolio, total_value = self._get_positions_and_prices(
            portfolio_id, portfolio_mgr
        )
        if not positions or total_value <= 0:
            return []

        n = len(positions)
        target_weight = 1.0 / n

        actions = []
        for pos in positions:
            price = pos.get("current_price")
            if price is None or price <= 0:
                continue

            current_shares = float(pos.get("shares", 0))
            current_value = pos.get("current_value") or pos.get("cost_basis", 0)
            target_value = total_value * target_weight
            target_shares = target_value / price
            delta = target_shares - current_shares

            if abs(delta) < 0.01:
                continue

            action = "buy" if delta > 0 else "sell"
            actions.append(
                RebalanceAction(
                    ticker=pos["ticker"],
                    action=action,
                    current_shares=round(current_shares, 4),
                    target_shares=round(target_shares, 4),
                    delta_shares=round(delta, 4),
                    estimated_price=round(price, 2),
                    estimated_value=round(abs(delta) * price, 2),
                    reason=f"Equal weight {target_weight:.1%} vs current {current_value/total_value:.1%}",
                )
            )

        actions.sort(key=lambda a: 0 if a.action == "sell" else 1)
        return actions

    def conviction_weighted_rebalance(
        self, portfolio_id, portfolio_mgr, signals, price_source=None
    ) -> List[RebalanceAction]:
        """
        Weight by conviction score. Higher conviction = larger weight.
        Only positions with positive conviction receive allocations.
        """
        positions, cash, portfolio, total_value = self._get_positions_and_prices(
            portfolio_id, portfolio_mgr
        )
        if not positions or total_value <= 0 or not signals:
            return []

        conviction_map = {}
        for s in signals:
            if s.conviction > 0:
                conviction_map[s.ticker] = conviction_map.get(s.ticker, 0) + s.conviction

        total_conviction = sum(conviction_map.values())
        if total_conviction <= 0:
            return []

        actions = []
        for pos in positions:
            ticker = pos["ticker"]
            price = pos.get("current_price")
            if price is None or price <= 0:
                continue

            conv = conviction_map.get(ticker, 0)
            if conv <= 0:
                continue

            target_weight = conv / total_conviction
            current_shares = float(pos.get("shares", 0))
            current_value = pos.get("current_value") or pos.get("cost_basis", 0)
            target_value = total_value * target_weight
            target_shares = target_value / price
            delta = target_shares - current_shares

            if abs(delta) < 0.01:
                continue

            action = "buy" if delta > 0 else "sell"
            actions.append(
                RebalanceAction(
                    ticker=ticker,
                    action=action,
                    current_shares=round(current_shares, 4),
                    target_shares=round(target_shares, 4),
                    delta_shares=round(delta, 4),
                    estimated_price=round(price, 2),
                    estimated_value=round(abs(delta) * price, 2),
                    reason=f"Conviction weight {target_weight:.1%} vs current {current_value/total_value:.1%}",
                )
            )

        actions.sort(key=lambda a: 0 if a.action == "sell" else 1)
        return actions

    def risk_parity_rebalance(
        self, portfolio_id, portfolio_mgr, price_source=None
    ) -> List[RebalanceAction]:
        """
        Equal risk contribution. Higher volatility = smaller weight.
        Weights are proportional to inverse volatility.
        """
        positions, cash, portfolio, total_value = self._get_positions_and_prices(
            portfolio_id, portfolio_mgr
        )
        if not positions or total_value <= 0:
            return []

        inv_vols = {}
        for pos in positions:
            ticker = pos["ticker"]
            try:
                hist = yf.Ticker(ticker).history(period="1y", interval="1d")
                if not hist.empty and len(hist) > 20:
                    returns = hist["Close"].pct_change().dropna()
                    vol = returns.std() * (252**0.5)
                    if vol and vol > 0:
                        inv_vols[ticker] = 1.0 / vol
            except Exception:
                pass

        total_inv_vol = sum(inv_vols.values())
        if total_inv_vol <= 0:
            return []

        actions = []
        for pos in positions:
            ticker = pos["ticker"]
            price = pos.get("current_price")
            if price is None or price <= 0:
                continue

            inv_vol = inv_vols.get(ticker, 0)
            if inv_vol <= 0:
                continue

            target_weight = inv_vol / total_inv_vol
            current_shares = float(pos.get("shares", 0))
            current_value = pos.get("current_value") or pos.get("cost_basis", 0)
            target_value = total_value * target_weight
            target_shares = target_value / price
            delta = target_shares - current_shares

            if abs(delta) < 0.01:
                continue

            action = "buy" if delta > 0 else "sell"
            actions.append(
                RebalanceAction(
                    ticker=ticker,
                    action=action,
                    current_shares=round(current_shares, 4),
                    target_shares=round(target_shares, 4),
                    delta_shares=round(delta, 4),
                    estimated_price=round(price, 2),
                    estimated_value=round(abs(delta) * price, 2),
                    reason=f"Risk parity weight {target_weight:.1%} vs current {current_value/total_value:.1%}",
                )
            )

        actions.sort(key=lambda a: 0 if a.action == "sell" else 1)
        return actions
