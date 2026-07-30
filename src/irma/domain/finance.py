"""Pure financial calculations used across IRMA."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

RIALS_PER_TOMAN = Decimal(10)


def _positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def rial_to_toman(amount_rial: Decimal | int | str) -> Decimal:
    return Decimal(amount_rial) / RIALS_PER_TOMAN


def toman_to_rial(amount_toman: Decimal | int | str) -> Decimal:
    return Decimal(amount_toman) * RIALS_PER_TOMAN


def simple_return(initial_value: float, final_value: float) -> float:
    _positive(initial_value, "initial_value")
    return final_value / initial_value - 1


def cumulative_return(period_returns: Iterable[float]) -> float:
    growth = 1.0
    for period_return in period_returns:
        if period_return < -1:
            raise ValueError("period returns cannot be less than -1")
        growth *= 1 + period_return
    return growth - 1


def annualized_return(total_return: float, years: float) -> float:
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
    if inflation_rate <= -1:
        raise ValueError("inflation_rate must be greater than -1")
    return nominal_value / (1 + inflation_rate)


def real_return(nominal_return: float, inflation_rate: float) -> float:
    if inflation_rate <= -1:
        raise ValueError("inflation_rate must be greater than -1")
    return (1 + nominal_return) / (1 + inflation_rate) - 1


def volatility(period_returns: Sequence[float], *, sample: bool = True) -> float:
    minimum = 2 if sample else 1
    if len(period_returns) < minimum:
        raise ValueError(f"at least {minimum} return values are required")
    return statistics.stdev(period_returns) if sample else statistics.pstdev(period_returns)


def maximum_drawdown(portfolio_values: Sequence[float]) -> float:
    if not portfolio_values:
        raise ValueError("portfolio_values cannot be empty")
    if any(value <= 0 for value in portfolio_values):
        raise ValueError("portfolio values must be greater than zero")
    peak = portfolio_values[0]
    maximum = 0.0
    for value in portfolio_values:
        peak = max(peak, value)
        maximum = max(maximum, (peak - value) / peak)
    return maximum


def sharpe_ratio(
    period_returns: Sequence[float],
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 12,
) -> float:
    if len(period_returns) < 2:
        raise ValueError("at least two return values are required")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be greater than zero")
    risk_free_per_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = [item - risk_free_per_period for item in period_returns]
    deviation = statistics.stdev(excess)
    if math.isclose(deviation, 0.0, abs_tol=1e-15):
        raise ValueError("Sharpe ratio is undefined when volatility is zero")
    return statistics.mean(excess) / deviation * math.sqrt(periods_per_year)


def sortino_ratio(
    period_returns: Sequence[float],
    *,
    target_return: float = 0.0,
    periods_per_year: int = 12,
) -> float:
    if len(period_returns) < 2:
        raise ValueError("at least two return values are required")
    downside = [min(0.0, item - target_return) ** 2 for item in period_returns]
    downside_deviation = math.sqrt(sum(downside) / len(downside))
    if math.isclose(downside_deviation, 0.0, abs_tol=1e-15):
        raise ValueError("Sortino ratio is undefined without downside volatility")
    return (statistics.mean(period_returns) - target_return) / downside_deviation * math.sqrt(
        periods_per_year
    )


def recovery_period(portfolio_values: Sequence[float]) -> int | None:
    if len(portfolio_values) < 2:
        return 0
    peak_index = 0
    peak_value = portfolio_values[0]
    worst_peak_index = 0
    worst_index = 0
    worst_drawdown = 0.0
    for index, value in enumerate(portfolio_values):
        if value > peak_value:
            peak_value = value
            peak_index = index
        drawdown = (peak_value - value) / peak_value
        if drawdown > worst_drawdown:
            worst_drawdown = drawdown
            worst_peak_index = peak_index
            worst_index = index
    if worst_drawdown == 0:
        return 0
    target = portfolio_values[worst_peak_index]
    for index in range(worst_index + 1, len(portfolio_values)):
        if portfolio_values[index] >= target:
            return index - worst_peak_index
    return None


@dataclass(frozen=True, slots=True)
class CompoundResult:
    final_nominal: float
    final_real: float
    total_contributions: float
    nominal_profit: float
    timeline: list[dict[str, float | int]]


def compound_with_contributions(
    *,
    principal: float,
    monthly_contribution: float,
    annual_rate: float,
    months: int,
    compounding: str = "monthly",
    annual_inflation: float = 0.0,
) -> CompoundResult:
    if principal < 0 or monthly_contribution < 0:
        raise ValueError("principal and monthly contribution cannot be negative")
    if months <= 0:
        raise ValueError("months must be greater than zero")
    if annual_inflation <= -1:
        raise ValueError("annual inflation must be greater than -1")
    if compounding not in {"monthly", "annual"}:
        raise ValueError("compounding must be monthly or annual")
    balance = principal
    timeline: list[dict[str, float | int]] = [{"month": 0, "nominal": balance, "real": balance}]
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    for month in range(1, months + 1):
        balance += monthly_contribution
        if compounding == "monthly":
            balance *= 1 + monthly_rate
        elif month % 12 == 0:
            balance *= 1 + annual_rate
        inflation_factor = (1 + annual_inflation) ** (month / 12)
        timeline.append(
            {"month": month, "nominal": balance, "real": balance / inflation_factor}
        )
    contributions = principal + monthly_contribution * months
    final_real = float(timeline[-1]["real"])
    return CompoundResult(
        final_nominal=balance,
        final_real=final_real,
        total_contributions=contributions,
        nominal_profit=balance - contributions,
        timeline=timeline,
    )
