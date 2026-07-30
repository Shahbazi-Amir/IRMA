"""User-supplied scenario calculations; assumptions are never presented as forecasts."""

from pydantic import BaseModel, Field

from irma.domain.finance import compound_with_contributions


class ScenarioAssumption(BaseModel):
    name: str
    annual_return: float = Field(gt=-1, le=5)
    annual_inflation: float = Field(gt=-1, le=5)
    possible_drawdown: float = Field(ge=0, le=1)
    uncertainty: str


class ScenarioResult(BaseModel):
    name: str
    nominal_value: float
    real_value: float
    possible_drawdown: float
    uncertainty: str


def calculate_scenarios(
    *,
    principal: float,
    monthly_contribution: float,
    months: int,
    assumptions: list[ScenarioAssumption],
) -> list[ScenarioResult]:
    if {item.name for item in assumptions} != {"pessimistic", "base", "optimistic"}:
        raise ValueError("pessimistic, base and optimistic assumptions are required")
    results = []
    for assumption in assumptions:
        outcome = compound_with_contributions(
            principal=principal,
            monthly_contribution=monthly_contribution,
            annual_rate=assumption.annual_return,
            months=months,
            annual_inflation=assumption.annual_inflation,
        )
        results.append(
            ScenarioResult(
                name=assumption.name,
                nominal_value=outcome.final_nominal,
                real_value=outcome.final_real,
                possible_drawdown=assumption.possible_drawdown,
                uncertainty=assumption.uncertainty,
            )
        )
    return results
