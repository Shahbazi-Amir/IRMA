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


class InvestorProfile(BaseModel):
    """Validated inputs used by the initial rule engine."""

    model_config = ConfigDict(extra="forbid")

    capital_toman: Decimal = Field(ge=Decimal("1000000"))
    monthly_contribution_toman: Decimal = Field(default=Decimal(0), ge=0)
    horizon_months: int = Field(ge=1, le=1200)
    risk_tolerance: RiskTolerance
    max_drawdown_tolerance: float = Field(ge=0, le=1)
    needs_monthly_income: bool
    liquidity_need: LiquidityNeed
    wants_trading: bool
    experience: InvestmentExperience
