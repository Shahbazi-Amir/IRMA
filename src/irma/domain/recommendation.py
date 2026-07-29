"""Transparent rule-based allocation for the IRMA MVP."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from irma.domain.profile import (
    InvestmentExperience,
    InvestorProfile,
    LiquidityNeed,
    RiskTolerance,
)

AllocationMap = dict[str, int]

BASE_ALLOCATIONS: dict[RiskTolerance, AllocationMap] = {
    RiskTolerance.CONSERVATIVE: {
        "cash": 15,
        "fixed_income": 60,
        "gold": 20,
        "equity_fund": 5,
        "high_risk_trading": 0,
    },
    RiskTolerance.MODERATE: {
        "cash": 10,
        "fixed_income": 40,
        "gold": 20,
        "equity_fund": 25,
        "high_risk_trading": 5,
    },
    RiskTolerance.AGGRESSIVE: {
        "cash": 5,
        "fixed_income": 20,
        "gold": 15,
        "equity_fund": 45,
        "high_risk_trading": 15,
    },
}

RISKY_CATEGORIES = ("high_risk_trading", "equity_fund", "gold")
DISCLAIMER = (
    "Experimental rule-based suggestion only; it uses no live market data, forecast, "
    "or guaranteed return and is not personalized financial advice."
)


class AllocationRecommendation(BaseModel):
    """Explainable allocation response."""

    model_config = ConfigDict(extra="forbid")

    experimental: bool = True
    allocations_percent: AllocationMap
    applied_rules: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER

    @model_validator(mode="after")
    def validate_allocations(self) -> AllocationRecommendation:
        if set(self.allocations_percent) != set(next(iter(BASE_ALLOCATIONS.values()))):
            raise ValueError("allocation categories are incomplete")
        if any(value < 0 for value in self.allocations_percent.values()):
            raise ValueError("allocations cannot be negative")
        if sum(self.allocations_percent.values()) != 100:
            raise ValueError("allocations must sum to 100")
        return self


def _transfer(
    allocations: AllocationMap,
    amount: int,
    *,
    sources: tuple[str, ...],
    destination: str,
) -> int:
    """Transfer up to amount points from sources to a destination."""

    remaining = amount
    for source in sources:
        moved = min(allocations[source], remaining)
        allocations[source] -= moved
        allocations[destination] += moved
        remaining -= moved
        if remaining == 0:
            break
    return amount - remaining


def _cap_risky_allocation(
    allocations: AllocationMap,
    maximum: int,
    destination: str,
) -> int:
    risky_total = allocations["equity_fund"] + allocations["high_risk_trading"]
    excess = max(0, risky_total - maximum)
    return _transfer(
        allocations,
        excess,
        sources=("high_risk_trading", "equity_fund"),
        destination=destination,
    )


def recommend_allocation(profile: InvestorProfile) -> AllocationRecommendation:
    """Return a deterministic allocation and the rules that changed it."""

    allocations = BASE_ALLOCATIONS[profile.risk_tolerance].copy()
    rules = [f"Started from the {profile.risk_tolerance.value} risk allocation."]

    liquidity_shift = {
        LiquidityNeed.LOW: 0,
        LiquidityNeed.MEDIUM: 5,
        LiquidityNeed.HIGH: 10,
    }[profile.liquidity_need]
    if liquidity_shift:
        moved = _transfer(
            allocations,
            liquidity_shift,
            sources=RISKY_CATEGORIES,
            destination="cash",
        )
        rules.append(f"Moved {moved}% to cash for {profile.liquidity_need.value} liquidity need.")

    if profile.needs_monthly_income:
        moved = _transfer(
            allocations,
            10,
            sources=("high_risk_trading", "equity_fund", "gold", "cash"),
            destination="fixed_income",
        )
        rules.append(f"Moved {moved}% to fixed income for monthly-income preference.")

    if profile.horizon_months < 12:
        moved_to_cash = _transfer(
            allocations,
            10,
            sources=("high_risk_trading", "equity_fund"),
            destination="cash",
        )
        moved_to_fixed = _transfer(
            allocations,
            5,
            sources=("high_risk_trading", "equity_fund", "gold"),
            destination="fixed_income",
        )
        moved_total = moved_to_cash + moved_to_fixed
        rules.append(
            f"Moved {moved_total}% from risk assets for a horizon under 12 months."
        )

    if profile.max_drawdown_tolerance <= 0.10:
        moved = _cap_risky_allocation(allocations, maximum=10, destination="fixed_income")
        rules.append(f"Capped equity and trading exposure at 10%; moved {moved}% to fixed income.")
    elif profile.max_drawdown_tolerance <= 0.20:
        moved = _cap_risky_allocation(allocations, maximum=30, destination="fixed_income")
        if moved:
            rules.append(
                f"Capped equity and trading exposure at 30%; moved {moved}% to fixed income."
            )

    if not profile.wants_trading and allocations["high_risk_trading"]:
        destination = (
            "equity_fund"
            if profile.risk_tolerance is RiskTolerance.AGGRESSIVE
            else "fixed_income"
        )
        moved = _transfer(
            allocations,
            allocations["high_risk_trading"],
            sources=("high_risk_trading",),
            destination=destination,
        )
        rules.append(f"Moved {moved}% out of trading because trading preference is disabled.")

    if profile.experience in {InvestmentExperience.NONE, InvestmentExperience.BEGINNER}:
        excess = max(0, allocations["high_risk_trading"] - 5)
        if excess:
            moved = _transfer(
                allocations,
                excess,
                sources=("high_risk_trading",),
                destination="fixed_income",
            )
            rules.append(f"Limited trading to 5% for limited experience; moved {moved}%.")

    return AllocationRecommendation(allocations_percent=allocations, applied_rules=rules)
