"""Recommendation persistence and orchestration."""

from decimal import Decimal

from sqlalchemy.orm import Session

from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import (
    AllocationRecommendation,
    DataUse,
    FundSuggestion,
    recommend_allocation,
)
from irma.persistence.models import (
    DataSource,
    InvestorProfileRecord,
    RecommendationAllocation,
    RecommendationRun,
)
from irma.services.fund_rankings import rank_funds

CATEGORY_FUND_TYPES = {
    "fixed_income": "fixed_income",
    "gold": "gold",
    "equity_index": "index",
    "mixed_fund": "mixed",
}


def create_recommendation(
    profile: InvestorProfile,
    *,
    session: Session | None = None,
) -> AllocationRecommendation:
    recommendation = recommend_allocation(profile)
    if session is None:
        return recommendation
    sources = session.query(DataSource).filter(DataSource.status == "valid").all()
    if sources:
        recommendation.data_used = [
            DataUse(
                source=source.name,
                observed_at=source.last_valid_observation_at,
                quality=source.status,
                note=f"Sourced fund data version {source.data_version or 'unknown'}.",
            )
            for source in sources
        ]
    max_instruments = 1 if profile.capital_toman < Decimal("10000000") else 2
    for allocation in recommendation.allocations:
        fund_type = CATEGORY_FUND_TYPES.get(allocation.category)
        if fund_type is None or allocation.percent == 0:
            continue
        ranking = rank_funds(session, fund_type)
        amount = allocation.amount_toman
        if ranking["eligible_count"] == 0 or amount < Decimal("100000"):
            recommendation.warnings.append(
                f"No specific {fund_type} fund was suggested because eligible sourced data is insufficient."
            )
            continue
        allocation.instruments = [
            FundSuggestion(
                fund_id=item["fund_id"],
                name_fa=item["name_fa"],
                symbol=item["symbol"],
                score=item["score"],
                ranking_version=item["ranking_version"],
                reason=(
                    f"Rank {item['rank']} within {fund_type}; based on sourced historical "
                    "return, risk, drawdown, stability, history and data quality."
                ),
            )
            for item in ranking["items"][:max_instruments]
        ]
    profile_record = InvestorProfileRecord(profile_json=profile.model_dump(mode="json"))
    session.add(profile_record)
    session.flush()
    run = RecommendationRun(
        investor_profile_id=profile_record.id,
        ruleset_version=recommendation.ruleset_version,
        warnings_json=recommendation.warnings,
        data_snapshot_json=[item.model_dump(mode="json") for item in recommendation.data_used],
    )
    session.add(run)
    session.flush()
    for allocation in recommendation.allocations:
        session.add(
            RecommendationAllocation(
                recommendation_run_id=run.id,
                category=allocation.category,
                percent=allocation.percent,
                amount_toman=Decimal(allocation.amount_toman),
                reason=allocation.reason,
            )
        )
    session.commit()
    return recommendation
