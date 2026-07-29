from decimal import Decimal

import pytest
from pydantic import ValidationError

from irma.domain.profile import InvestorProfile


def valid_profile_data() -> dict[str, object]:
    return {
        "capital_toman": 1_000_000,
        "monthly_contribution_toman": 100_000,
        "horizon_months": 24,
        "risk_tolerance": "moderate",
        "max_drawdown_tolerance": 0.2,
        "needs_monthly_income": False,
        "liquidity_need": "medium",
        "wants_trading": True,
        "experience": "intermediate",
    }


def test_profile_accepts_minimum_capital() -> None:
    profile = InvestorProfile.model_validate(valid_profile_data())

    assert profile.capital_toman == Decimal("1000000")


def test_profile_rejects_capital_below_one_million_toman() -> None:
    data = valid_profile_data()
    data["capital_toman"] = 999_999

    with pytest.raises(ValidationError):
        InvestorProfile.model_validate(data)


def test_profile_rejects_unknown_fields() -> None:
    data = valid_profile_data()
    data["private_note"] = "must not be persisted"

    with pytest.raises(ValidationError):
        InvestorProfile.model_validate(data)
