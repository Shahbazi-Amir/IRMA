"""Versioned and explainable rule-based portfolio allocation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict, Field, model_validator

from irma.domain.profile import (
    HORIZON_MONTHS,
    InvestmentExperience,
    InvestorProfile,
    InvestmentStyle,
    LiquidityNeed,
    RiskTolerance,
    TradingExperience,
)

RULESET_VERSION = "2026.07.1"
DISCLAIMER_FA = (
    "این پیشنهاد آزمایشی و مبتنی بر قواعد است؛ تضمین سود یا جایگزین مشاوره مالی دارای مجوز نیست. "
    "عملکرد گذشته تضمین آینده نیست و داده‌های بازار ممکن است ناقص یا با تأخیر باشند."
)
CATEGORIES = (
    "cash",
    "fixed_income",
    "gold",
    "equity_index",
    "mixed_fund",
    "short_term",
)
MINIMUM_EXECUTABLE_TOMAN = {
    "cash": Decimal("1"),
    "fixed_income": Decimal("100000"),
    "gold": Decimal("100000"),
    "equity_index": Decimal("100000"),
    "mixed_fund": Decimal("100000"),
    "short_term": Decimal("500000"),
}
BASE_ALLOCATIONS: dict[RiskTolerance, dict[str, int]] = {
    RiskTolerance.CONSERVATIVE: {
        "cash": 15,
        "fixed_income": 60,
        "gold": 15,
        "equity_index": 5,
        "mixed_fund": 5,
        "short_term": 0,
    },
    RiskTolerance.MODERATE: {
        "cash": 10,
        "fixed_income": 40,
        "gold": 20,
        "equity_index": 20,
        "mixed_fund": 5,
        "short_term": 5,
    },
    RiskTolerance.AGGRESSIVE: {
        "cash": 5,
        "fixed_income": 20,
        "gold": 15,
        "equity_index": 40,
        "mixed_fund": 5,
        "short_term": 15,
    },
}


class DataUse(BaseModel):
    source: str
    observed_at: datetime | None = None
    quality: str = "missing"
    note: str


class AllocationItem(BaseModel):
    category: str
    percent: int = Field(ge=0, le=100)
    amount_toman: Decimal = Field(ge=0)
    reason: str
    risk: str
    liquidity: str
    suggested_holding: str
    entry_method: str


class AllocationRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experimental: bool = True
    ruleset_version: str = RULESET_VERSION
    allocations: list[AllocationItem]
    applied_rules: list[str]
    warnings: list[str]
    review_at: datetime
    data_used: list[DataUse]
    disclaimer: str = DISCLAIMER_FA

    @model_validator(mode="after")
    def validate_total(self) -> "AllocationRecommendation":
        if sum(item.percent for item in self.allocations) != 100:
            raise ValueError("allocations must sum to 100")
        if any(item.percent < 0 for item in self.allocations):
            raise ValueError("allocations cannot be negative")
        return self


DETAILS = {
    "cash": ("very_low", "very_high", "immediate", "lump_sum"),
    "fixed_income": ("low", "high", "3-12 months", "lump_sum"),
    "gold": ("medium", "high", "6-24 months", "staged"),
    "equity_index": ("high", "high", "12+ months", "staged"),
    "mixed_fund": ("medium", "medium", "12+ months", "staged"),
    "short_term": ("very_high", "high", "days-weeks", "paper-test-first"),
}


def _transfer(allocations: dict[str, int], amount: int, sources: tuple[str, ...], target: str) -> int:
    remaining = amount
    for source in sources:
        moved = min(allocations[source], remaining)
        allocations[source] -= moved
        allocations[target] += moved
        remaining -= moved
        if remaining == 0:
            break
    return amount - remaining


def _enforce_minimums(allocations: dict[str, int], capital: Decimal, rules: list[str]) -> None:
    removed = 0
    for category in CATEGORIES:
        if category in {"cash", "fixed_income"}:
            continue
        amount = capital * Decimal(allocations[category]) / Decimal(100)
        if allocations[category] and amount < MINIMUM_EXECUTABLE_TOMAN[category]:
            removed += allocations[category]
            rules.append(
                f"Removed {category} because its amount was below the executable minimum."
            )
            allocations[category] = 0
    allocations["fixed_income"] += removed


def recommend_allocation(
    profile: InvestorProfile,
    *,
    data_used: list[DataUse] | None = None,
) -> AllocationRecommendation:
    allocations = BASE_ALLOCATIONS[profile.risk_tolerance].copy()
    rules = [f"Started from {profile.risk_tolerance.value} ruleset {RULESET_VERSION}."]
    warnings = ["No live market return is assumed in this allocation."]
    horizon_months = HORIZON_MONTHS[profile.horizon]

    if profile.liquidity_need is LiquidityNeed.HIGH:
        moved = _transfer(allocations, 10, ("short_term", "equity_index", "gold"), "cash")
        rules.append(f"Moved {moved}% to cash for high liquidity need.")
    elif profile.liquidity_need is LiquidityNeed.MEDIUM:
        moved = _transfer(allocations, 5, ("short_term", "equity_index"), "cash")
        rules.append(f"Moved {moved}% to cash for medium liquidity need.")

    if not profile.has_emergency_fund:
        moved = _transfer(allocations, 5, ("short_term", "equity_index", "gold"), "cash")
        rules.append(f"Moved {moved}% to cash because no emergency fund was reported.")

    if profile.needs_monthly_income:
        moved = _transfer(
            allocations,
            10,
            ("short_term", "equity_index", "mixed_fund", "gold"),
            "fixed_income",
        )
        rules.append(f"Moved {moved}% to fixed income for monthly income preference.")

    if horizon_months <= 6:
        moved = _transfer(
            allocations,
            25,
            ("short_term", "equity_index", "mixed_fund", "gold"),
            "fixed_income",
        )
        rules.append(f"Moved {moved}% away from volatile assets for a short horizon.")
    elif horizon_months <= 12:
        moved = _transfer(allocations, 10, ("short_term", "equity_index"), "fixed_income")
        rules.append(f"Moved {moved}% to fixed income for a sub-one-year horizon.")

    if profile.max_drawdown_tolerance <= 0.10:
        risky = allocations["equity_index"] + allocations["mixed_fund"] + allocations["short_term"]
        moved = _transfer(
            allocations,
            max(0, risky - 10),
            ("short_term", "equity_index", "mixed_fund"),
            "fixed_income",
        )
        rules.append(f"Capped growth and trading exposure near 10%; moved {moved}%.")
    elif profile.max_drawdown_tolerance <= 0.20:
        risky = allocations["equity_index"] + allocations["mixed_fund"] + allocations["short_term"]
        moved = _transfer(
            allocations,
            max(0, risky - 30),
            ("short_term", "equity_index", "mixed_fund"),
            "fixed_income",
        )
        if moved:
            rules.append(f"Capped growth and trading exposure near 30%; moved {moved}%.")

    trading_cap = min(profile.max_trading_percent, 20)
    if not profile.wants_trading:
        trading_cap = 0
    if profile.trading_experience in {TradingExperience.NONE, TradingExperience.BEGINNER}:
        trading_cap = min(trading_cap, 3)
    if profile.experience in {InvestmentExperience.NONE, InvestmentExperience.BEGINNER}:
        trading_cap = min(trading_cap, 5)
    excess = max(0, allocations["short_term"] - trading_cap)
    if excess:
        allocations["short_term"] -= excess
        allocations["fixed_income"] += excess
        rules.append(f"Limited research trading allocation to {trading_cap}%.")

    if profile.investment_style is InvestmentStyle.PASSIVE and allocations["short_term"]:
        moved = allocations["short_term"]
        allocations["short_term"] = 0
        allocations["equity_index"] += moved
        rules.append("Moved short-term allocation to passive equity/index exposure.")

    _enforce_minimums(allocations, profile.capital_toman, rules)

    reasons = {
        "cash": "Liquidity buffer and uncertainty management.",
        "fixed_income": "Capital stability, income preference and short-horizon support.",
        "gold": "Diversification and inflation-sensitive exposure without a return promise.",
        "equity_index": "Longer-horizon growth exposure with high drawdown risk.",
        "mixed_fund": "Balanced exposure when data and executable products are available.",
        "short_term": "Research-only allocation; requires liquid data and a tested strategy.",
    }
    items: list[AllocationItem] = []
    assigned = Decimal(0)
    for index, category in enumerate(CATEGORIES):
        percent = allocations[category]
        if index == len(CATEGORIES) - 1:
            amount = profile.capital_toman - assigned
        else:
            amount = (profile.capital_toman * Decimal(percent) / Decimal(100)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            assigned += amount
        risk, liquidity, holding, entry = DETAILS[category]
        items.append(
            AllocationItem(
                category=category,
                percent=percent,
                amount_toman=amount,
                reason=reasons[category],
                risk=risk,
                liquidity=liquidity,
                suggested_holding=holding,
                entry_method=entry,
            )
        )
    if not data_used:
        data_used = [
            DataUse(
                source="rule-engine",
                quality="missing",
                note="Allocation used profile rules only; no live market dataset was available.",
            )
        ]
    review_days = 30 if horizon_months <= 12 else 90
    return AllocationRecommendation(
        allocations=items,
        applied_rules=rules,
        warnings=warnings,
        review_at=datetime.now(UTC) + timedelta(days=review_days),
        data_used=data_used,
    )
