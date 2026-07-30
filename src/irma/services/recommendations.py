"""Recommendation persistence and orchestration."""

from decimal import Decimal

from sqlalchemy.orm import Session

from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import AllocationRecommendation, recommend_allocation
from irma.persistence.models import (
    InvestorProfileRecord,
    RecommendationAllocation,
    RecommendationRun,
)


def create_recommendation(
    profile: InvestorProfile,
    *,
    session: Session | None = None,
) -> AllocationRecommendation:
    recommendation = recommend_allocation(profile)
    if session is None:
        return recommendation
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
