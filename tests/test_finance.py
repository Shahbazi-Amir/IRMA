from decimal import Decimal

import pytest

from irma.domain.finance import (
    adjust_for_inflation,
    annualized_return,
    compound_interest,
    cumulative_return,
    maximum_drawdown,
    real_return,
    rial_to_toman,
    sharpe_ratio,
    simple_return,
    toman_to_rial,
    volatility,
)


def test_rial_to_toman() -> None:
    assert rial_to_toman(10_000_000) == Decimal("1000000")


def test_toman_to_rial() -> None:
    assert toman_to_rial(1_000_000) == Decimal("10000000")


def test_simple_return() -> None:
    assert simple_return(100, 125) == pytest.approx(0.25)


def test_simple_return_rejects_non_positive_initial_value() -> None:
    with pytest.raises(ValueError, match="initial_value"):
        simple_return(0, 100)


def test_cumulative_return() -> None:
    assert cumulative_return([0.1, -0.05, 0.2]) == pytest.approx(0.254)


def test_cumulative_return_rejects_loss_below_negative_one() -> None:
    with pytest.raises(ValueError, match="cannot be less"):
        cumulative_return([-1.1])


def test_annualized_return() -> None:
    assert annualized_return(0.21, 2) == pytest.approx(0.1)


def test_annualized_return_rejects_zero_years() -> None:
    with pytest.raises(ValueError, match="years"):
        annualized_return(0.1, 0)


def test_compound_interest() -> None:
    assert compound_interest(1_000_000, 0.2, 2, 12) == pytest.approx(
        1_486_914.617946,
        rel=1e-9,
    )


def test_compound_interest_rejects_negative_principal() -> None:
    with pytest.raises(ValueError, match="principal"):
        compound_interest(-1, 0.2, 1)


def test_adjust_for_inflation() -> None:
    assert adjust_for_inflation(1_400_000, 0.4) == pytest.approx(1_000_000)


def test_real_return() -> None:
    assert real_return(0.5, 0.4) == pytest.approx(0.0714285714)


def test_inflation_rate_rejects_negative_one() -> None:
    with pytest.raises(ValueError, match="inflation_rate"):
        real_return(0.1, -1)


def test_sample_volatility() -> None:
    assert volatility([0.01, 0.03, 0.02]) == pytest.approx(0.01)


def test_population_volatility_accepts_one_value() -> None:
    assert volatility([0.02], sample=False) == 0


def test_volatility_requires_enough_values() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        volatility([0.1])


def test_maximum_drawdown() -> None:
    assert maximum_drawdown([100, 120, 90, 110, 80]) == pytest.approx(1 / 3)


def test_maximum_drawdown_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        maximum_drawdown([])


def test_sharpe_ratio() -> None:
    ratio = sharpe_ratio([0.01, 0.02, 0.015, 0.03], risk_free_rate=0.05, periods_per_year=12)

    assert ratio == pytest.approx(5.9536220285, rel=1e-9)


def test_sharpe_ratio_rejects_zero_volatility() -> None:
    with pytest.raises(ValueError, match="volatility is zero"):
        sharpe_ratio([0.01, 0.01, 0.01])
