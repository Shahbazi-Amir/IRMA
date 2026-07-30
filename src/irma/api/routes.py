"""FastAPI routes for the deployable IRMA application."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from irma import __version__
from irma.analytics.scenarios import calculate_scenarios
from irma.api.dependencies import require_admin_key
from irma.api.schemas import (
    CompoundInterestRequest,
    CompoundInterestResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from irma.config import get_settings
from irma.domain.finance import compound_with_contributions
from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import AllocationRecommendation
from irma.persistence.database import get_session
from irma.persistence.models import AssetPrice, BacktestMetric, BacktestRun
from irma.persistence.repositories import data_source_status, get_fund, list_funds
from irma.providers.placeholders import PROVIDERS
from irma.services.backtests import execute_backtest
from irma.services.data_refresh import RefreshAlreadyRunningError, refresh_from_configured_csv
from irma.services.recommendations import create_recommendation
from irma.trading_engine.backtest import BacktestRequest, BacktestResult

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "irma"}


@router.get("/v1/info", tags=["system"])
def info() -> dict[str, Any]:
    return {
        "name": "IRMA — Iranian Risk & Market Advisor",
        "name_fa": "سامانه هوشمند تحلیل بازار، ریسک و سرمایه‌گذاری ایران",
        "version": __version__,
        "stage": "deployable-v1",
        "live_market_data": False,
        "trade_execution": False,
        "price_prediction": False,
        "warnings": [
            "No profit is guaranteed.",
            "Outputs are not a substitute for licensed financial advice.",
            "Past performance does not guarantee future results.",
        ],
    }


@router.post(
    "/v1/recommendations",
    response_model=AllocationRecommendation,
    tags=["recommendations"],
)
def recommendations(profile: InvestorProfile, session: SessionDependency) -> AllocationRecommendation:
    return create_recommendation(profile, session=session)


@router.post(
    "/v1/compound-interest",
    response_model=CompoundInterestResponse,
    tags=["calculators"],
)
def compound_interest(request: CompoundInterestRequest) -> CompoundInterestResponse:
    result = compound_with_contributions(
        principal=request.principal_toman,
        monthly_contribution=request.monthly_contribution_toman,
        annual_rate=request.annual_rate,
        months=request.months,
        compounding=request.compounding,
        annual_inflation=request.annual_inflation,
    )
    return CompoundInterestResponse(
        assumption_notice="The entered rate is a calculation assumption, not a guaranteed return.",
        final_nominal_toman=result.final_nominal,
        final_real_toman=result.final_real,
        total_contributions_toman=result.total_contributions,
        nominal_profit_toman=result.nominal_profit,
        timeline=result.timeline,
    )


@router.post("/v1/scenarios", response_model=ScenarioResponse, tags=["calculators"])
def scenarios(request: ScenarioRequest) -> ScenarioResponse:
    return ScenarioResponse(
        assumption_notice="All scenario rates are user-supplied assumptions, not forecasts.",
        results=calculate_scenarios(
            principal=request.principal_toman,
            monthly_contribution=request.monthly_contribution_toman,
            months=request.months,
            assumptions=request.assumptions,
        ),
    )


@router.get("/v1/funds", tags=["funds"])
def funds(
    session: SessionDependency,
    fund_type: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    items = list_funds(session, fund_type=fund_type, query=query)
    return {
        "items": items,
        "count": len(items),
        "data_notice": "No synthetic fund record is returned; an empty list means data is unavailable.",
    }


@router.get("/v1/funds/rankings", tags=["funds"])
def fund_rankings(session: SessionDependency, fund_type: str) -> dict[str, Any]:
    items = list_funds(session, fund_type=fund_type)
    return {
        "fund_type": fund_type,
        "items": [],
        "eligible_count": 0,
        "data_notice": (
            "Ranking is withheld until enough sourced history, liquidity and quality metrics exist. "
            f"{len(items)} fund records are currently known."
        ),
    }


@router.get("/v1/funds/{fund_id}", tags=["funds"])
def fund_detail(fund_id: int, session: SessionDependency) -> dict[str, Any]:
    item = get_fund(session, fund_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fund not found")
    return item


@router.get("/v1/market/summary", tags=["market"])
def market_summary(session: SessionDependency) -> dict[str, Any]:
    latest = session.scalars(select(AssetPrice).order_by(AssetPrice.observed_at.desc()).limit(20)).all()
    return {
        "data_available": bool(latest),
        "observed_at": max((item.observed_at for item in latest), default=None),
        "items": [
            {
                "asset_id": item.asset_id,
                "close_price": float(item.close_price) if item.close_price is not None else None,
                "volume": float(item.volume) if item.volume is not None else None,
                "quality_status": item.quality_status,
                "source_id": item.source_id,
            }
            for item in latest
        ],
        "notice": "Missing values are not converted to zero.",
    }


@router.get("/v1/data-sources/status", tags=["data"])
def source_status(session: SessionDependency) -> dict[str, Any]:
    return {
        "database_sources": data_source_status(session),
        "unavailable_adapters": [provider.status() for provider in PROVIDERS],
        "checked_at": datetime.now(UTC),
    }


@router.post("/v1/backtests", tags=["backtesting"])
def backtests(request: BacktestRequest, session: SessionDependency) -> dict[str, Any]:
    run_id, result = execute_backtest(request, session=session)
    return {"backtest_id": run_id, "result": result}


@router.get("/v1/backtests/{backtest_id}", tags=["backtesting"])
def backtest_detail(backtest_id: int, session: SessionDependency) -> dict[str, Any]:
    run = session.get(BacktestRun, backtest_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="backtest not found")
    metrics = session.scalars(
        select(BacktestMetric).where(BacktestMetric.backtest_run_id == backtest_id)
    ).all()
    return {
        "id": run.id,
        "strategy": run.strategy_name,
        "strategy_version": run.strategy_version,
        "status": run.status,
        "input_hash": run.input_hash,
        "warnings": run.warnings_json,
        "metrics": {
            item.metric_name: float(item.value) if item.value is not None else None for item in metrics
        },
    }


@router.post(
    "/v1/admin/data-refresh",
    dependencies=[Depends(require_admin_key)],
    tags=["admin"],
)
def admin_refresh(session: SessionDependency) -> dict[str, int | str]:
    settings = get_settings()
    try:
        return refresh_from_configured_csv(
            session,
            csv_path=settings.fund_csv_path,
            max_retries=settings.provider_max_retries,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(exc)) from exc
    except RefreshAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
