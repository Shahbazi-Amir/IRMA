from decimal import Decimal

import pytest
from pydantic import ValidationError

from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import recommend_allocation


def profile(**overrides: object) -> InvestorProfile:
    data: dict[str, object] = {
        "capital_toman": 1_000_000,
        "monthly_contribution_toman": 100_000,
        "horizon": "one_to_three_years",
        "risk_tolerance": "moderate",
        "max_drawdown_tolerance": 0.2,
        "needs_monthly_income": False,
        "liquidity_need": "medium",
        "experience": "beginner",
        "trading_experience": "none",
        "investment_style": "balanced",
        "wants_trading": False,
        "max_trading_percent": 0,
        "has_emergency_fund": False,
        "goal": "capital growth",
        "current_assets": [],
    }
    data.update(overrides)
    return InvestorProfile.model_validate(data)


def test_minimum_capital_is_accepted() -> None:
    assert profile().capital_toman == Decimal("1000000")


def test_below_minimum_capital_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile(capital_toman=999_999)


def test_large_capital_is_supported() -> None:
    recommendation = recommend_allocation(profile(capital_toman=5_000_000_000))
    assert sum(item.amount_toman for item in recommendation.allocations) == Decimal("5000000000")


def test_allocation_sums_to_100_and_capital() -> None:
    recommendation = recommend_allocation(profile())
    assert sum(item.percent for item in recommendation.allocations) == 100
    assert sum(item.amount_toman for item in recommendation.allocations) == Decimal("1000000")


def test_beginner_without_trading_gets_zero_short_term() -> None:
    recommendation = recommend_allocation(profile())
    short_term = next(item for item in recommendation.allocations if item.category == "short_term")
    assert short_term.percent == 0


def test_aggressive_user_respects_trading_cap() -> None:
    recommendation = recommend_allocation(
        profile(
            capital_toman=100_000_000,
            risk_tolerance="aggressive",
            wants_trading=True,
            max_trading_percent=8,
            trading_experience="advanced",
            experience="advanced",
            has_emergency_fund=True,
            max_drawdown_tolerance=0.5,
        )
    )
    short_term = next(item for item in recommendation.allocations if item.category == "short_term")
    assert short_term.percent == 8


def test_small_unexecutable_allocation_is_reassigned() -> None:
    recommendation = recommend_allocation(
        profile(wants_trading=True, max_trading_percent=5, trading_experience="advanced")
    )
    short_term = next(item for item in recommendation.allocations if item.category == "short_term")
    assert short_term.percent == 0
    assert any("executable minimum" in rule for rule in recommendation.applied_rules)


def test_passive_style_removes_short_term() -> None:
    recommendation = recommend_allocation(
        profile(
            capital_toman=100_000_000,
            investment_style="passive",
            wants_trading=True,
            max_trading_percent=10,
            trading_experience="advanced",
            experience="advanced",
            max_drawdown_tolerance=0.5,
            has_emergency_fund=True,
        )
    )
    short_term = next(item for item in recommendation.allocations if item.category == "short_term")
    assert short_term.percent == 0
