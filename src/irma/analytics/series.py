"""Frequency-explicit analytics shared by funds, indices and instruments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import mean, stdev

from irma.domain.finance import maximum_drawdown, recovery_period


@dataclass(frozen=True, slots=True)
class SeriesMetrics:
    observation_count: int
    total_return: float
    cagr: float | None
    annualized_volatility: float | None
    maximum_drawdown: float
    recovery_periods: int | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    positive_period_ratio: float


def periodic_returns(values: list[float]) -> list[float]:
    if len(values) < 2 or any(value <= 0 for value in values):
        raise ValueError("at least two positive observations are required")
    return [values[index] / values[index - 1] - 1 for index in range(1, len(values))]


def calculate_series_metrics(
    dates: list[date],
    values: list[float],
    *,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> SeriesMetrics:
    if len(dates) != len(values) or dates != sorted(dates):
        raise ValueError("dates and values must be aligned and ordered")
    returns = periodic_returns(values)
    years = (dates[-1] - dates[0]).days / 365.25
    total = values[-1] / values[0] - 1
    cagr = (values[-1] / values[0]) ** (1 / years) - 1 if years >= 30 / 365.25 else None
    volatility = stdev(returns) * math.sqrt(periods_per_year) if len(returns) >= 2 else None
    periodic_rf = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = [item - periodic_rf for item in returns]
    sharpe = None
    if len(excess) >= 2 and stdev(excess) > 0:
        sharpe = mean(excess) / stdev(excess) * math.sqrt(periods_per_year)
    downside = [min(0.0, item - periodic_rf) for item in returns]
    downside_deviation = math.sqrt(mean([item * item for item in downside]))
    sortino = (
        mean(excess) / downside_deviation * math.sqrt(periods_per_year)
        if downside_deviation > 0
        else None
    )
    drawdown = maximum_drawdown(values)
    return SeriesMetrics(
        observation_count=len(values),
        total_return=total,
        cagr=cagr,
        annualized_volatility=volatility,
        maximum_drawdown=drawdown,
        recovery_periods=recovery_period(values),
        sharpe=sharpe,
        sortino=sortino,
        calmar=cagr / abs(drawdown) if cagr is not None and drawdown < 0 else None,
        positive_period_ratio=sum(item > 0 for item in returns) / len(returns),
    )


def real_total_return(nominal_return: float, inflation_return: float) -> float:
    if inflation_return <= -1:
        raise ValueError("inflation return must be greater than -100%")
    return (1 + nominal_return) / (1 + inflation_return) - 1


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("aligned series with at least two values are required")
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((item - left_mean) ** 2 for item in left)
        * sum((item - right_mean) ** 2 for item in right)
    )
    return numerator / denominator if denominator else None


def tracking_error(asset_returns: list[float], benchmark_returns: list[float]) -> float | None:
    if len(asset_returns) != len(benchmark_returns) or len(asset_returns) < 2:
        raise ValueError("aligned return series are required")
    active = [a - b for a, b in zip(asset_returns, benchmark_returns, strict=True)]
    return stdev(active) * math.sqrt(252) if stdev(active) > 0 else None


def information_ratio(asset_returns: list[float], benchmark_returns: list[float]) -> float | None:
    error = tracking_error(asset_returns, benchmark_returns)
    if error is None:
        return None
    active = [a - b for a, b in zip(asset_returns, benchmark_returns, strict=True)]
    return mean(active) * 252 / error
