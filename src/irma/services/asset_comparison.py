"""Evidence-gated comparison of investment alternatives for beginner decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.domain.profile import Horizon, RiskTolerance
from irma.persistence.models import Fund, FundNavHistory
from irma.presentation import ASSET_LABELS, LIQUIDITY_LABELS, RISK_LABELS
from irma.services.financial_scenarios import historical_scenarios

HORIZON_DAYS = {
    Horizon.DAYS: 7,
    Horizon.ONE_TO_FOUR_WEEKS: 30,
    Horizon.ONE_TO_THREE_MONTHS: 90,
    Horizon.THREE_TO_SIX_MONTHS: 180,
    Horizon.SIX_TO_TWELVE_MONTHS: 365,
    Horizon.ONE_TO_THREE_YEARS: 1095,
    Horizon.THREE_TO_FIVE_YEARS: 1825,
    Horizon.OVER_FIVE_YEARS: 1825,
}
ASSETS = [
    ("fixed_income", "low", "high", {"fixed_income"}),
    ("gold_fund", "medium", "high", {"gold"}),
    ("equity_fund", "high", "high", {"equity", "index"}),
    ("gold", "medium", "medium", set()),
    ("fx", "medium", "medium", set()),
    ("bank_deposit", "low", "low", set()),
    ("housing", "high", "very_low", set()),
]
RISK_LEVEL = {"low": 1, "medium": 2, "high": 3}
USER_RISK = {
    RiskTolerance.CONSERVATIVE: 1,
    RiskTolerance.MODERATE: 2,
    RiskTolerance.AGGRESSIVE: 3,
}


def _fund_evidence(
    session: Session, fund_types: set[str], principal: Decimal, horizon_days: int
) -> tuple[dict[str, object] | None, list[dict[str, object]], datetime | None]:
    if not fund_types:
        return None, [], None
    funds = list(
        session.scalars(
            select(Fund).where(
                Fund.fund_type.in_(fund_types),
                Fund.is_active.is_(True),
                Fund.quality_status == "valid",
            )
        )
    )
    eligible: list[tuple[Fund, list[FundNavHistory]]] = []
    for fund in funds:
        rows = list(
            session.scalars(
                select(FundNavHistory)
                .where(FundNavHistory.fund_id == fund.id, FundNavHistory.nav.is_not(None))
                .order_by(FundNavHistory.valid_at)
            )
        )
        dated = [row for row in rows if row.valid_at is not None and row.nav is not None]
        if len(dated) < 3 or fund.last_data_at is None:
            continue
        latest = fund.last_data_at.replace(tzinfo=fund.last_data_at.tzinfo or UTC)
        if (datetime.now(UTC) - latest).days > 7:
            continue
        eligible.append((fund, dated))
    if not eligible:
        return None, [], None
    fund, rows = max(eligible, key=lambda item: len(item[1]))
    dates = [row.valid_at for row in rows if row.valid_at is not None]
    coverage_days = (dates[-1] - dates[0]).days
    if coverage_days < horizon_days * 2:
        return None, [], fund.last_data_at
    typical_step = max(1, coverage_days // (len(rows) - 1))
    horizon_periods = max(1, round(horizon_days / typical_step))
    if len(rows) <= horizon_periods:
        return None, [], fund.last_data_at
    nav_values = [float(row.nav) for row in rows if row.nav is not None]
    scenario = historical_scenarios(principal, nav_values, horizon_periods)
    candidates = [
        {"name": item[0].name_fa, "observations": len(item[1])}
        for item in sorted(eligible, key=lambda item: len(item[1]), reverse=True)[:3]
    ]
    return scenario, candidates, fund.last_data_at


def compare_assets(
    session: Session,
    principal: Decimal,
    horizon: Horizon,
    risk: RiskTolerance,
    requested_days: int | None = None,
) -> list[dict[str, Any]]:
    horizon_days = requested_days or HORIZON_DAYS[horizon]
    results: list[dict[str, Any]] = []
    for code, asset_risk, liquidity, fund_types in ASSETS:
        scenario, candidates, latest = _fund_evidence(session, fund_types, principal, horizon_days)
        risk_gap = max(0, RISK_LEVEL[asset_risk] - USER_RISK[risk])
        score = 90 - risk_gap * 30 if scenario else 0
        results.append(
            {
                "asset": code,
                "label": ASSET_LABELS[code],
                "risk": RISK_LABELS[asset_risk],
                "liquidity": LIQUIDITY_LABELS[liquidity],
                "suitability_score": max(0, min(100, score)),
                "suitability": (
                    "زیاد"
                    if score >= 75
                    else "متوسط"
                    if score >= 45
                    else "کم"
                    if scenario
                    else "قابل رتبه‌بندی نیست"
                ),
                "numeric_scenario_allowed": scenario is not None,
                "scenario": scenario,
                "latest_observation_at": latest,
                "fund_candidates": candidates,
                "data_status": "valid" if scenario else "insufficient",
                "withheld_reason": None
                if scenario
                else "داده معتبر کافی برای محاسبه این بازه موجود نیست.",
                "method": "پنجره‌های تاریخی هم‌طول بر پایه NAV معتبر"
                if scenario
                else "عدد بازده تا تکمیل داده معتبر نمایش داده نمی‌شود.",
            }
        )
    results.sort(key=lambda item: (-item["suitability_score"], item["label"]))
    for rank, item in enumerate((item for item in results if item["scenario"]), start=1):
        item["rank"] = rank
    return results
