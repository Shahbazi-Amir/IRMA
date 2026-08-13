"""Typed, gated financial scenarios; missing evidence never becomes a return estimate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from math import pow

from irma.services.historical_intelligence import window_distribution


@dataclass(frozen=True, slots=True)
class ScenarioAmount:
    principal_toman: Decimal
    profit_loss_toman: Decimal
    final_value_toman: Decimal
    period_return: float


def annual_effective_to_period_rate(annual_effective_rate: float, days: int) -> float:
    if annual_effective_rate <= -1 or days < 1:
        raise ValueError("rate must exceed -100% and days must be positive")
    return pow(1 + annual_effective_rate, days / 365.25) - 1


def scenario_amount(principal_toman: Decimal, period_return: float) -> ScenarioAmount:
    final = principal_toman * Decimal(str(1 + period_return))
    return ScenarioAmount(
        principal_toman=principal_toman,
        profit_loss_toman=final - principal_toman,
        final_value_toman=final,
        period_return=period_return,
    )


def historical_scenarios(
    principal_toman: Decimal, values: list[float], horizon_periods: int
) -> dict[str, object]:
    distribution = window_distribution(values, horizon_periods)
    return {
        "weak": asdict(scenario_amount(principal_toman, distribution.percentile_25)),
        "median": asdict(scenario_amount(principal_toman, distribution.median_return)),
        "strong": asdict(scenario_amount(principal_toman, distribution.percentile_75)),
        "worst_observed_return": distribution.worst_return,
        "best_observed_return": distribution.best_return,
        "positive_window_ratio": distribution.positive_ratio,
        "sample_count": distribution.sample_count,
        "value_semantics": "historical_window_return",
    }
