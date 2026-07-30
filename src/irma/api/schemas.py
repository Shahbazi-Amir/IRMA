"""API request and response schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from irma.analytics.scenarios import ScenarioAssumption, ScenarioResult


class CompoundInterestRequest(BaseModel):
    principal_toman: float = Field(ge=0)
    monthly_contribution_toman: float = Field(default=0, ge=0)
    annual_rate: float = Field(gt=-1, le=5)
    months: int = Field(ge=1, le=1200)
    compounding: Literal["monthly", "annual"] = "monthly"
    annual_inflation: float = Field(default=0, gt=-1, le=5)


class CompoundInterestResponse(BaseModel):
    assumption_notice: str
    final_nominal_toman: float
    final_real_toman: float
    total_contributions_toman: float
    nominal_profit_toman: float
    timeline: list[dict[str, float | int]]


class ScenarioRequest(BaseModel):
    principal_toman: float = Field(ge=0)
    monthly_contribution_toman: float = Field(default=0, ge=0)
    months: int = Field(ge=1, le=1200)
    assumptions: list[ScenarioAssumption]


class ScenarioResponse(BaseModel):
    assumption_notice: str
    results: list[ScenarioResult]
