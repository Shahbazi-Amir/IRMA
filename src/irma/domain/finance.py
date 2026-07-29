"""Pure financial calculation functions used by IRMA."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from decimal import Decimal

RIALS_PER_TOMAN = Decimal(10)


def _positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def rial_to_toman(amount_rial: Decimal | int | str) -> Decimal:
    """Convert Iranian rial to toman without rounding."""

    return Decimal(amount_rial) / RIALS_PER_TOMAN


def toman_to_rial(amount_toman: Decimal | int | str) -> Decimal:
    """Convert Iranian toman to rial without rounding."""

    return Decimal(amount_toman) * RIALS_PER_TOMAN


def simple_return(initial_value: float, final_value: float) -> float:
    """Calculate simple return as a decimal ratio."""

    _positive(initial_value, "initial_value")
    return final_value / initial_value - 1


def cumulative_return(period_returns: Iterable[float]) -> float:
    """Compound period returns into one cumulative return."""

    growth = 1.0
    for period_return in period_returns:
        if period_return < -1:
            raise ValueError("period returns cannot be less than -1")
        growth *= 1 + period_return
    return growth - 1


def annualized_return(total_return: float, years: float) -> float:
    """Calculate compound annual growth from a total return and duration."""

    _positive(years, "years")
    if total_return < -1:
        raise ValueError("total_return cannot be less than -1")
    return (1 + total_return) ** (1 / years) - 1


def compound_interest(
    principal: float,
    annual_rate: float,
    years: float,
    compounds_per_year: int = 1,
) -> float:
    """Calculate a future value using periodic compounding."""

    if principal < 0:
        raise ValueError("principal cannot be negative")
    _positive(years, "years")
    if compounds_per_year <= 0:
        raise ValueError("compounds_per_year must be greater than zero")
    periodic_base = 1 + annual_rate / compounds_per_year
    if periodic_base < 0:
        raise ValueError("annual_rate is too negative for the compounding frequency")
    return principal * periodic_base ** (compounds_per_year * years)


def adjust_for_inflation(nominal_value: float, inflation_rate: float) -> float:
    """Express a nominal value in current purchasing-power terms."""

    if inflation_rate <= -1:
        raise ValueError("inflation_rate must be greater than -1")
    return nominal_value / (1 + inflation_rate)


def real_return(nominal_return: float, inflation_rate: float) -> float:
    """Calculate the inflation-adjusted return using the Fisher relation."""

    if inflation_rate <= -1:
        raise ValueError("inflation_rate must be greater than -1")
    return (1 + nominal_return) / (1 + inflation_rate) - 1


def volatility(period_returns: Sequence[float], *, sample: bool = True) -> float:
    """Calculate period-return standard deviation."""

    minimum = 2 if sample else 1
    if len(period_returns) < minimum:
        raise ValueError(f"at least {minimum} return values are required")
    return statistics.stdev(period_returns) if sample else statistics.pstdev(period_returns)


def maximum_drawdown(portfolio_values: Sequence[float]) -> float:
    """Return the largest peak-to-trough decline as a positive ratio."""

    if not portfolio_values:
        raise ValueError("portfolio_values cannot be empty")
    if any(value <= 0 for value in portfolio_values):
        raise ValueError("portfolio values must be greater than zero")

    peak = portfolio_values[0]
    maximum = 0.0
    for value in portfolio_values:
        peak = max(peak, value)
        drawdown = (peak - value) / peak
        maximum = max(maximum, drawdown)
    return maximum


def sharpe_ratio(
    period_returns: Sequence[float],
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 12,
) -> float:
    """Calculate an annualized Sharpe ratio from periodic returns."""

    if len(period_returns) < 2:
        raise ValueError("at least two return values are required")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be greater than zero")

    risk_free_per_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = [value - risk_free_per_period for value in period_returns]
    deviation = statistics.stdev(excess_returns)
    if math.isclose(deviation, 0.0, abs_tol=1e-15):
        raise ValueError("Sharpe ratio is undefined when volatility is zero")
    return statistics.mean(excess_returns) / deviation * math.sqrt(periods_per_year)
