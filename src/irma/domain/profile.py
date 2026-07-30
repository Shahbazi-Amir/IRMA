"""Investor profile models."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskTolerance(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class LiquidityNeed(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InvestmentExperience(StrEnum):
    NONE = "none"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TradingExperience(StrEnum):
    NONE = "none"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class InvestmentStyle(StrEnum):
    PASSIVE = "passive"
    BALANCED = "balanced"
    ACTIVE = "active"


class Horizon(StrEnum):
    DAYS = "days"
    ONE_TO_FOUR_WEEKS = "one_to_four_weeks"
    ONE_TO_THREE_MONTHS = "one_to_three_months"
    THREE_TO_SIX_MONTHS = "three_to_six_months"
    SIX_TO_TWELVE_MONTHS = "six_to_twelve_months"
    ONE_TO_THREE_YEARS = "one_to_three_years"
    THREE_TO_FIVE_YEARS = "three_to_five_years"
    OVER_FIVE_YEARS = "over_five_years"


HORIZON_MONTHS = {
    Horizon.DAYS: 1,
    Horizon.ONE_TO_FOUR_WEEKS: 1,
    Horizon.ONE_TO_THREE_MONTHS: 3,
    Horizon.THREE_TO_SIX_MONTHS: 6,
    Horizon.SIX_TO_TWELVE_MONTHS: 12,
    Horizon.ONE_TO_THREE_YEARS: 24,
    Horizon.THREE_TO_FIVE_YEARS: 48,
    Horizon.OVER_FIVE_YEARS: 72,
}


class CurrentAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    amount_toman: Decimal = Field(ge=0)


class InvestorProfile(BaseModel):
    """Validated inputs for the recommendation engine."""

    model_config = ConfigDict(extra="forbid")

    capital_toman: Decimal = Field(ge=Decimal("1000000"))
    monthly_contribution_toman: Decimal = Field(default=Decimal(0), ge=0)
    horizon: Horizon
    risk_tolerance: RiskTolerance
    max_drawdown_tolerance: float = Field(ge=0, le=1)
    needs_monthly_income: bool = False
    liquidity_need: LiquidityNeed
    experience: InvestmentExperience
    trading_experience: TradingExperience = TradingExperience.NONE
    investment_style: InvestmentStyle = InvestmentStyle.BALANCED
    wants_trading: bool = False
    max_trading_percent: int = Field(default=0, ge=0, le=20)
    has_emergency_fund: bool = False
    goal: str = Field(default="capital_growth", min_length=2, max_length=200)
    current_assets: list[CurrentAsset] = Field(default_factory=list)
