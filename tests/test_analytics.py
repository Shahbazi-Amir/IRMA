from datetime import date, timedelta

import pytest

from irma.analytics.funds import calculate_fund_analytics, ranking_score
from irma.analytics.scenarios import ScenarioAssumption, calculate_scenarios


def test_fund_analytics() -> None:
    start = date(2025, 1, 1)
    dates = [start + timedelta(days=index) for index in range(300)]
    nav = [100 + index * 0.2 + (index % 7) for index in range(300)]
    result = calculate_fund_analytics(
        dates=dates,
        nav_values=nav,
        inflation_rate=0.4,
        market_price=170,
        latest_nav=160,
    )
    assert result.cagr is not None
    assert result.data_quality_score == 1.0
    assert result.nav_premium_discount == pytest.approx(0.0625)


def test_fund_analytics_rejects_missing_alignment() -> None:
    with pytest.raises(ValueError):
        calculate_fund_analytics(dates=[date.today()], nav_values=[100, 101])


def test_ranking_withholds_when_data_missing() -> None:
    assert (
        ranking_score(
            cagr=None,
            maximum_drawdown_value=0.1,
            liquidity_score=0.8,
            data_quality_score=1.0,
            age_years=5,
        )
        is None
    )


def test_young_fund_is_penalized() -> None:
    mature = ranking_score(
        cagr=0.3,
        maximum_drawdown_value=0.2,
        liquidity_score=0.8,
        data_quality_score=0.9,
        age_years=5,
    )
    young = ranking_score(
        cagr=0.3,
        maximum_drawdown_value=0.2,
        liquidity_score=0.8,
        data_quality_score=0.9,
        age_years=0.5,
    )
    assert mature is not None and young is not None and mature > young


def test_scenarios_require_three_named_assumptions() -> None:
    assumptions = [
        ScenarioAssumption(
            name="pessimistic",
            annual_return=-0.1,
            annual_inflation=0.5,
            possible_drawdown=0.3,
            uncertainty="high",
        ),
        ScenarioAssumption(
            name="base",
            annual_return=0.2,
            annual_inflation=0.35,
            possible_drawdown=0.2,
            uncertainty="high",
        ),
        ScenarioAssumption(
            name="optimistic",
            annual_return=0.4,
            annual_inflation=0.25,
            possible_drawdown=0.15,
            uncertainty="very_high",
        ),
    ]
    results = calculate_scenarios(
        principal=1_000_000, monthly_contribution=0, months=12, assumptions=assumptions
    )
    assert [item.name for item in results] == ["pessimistic", "base", "optimistic"]
    assert results[0].nominal_value < results[2].nominal_value
