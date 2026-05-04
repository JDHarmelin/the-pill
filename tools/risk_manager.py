"""
Risk Management & Position Sizing Engine
Manages single-portfolio risk with a fixed $10,000 paper capital wallet.
"""

from dataclasses import dataclass
from typing import Optional

DEFAULT_CAPITAL = 10000.0
MAX_POSITION_HEAT = 0.25       # Max 25% of portfolio in one position
MAX_SECTOR_HEAT = 0.40         # Max 40% in one sector
DEFAULT_RISK_PER_TRADE = 0.02  # 2% max risk per trade
MAX_TOTAL_HEAT = 0.60          # Max 60% of capital deployed


@dataclass
class PositionSizeResult:
    ticker: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_per_share: float
    reward_per_share: float
    risk_reward_ratio: float
    suggested_shares: int
    position_value: float
    capital_at_risk: float
    capital_at_risk_pct: float
    portfolio_heat_after: float
    can_execute: bool
    warning: Optional[str] = None


@dataclass
class RiskCheck:
    can_trade: bool
    reason: str
    current_heat: float
    max_heat: float
    sector_exposure: dict


class RiskManager:
    def __init__(self, total_capital: float = DEFAULT_CAPITAL):
        self.total_capital = total_capital

    def calculate_position_size(
        self,
        ticker: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_pct: float = DEFAULT_RISK_PER_TRADE,
        current_positions: list = None,
        sector: str = "",
    ) -> PositionSizeResult:
        """
        Calculate optimal position size based on risk parameters.
        """
        current_positions = current_positions or []
        risk_per_share = abs(entry_price - stop_loss)
        reward_per_share = abs(take_profit - entry_price)

        if risk_per_share <= 0:
            return PositionSizeResult(
                ticker=ticker,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_per_share=0,
                reward_per_share=reward_per_share,
                risk_reward_ratio=0,
                suggested_shares=0,
                position_value=0,
                capital_at_risk=0,
                capital_at_risk_pct=0,
                portfolio_heat_after=0,
                can_execute=False,
                warning="Stop loss must differ from entry price",
            )

        risk_reward = reward_per_share / risk_per_share
        capital_at_risk = self.total_capital * risk_pct
        suggested_shares = int(capital_at_risk / risk_per_share)

        if suggested_shares < 1:
            return PositionSizeResult(
                ticker=ticker,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_per_share=risk_per_share,
                reward_per_share=reward_per_share,
                risk_reward_ratio=risk_reward,
                suggested_shares=0,
                position_value=0,
                capital_at_risk=0,
                capital_at_risk_pct=0,
                portfolio_heat_after=0,
                can_execute=False,
                warning="Position too small — increase risk % or tighten stop",
            )

        position_value = suggested_shares * entry_price
        position_heat = position_value / self.total_capital

        # Calculate current portfolio heat
        current_heat = sum(
            p.get("current_value", p.get("shares", 0) * entry_price)
            for p in current_positions
        ) / self.total_capital

        heat_after = current_heat + position_heat
        warning = None
        can_execute = True

        # Check position heat limit
        if position_heat > MAX_POSITION_HEAT:
            # Scale down to max heat
            max_shares = int((self.total_capital * MAX_POSITION_HEAT) / entry_price)
            suggested_shares = max_shares
            position_value = suggested_shares * entry_price
            position_heat = position_value / self.total_capital
            heat_after = current_heat + position_heat
            warning = f"Position scaled down to {MAX_POSITION_HEAT*100:.0f}% max position size"

        # Check total portfolio heat
        if heat_after > MAX_TOTAL_HEAT:
            can_execute = False
            warning = f"Portfolio would be {heat_after*100:.1f}% deployed (max {MAX_TOTAL_HEAT*100:.0f}%)"

        # Check sector concentration
        if sector:
            sector_value = sum(
                p.get("current_value", p.get("shares", 0) * entry_price)
                for p in current_positions
                if p.get("sector") == sector
            )
            sector_heat = (sector_value + position_value) / self.total_capital
            if sector_heat > MAX_SECTOR_HEAT:
                can_execute = False
                warning = f"{sector} exposure would be {sector_heat*100:.1f}% (max {MAX_SECTOR_HEAT*100:.0f}%)"

        capital_at_risk = suggested_shares * risk_per_share
        capital_at_risk_pct = (capital_at_risk / self.total_capital) * 100

        return PositionSizeResult(
            ticker=ticker,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_share=risk_per_share,
            reward_per_share=reward_per_share,
            risk_reward_ratio=risk_reward,
            suggested_shares=suggested_shares,
            position_value=position_value,
            capital_at_risk=capital_at_risk,
            capital_at_risk_pct=capital_at_risk_pct,
            portfolio_heat_after=heat_after,
            can_execute=can_execute,
            warning=warning,
        )

    def check_portfolio_risk(self, positions: list, sector_map: dict = None) -> RiskCheck:
        """
        Check overall portfolio risk state.
        """
        sector_map = sector_map or {}
        total_value = sum(p.get("current_value", 0) or 0 for p in positions)
        current_heat = total_value / self.total_capital

        sector_exposure = {}
        for p in positions:
            sector = sector_map.get(p.get("ticker"), "Unknown")
            val = p.get("current_value", 0) or 0
            sector_exposure[sector] = sector_exposure.get(sector, 0) + val

        for sector, val in sector_exposure.items():
            sector_exposure[sector] = round(val / self.total_capital, 4)

        can_trade = current_heat < MAX_TOTAL_HEAT
        reason = "OK" if can_trade else f"Portfolio {current_heat*100:.1f}% deployed"

        # Flag over-concentration
        for p in positions:
            pos_heat = (p.get("current_value", 0) or 0) / self.total_capital
            if pos_heat > MAX_POSITION_HEAT:
                can_trade = False
                reason = f"{p['ticker']} is {pos_heat*100:.1f}% of portfolio (max {MAX_POSITION_HEAT*100:.0f}%)"
                break

        for sector, heat in sector_exposure.items():
            if heat > MAX_SECTOR_HEAT:
                can_trade = False
                reason = f"{sector} is {heat*100:.1f}% of portfolio (max {MAX_SECTOR_HEAT*100:.0f}%)"
                break

        return RiskCheck(
            can_trade=can_trade,
            reason=reason,
            current_heat=round(current_heat, 4),
            max_heat=MAX_TOTAL_HEAT,
            sector_exposure=sector_exposure,
        )

    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly fraction for optimal bet sizing.
        Returns fraction of capital to risk (0 = don't bet).
        """
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        # Use half-Kelly for safety
        return max(0.0, kelly / 2)
