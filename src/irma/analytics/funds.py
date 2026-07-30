"""Fund analytics and within-category ranking helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from irma.domain.finance import (
    annualized_return,
    maximum_drawdown,
    real_return,
    recovery_period,
    sharpe_ratio,
    sortino_ratio,
    volatility,
)


@dataclass(frozen=True, slots=True)
class FundAnalytics:
    total_return: float
    cagr: float | None
    real_total_return: float | None
    volatility: float | None
    maximum_drawdown: float
    recovery_periods: int | None
    sharpe: float | None
    sortino: float | None
    positive_period_ratio: float | None
    nav_premium_discount: float | None
    data_quality_score: float


def calculate_fund_analytics(
    *,
    dates: list[date],
    nav_values: list[float],
    inflation_rate: float | None = None,
    market_price: float | None = None,
    latest_nav: float | None = None,
    risk_free_rate: float = 0.0,
) -> FundAnalytics:
    if len(dates) != len(nav_values) or len(nav_values) < 2:
        raise ValueError("at least two aligned NAV observations are required")
    if any(value <= 0 for value in nav_values):
        raise ValueError("NAV observations must be positive")
    returns = [nav_values[index] / nav_values[index - 1] - 1 for index in range(1, len(nav_values))]
    total = nav_values[-1] / nav_values[0] - 1
    days = (dates[-1] - dates[0]).days
    cagr = annualized_return(total, days / 365.25) if days >= 30 else None
    annual_volatility = volatility(returns) * (252**0.5) if len(returns) >= 2 else None
    try:
        sharpe = sharpe_ratio(returns, risk_free_rate=risk_free_rate, periods_per_year=252)
    except ValueError:
        sharpe = None
    try:
        sortino = sortino_ratio(returns, periods_per_year=252)
    except ValueError:
        sortino = None
    premium = None
    if market_price is not None and latest_nav is not None and latest_nav > 0:
        premium = market_price / latest_nav - 1
    quality = min(1.0, len(nav_values) / 252) * (1.0 if days > 0 else 0.0)
    return FundAnalytics(
        total_return=total,
        cagr=cagr,
        real_total_return=real_return(total, inflation_rate) if inflation_rate is not None else None,
        volatility=annual_volatility,
        maximum_drawdown=maximum_drawdown(nav_values),
        recovery_periods=recovery_period(nav_values),
        sharpe=sharpe,
        sortino=sortino,
        positive_period_ratio=sum(item > 0 for item in returns) / len(returns),
        nav_premium_discount=premium,
        data_quality_score=quality,
    )


def ranking_score(
    *,
    cagr: float | None,
    maximum_drawdown_value: float | None,
    liquidity_score: float | None,
    data_quality_score: float,
    age_years: float,
) -> float | None:
    if cagr is None or maximum_drawdown_value is None or liquidity_score is None:
        return None
    age_factor = min(1.0, max(0.2, age_years / 3))
    return (
        cagr * 0.35
        - maximum_drawdown_value * 0.25
        + liquidity_score * 0.20
        + data_quality_score * 0.20
    ) * age_factor
