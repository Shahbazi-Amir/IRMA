from decimal import Decimal

import pytest

from irma.domain.finance import (
    adjust_for_inflation,
    annualized_return,
    compound_interest,
    compound_with_contributions,
    cumulative_return,
    maximum_drawdown,
    real_return,
    recovery_period,
    rial_to_toman,
    sharpe_ratio,
    simple_return,
    sortino_ratio,
    toman_to_rial,
    volatility,
)


def test_currency_conversion() -> None:
    assert rial_to_toman(10_000_000) == Decimal("1000000")
    assert toman_to_rial(1_000_000) == Decimal("10000000")


def test_returns_and_cagr() -> None:
    assert simple_return(100, 125) == pytest.approx(0.25)
    assert cumulative_return([0.1, -0.05, 0.2]) == pytest.approx(0.254)
    assert annualized_return(0.21, 2) == pytest.approx(0.1)


def test_compound_interest() -> None:
    assert compound_interest(1_000_000, 0.2, 2, 12) == pytest.approx(1_486_914.617946)


def test_inflation_and_real_return() -> None:
    assert adjust_for_inflation(1_400_000, 0.4) == pytest.approx(1_000_000)
    assert real_return(0.5, 0.4) == pytest.approx(0.0714285714)


def test_risk_metrics() -> None:
    returns = [0.01, -0.02, 0.03, -0.01, 0.02]
    assert volatility(returns) > 0
    assert sharpe_ratio(returns, periods_per_year=12) != 0
    assert sortino_ratio(returns, periods_per_year=12) != 0
    assert maximum_drawdown([100, 120, 90, 110, 80]) == pytest.approx(1 / 3)
    assert recovery_period([100, 120, 90, 100, 121]) == 3


def test_compound_with_monthly_contributions() -> None:
    result = compound_with_contributions(
        principal=1_000_000,
        monthly_contribution=100_000,
        annual_rate=0.24,
        annual_inflation=0.4,
        months=24,
    )
    assert result.total_contributions == 3_400_000
    assert result.final_nominal > result.total_contributions
    assert result.final_real < result.final_nominal
    assert len(result.timeline) == 25


def test_annual_compounding_only_applies_annually() -> None:
    result = compound_with_contributions(
        principal=1_000_000,
        monthly_contribution=0,
        annual_rate=0.2,
        months=12,
        compounding="annual",
    )
    assert result.final_nominal == pytest.approx(1_200_000)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: simple_return(0, 1), "initial_value"),
        (lambda: annualized_return(0.1, 0), "years"),
        (lambda: real_return(0.1, -1), "inflation"),
        (lambda: maximum_drawdown([]), "empty"),
        (lambda: sharpe_ratio([0.1, 0.1]), "volatility"),
        (lambda: sortino_ratio([0.1, 0.2]), "downside"),
    ],
)
def test_invalid_inputs(call, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        call()
