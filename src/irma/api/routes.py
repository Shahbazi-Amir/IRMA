"""HTTP routes for the IRMA MVP."""

from typing import Any

from fastapi import APIRouter

from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import AllocationRecommendation, recommend_allocation

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a minimal liveness response."""

    return {"status": "ok", "service": "irma"}


@router.get("/v1/info", tags=["system"])
def info() -> dict[str, Any]:
    """Describe the current product boundary."""

    return {
        "version": "0.1.0",
        "stage": "experimental-mvp",
        "live_market_data": False,
        "trade_execution": False,
        "price_prediction": False,
    }


@router.post(
    "/v1/recommendations",
    response_model=AllocationRecommendation,
    tags=["recommendations"],
)
def create_recommendation(profile: InvestorProfile) -> AllocationRecommendation:
    """Create a deterministic experimental allocation from validated inputs."""

    return recommend_allocation(profile)
