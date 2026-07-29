from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import BASE_ALLOCATIONS, recommend_allocation


def make_profile(**overrides: object) -> InvestorProfile:
    data: dict[str, object] = {
        "capital_toman": 1_000_000,
        "monthly_contribution_toman": 0,
        "horizon_months": 36,
        "risk_tolerance": "moderate",
        "max_drawdown_tolerance": 0.5,
        "needs_monthly_income": False,
        "liquidity_need": "low",
        "wants_trading": True,
        "experience": "advanced",
    }
    data.update(overrides)
    return InvestorProfile.model_validate(data)


def test_base_allocation_is_used_without_adjustments() -> None:
    recommendation = recommend_allocation(make_profile())

    assert recommendation.allocations_percent == BASE_ALLOCATIONS[make_profile().risk_tolerance]
    assert recommendation.experimental is True


def test_allocations_always_sum_to_one_hundred() -> None:
    recommendation = recommend_allocation(
        make_profile(
            risk_tolerance="aggressive",
            horizon_months=6,
            liquidity_need="high",
            needs_monthly_income=True,
            max_drawdown_tolerance=0.1,
            wants_trading=False,
            experience="none",
        )
    )

    assert sum(recommendation.allocations_percent.values()) == 100
    assert all(value >= 0 for value in recommendation.allocations_percent.values())


def test_high_liquidity_increases_cash() -> None:
    low = recommend_allocation(make_profile(liquidity_need="low"))
    high = recommend_allocation(make_profile(liquidity_need="high"))

    assert high.allocations_percent["cash"] > low.allocations_percent["cash"]


def test_monthly_income_increases_fixed_income() -> None:
    without_income = recommend_allocation(make_profile(needs_monthly_income=False))
    with_income = recommend_allocation(make_profile(needs_monthly_income=True))

    assert (
        with_income.allocations_percent["fixed_income"]
        > without_income.allocations_percent["fixed_income"]
    )


def test_short_horizon_reduces_equity_and_trading() -> None:
    long_horizon = recommend_allocation(make_profile(horizon_months=36))
    short_horizon = recommend_allocation(make_profile(horizon_months=6))

    long_risky = (
        long_horizon.allocations_percent["equity_fund"]
        + long_horizon.allocations_percent["high_risk_trading"]
    )
    short_risky = (
        short_horizon.allocations_percent["equity_fund"]
        + short_horizon.allocations_percent["high_risk_trading"]
    )
    assert short_risky < long_risky


def test_low_drawdown_tolerance_caps_equity_and_trading() -> None:
    recommendation = recommend_allocation(
        make_profile(risk_tolerance="aggressive", max_drawdown_tolerance=0.1)
    )

    risky = (
        recommendation.allocations_percent["equity_fund"]
        + recommendation.allocations_percent["high_risk_trading"]
    )
    assert risky <= 10


def test_disabled_trading_removes_trading_allocation() -> None:
    recommendation = recommend_allocation(make_profile(wants_trading=False))

    assert recommendation.allocations_percent["high_risk_trading"] == 0


def test_beginner_trading_is_capped() -> None:
    recommendation = recommend_allocation(
        make_profile(risk_tolerance="aggressive", experience="beginner")
    )

    assert recommendation.allocations_percent["high_risk_trading"] <= 5


def test_recommendation_contains_no_expected_return() -> None:
    recommendation = recommend_allocation(make_profile())

    assert "expected_return" not in recommendation.model_dump()
    assert "no live market data" in recommendation.disclaimer
