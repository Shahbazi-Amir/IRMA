"""Frequency-aware rolling historical analysis without forecasting claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from statistics import median

from irma.domain.finance import maximum_drawdown


@dataclass(frozen=True, slots=True)
class WindowDistribution:
    horizon_periods: int
    sample_count: int
    median_return: float
    percentile_25: float
    percentile_75: float
    worst_return: float
    best_return: float
    positive_ratio: float


def rolling_returns(values: list[float], horizon_periods: int) -> list[float]:
    if horizon_periods < 1:
        raise ValueError("horizon_periods must be positive")
    if any(value <= 0 for value in values):
        raise ValueError("historical values must be positive")
    return [
        values[index] / values[index - horizon_periods] - 1
        for index in range(horizon_periods, len(values))
    ]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def window_distribution(values: list[float], horizon_periods: int) -> WindowDistribution:
    returns = rolling_returns(values, horizon_periods)
    if not returns:
        raise ValueError("insufficient history for requested horizon")
    return WindowDistribution(
        horizon_periods=horizon_periods,
        sample_count=len(returns),
        median_return=median(returns),
        percentile_25=_percentile(returns, 0.25),
        percentile_75=_percentile(returns, 0.75),
        worst_return=min(returns),
        best_return=max(returns),
        positive_ratio=sum(item > 0 for item in returns) / len(returns),
    )


def historical_report(
    dates: list[date], values: list[float], horizon_periods: int
) -> dict[str, object]:
    if len(dates) != len(values) or dates != sorted(dates):
        raise ValueError("dates and values must be aligned and ordered")
    distribution = window_distribution(values, horizon_periods)
    return {
        "coverage_start": dates[0],
        "coverage_end": dates[-1],
        "observation_count": len(values),
        "total_return": values[-1] / values[0] - 1,
        "maximum_drawdown": maximum_drawdown(values),
        "window_distribution": asdict(distribution),
        "notice": "بازده‌های تاریخی پیش‌بینی یا تضمین بازده آینده نیستند.",
    }
