"""FastAPI routes for the deployable IRMA application."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from httpx import HTTPError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma import __version__
from irma.analytics.scenarios import calculate_scenarios
from irma.api.dependencies import require_admin_key
from irma.api.schemas import (
    CompoundInterestRequest,
    CompoundInterestResponse,
    RebalanceRequest,
    ScenarioRequest,
    ScenarioResponse,
)
from irma.config import get_settings
from irma.domain.finance import compound_with_contributions
from irma.domain.profile import InvestorProfile
from irma.domain.recommendation import AllocationRecommendation
from irma.persistence.database import get_session
from irma.persistence.models import (
    AssetPrice,
    BackfillRun,
    BacktestMetric,
    BacktestRun,
    BankProduct,
    BankProductVersion,
    DataIngestionRun,
    DataQualityEvent,
    DataSource,
    Fund,
    FundDataConflict,
    FundFieldProvenance,
    FundInstrumentMapping,
    FundMarketHistory,
    FundNavHistory,
    InflationObservation,
    InflationSeries,
    InstrumentMarketHistory,
    MarketIndex,
    MarketIndexHistory,
    MarketInstrument,
    ProviderHealthEvent,
    RecommendationRun,
)
from irma.persistence.repositories import data_source_status, get_fund, list_funds
from irma.providers.fipiran import FipiranFundProvider
from irma.providers.placeholders import PROVIDERS
from irma.services.backtests import execute_backtest
from irma.services.data_refresh import (
    RefreshAlreadyRunningError,
    refresh_from_configured_csv,
    refresh_from_fipiran,
)
from irma.services.fund_backfill import backfill_fund_history
from irma.services.fund_rankings import rank_funds
from irma.services.multi_asset_refresh import (
    refresh_bank_products,
    refresh_inflation,
    refresh_market_indices,
    refresh_market_instruments,
)
from irma.services.portfolio_plans import rebalance_plan
from irma.services.recommendations import create_recommendation
from irma.trading_engine.backtest import BacktestRequest

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "irma"}


@router.get("/ready", tags=["system"])
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(select(1))
    return {"status": "ready", "database": "ok"}


@router.get("/metrics", tags=["system"])
def metrics(session: SessionDependency) -> dict[str, int]:
    """Low-cardinality operational metrics without exposing user data."""
    successful = session.scalar(
        select(func.count(DataIngestionRun.id)).where(DataIngestionRun.status == "success")
    )
    failed = session.scalar(
        select(func.count(DataIngestionRun.id)).where(DataIngestionRun.status == "error")
    )
    stale = session.scalar(
        select(func.count(DataQualityEvent.id)).where(DataQualityEvent.rule_code == "stale")
    )
    recommendations_count = session.scalar(select(func.count(RecommendationRun.id)))
    withheld = session.scalar(
        select(func.count(RecommendationRun.id)).where(RecommendationRun.warnings_json.is_not(None))
    )
    rejected = session.scalar(
        select(func.count(DataQualityEvent.id)).where(
            DataQualityEvent.severity.in_(("error", "critical"))
        )
    )
    return {
        "ingestion_success_total": successful or 0,
        "ingestion_failure_total": failed or 0,
        "stale_records_total": stale or 0,
        "recommendations_total": recommendations_count or 0,
        "recommendations_with_warnings_total": withheld or 0,
        "records_rejected_total": rejected or 0,
    }


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
def recommendations(
    profile: InvestorProfile, session: SessionDependency
) -> AllocationRecommendation:
    return create_recommendation(profile, session=session)


@router.post("/v1/recommendations/rebalance", tags=["recommendations"])
def recommendations_rebalance(request: RebalanceRequest) -> dict[str, object]:
    return rebalance_plan(
        target_weights=request.target_weights,
        current_weights=request.current_weights,
        monthly_contribution_toman=request.monthly_contribution_toman,
        threshold_points=request.threshold_points,
    )


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
    return rank_funds(session, fund_type)


@router.get("/v1/providers/funds/status", tags=["funds"])
def fund_provider_status(session: SessionDependency) -> dict[str, Any]:
    settings = get_settings()
    source = session.scalar(select(DataSource).where(DataSource.name == "fipiran"))
    latest = session.scalar(
        select(ProviderHealthEvent)
        .where(ProviderHealthEvent.provider == "fipiran")
        .order_by(ProviderHealthEvent.observed_at.desc())
        .limit(1)
    )
    return {
        "configured_provider": settings.fund_provider,
        "contract": settings.fipiran_contract,
        "fallback_file_configured": settings.official_fund_file_path,
        "status": source.status if source else "unavailable",
        "last_success_at": source.last_valid_observation_at if source else None,
        "last_failure_at": latest.observed_at if latest else None,
        "last_failure_reason": latest.event_type if latest else None,
    }


@router.get("/v1/providers/funds/diagnostics", tags=["funds"])
def fund_provider_diagnostics(session: SessionDependency) -> dict[str, Any]:
    events = session.scalars(
        select(ProviderHealthEvent).order_by(ProviderHealthEvent.observed_at.desc()).limit(50)
    ).all()
    return {
        "items": [
            {
                "provider": event.provider,
                "event_type": event.event_type,
                "severity": event.severity,
                "status_code": event.status_code,
                "response_hash": event.response_hash,
                "sample": event.sanitized_sample,
                "observed_at": event.observed_at,
            }
            for event in events
        ],
        "notice": "Cookies, authorization headers, tokens and raw payloads are not stored.",
    }


@router.get("/v1/funds/{fund_id}/eligibility", tags=["funds"])
def fund_eligibility(fund_id: int, session: SessionDependency) -> dict[str, Any]:
    fund = session.get(Fund, fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="fund not found")
    ranking = rank_funds(session, fund.fund_type)
    item = next((row for row in ranking["items"] if row["fund_id"] == fund_id), None)
    reason = None
    if item is None:
        for key, count in ranking["exclusions"].items():
            if count:
                reason = key
                break
    return {
        "fund_id": fund_id,
        "eligible": item is not None,
        "reason": "eligible" if item is not None else reason or "not_eligible",
        "ruleset_version": ranking["ranking_version"],
        "minimum_observations": 90,
        "maximum_staleness_days": 7,
        "ranking": item,
    }


@router.get("/v1/funds/{fund_id}/provenance", tags=["funds"])
def fund_provenance(fund_id: int, session: SessionDependency) -> dict[str, Any]:
    fund = session.get(Fund, fund_id)
    if fund is None:
        raise HTTPException(status_code=404, detail="fund not found")
    fields = session.scalars(
        select(FundFieldProvenance).where(FundFieldProvenance.fund_id == fund_id)
    ).all()
    conflicts = session.scalars(
        select(FundDataConflict).where(FundDataConflict.fund_id == fund_id)
    ).all()
    return {
        "fund_id": fund_id,
        "source_id": fund.source_id,
        "last_data_at": fund.last_data_at,
        "fields": [
            {
                "field": item.field_name,
                "source_id": item.source_id,
                "value_hash": item.value_hash,
                "observed_at": item.observed_at,
            }
            for item in fields
        ],
        "conflicts": [
            {
                "field": item.field_name,
                "difference_percent": float(item.difference_percent)
                if item.difference_percent is not None
                else None,
                "severity": item.severity,
                "observed_at": item.observed_at,
            }
            for item in conflicts
        ],
    }


@router.get("/v1/funds/{fund_id}", tags=["funds"])
def fund_detail(fund_id: int, session: SessionDependency) -> dict[str, Any]:
    item = get_fund(session, fund_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fund not found")
    return item


@router.get("/v1/market/summary", tags=["market"])
def market_summary(session: SessionDependency) -> dict[str, Any]:
    latest = session.scalars(
        select(AssetPrice).order_by(AssetPrice.observed_at.desc()).limit(20)
    ).all()
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


@router.get("/v1/market/indices", tags=["market"])
def market_indices(
    session: SessionDependency,
    index_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    quality: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    statement = (
        select(MarketIndexHistory, MarketIndex, DataSource)
        .join(MarketIndex, MarketIndex.id == MarketIndexHistory.market_index_id)
        .outerjoin(DataSource, DataSource.id == MarketIndexHistory.source_id)
        .order_by(MarketIndexHistory.valid_at.desc())
    )
    if index_code:
        statement = statement.where(MarketIndex.index_code == index_code)
    if date_from:
        statement = statement.where(MarketIndexHistory.valid_at >= date_from)
    if date_to:
        statement = statement.where(MarketIndexHistory.valid_at <= date_to)
    if quality:
        statement = statement.where(MarketIndexHistory.quality_status == quality)
    rows = session.execute(statement.offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "index_code": index.index_code,
                "name_fa": index.name_fa,
                "name_en": index.name_en,
                "observation_date": history.valid_at,
                "open": history.open_value,
                "high": history.high_value,
                "low": history.low_value,
                "close": history.close_value,
                "change": history.change_value,
                "change_percent": history.change_percent,
                "quality_status": history.quality_status,
                "source_name": source.name if source else None,
                "observed_at": history.observed_at,
            }
            for history, index, source in rows
        ],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/v1/market/indices/{index_code}", tags=["market"])
def market_index_detail(index_code: str, session: SessionDependency) -> dict[str, Any]:
    payload = market_indices(
        session,
        index_code=index_code,
        date_from=None,
        date_to=None,
        quality=None,
        offset=0,
        limit=500,
    )
    if not payload["items"]:
        raise HTTPException(status_code=404, detail="market index not found")
    return payload


@router.get("/v1/market/instruments", tags=["market"])
def market_instruments(
    session: SessionDependency,
    instrument_type: str | None = None,
    symbol: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    statement = (
        select(InstrumentMarketHistory, MarketInstrument, DataSource)
        .join(MarketInstrument, MarketInstrument.id == InstrumentMarketHistory.instrument_id)
        .outerjoin(DataSource, DataSource.id == InstrumentMarketHistory.source_id)
        .order_by(InstrumentMarketHistory.valid_at.desc())
    )
    if instrument_type:
        statement = statement.where(MarketInstrument.instrument_type == instrument_type)
    if symbol:
        statement = statement.where(MarketInstrument.symbol == symbol)
    rows = session.execute(statement.offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "instrument_id": instrument.id,
                "stable_id": instrument.stable_id,
                "symbol": instrument.symbol,
                "name_fa": instrument.name_fa,
                "instrument_type": instrument.instrument_type,
                "date": history.valid_at,
                "close": history.close_price,
                "last": history.last_price,
                "volume": history.volume,
                "trade_value": history.trade_value,
                "market_status": history.market_status,
                "quality_status": history.quality_status,
                "source_name": source.name if source else None,
            }
            for history, instrument, source in rows
        ],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/v1/market/instruments/{instrument_id}", tags=["market"])
def market_instrument_detail(instrument_id: int, session: SessionDependency) -> dict[str, Any]:
    instrument = session.get(MarketInstrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail="market instrument not found")
    latest = session.scalar(
        select(InstrumentMarketHistory)
        .where(InstrumentMarketHistory.instrument_id == instrument_id)
        .order_by(InstrumentMarketHistory.valid_at.desc())
    )
    return {
        "id": instrument.id,
        "stable_id": instrument.stable_id,
        "symbol": instrument.symbol,
        "name_fa": instrument.name_fa,
        "instrument_type": instrument.instrument_type,
        "latest": {
            "date": latest.valid_at,
            "open": latest.open_price,
            "high": latest.high_price,
            "low": latest.low_price,
            "close": latest.close_price,
            "last": latest.last_price,
            "volume": latest.volume,
            "trade_value": latest.trade_value,
            "market_status": latest.market_status,
            "quality_status": latest.quality_status,
        }
        if latest
        else None,
    }


@router.get("/v1/market/gold-funds", tags=["market"])
def gold_funds(session: SessionDependency) -> dict[str, Any]:
    funds = session.scalars(select(Fund).where(Fund.fund_type == "gold")).all()
    items: list[dict[str, Any]] = []
    for fund in funds:
        nav = session.scalar(
            select(FundNavHistory)
            .where(FundNavHistory.fund_id == fund.id)
            .order_by(FundNavHistory.valid_at.desc())
        )
        market = session.scalar(
            select(FundMarketHistory)
            .where(FundMarketHistory.fund_id == fund.id)
            .order_by(FundMarketHistory.valid_at.desc())
        )
        mapping = session.scalar(
            select(FundInstrumentMapping).where(FundInstrumentMapping.fund_id == fund.id)
        )
        premium = None
        if nav and market and nav.nav and market.market_price:
            premium = float(market.market_price / nav.nav - 1)
        items.append(
            {
                "fund_id": fund.id,
                "name_fa": fund.name_fa,
                "symbol": fund.symbol,
                "nav": nav.nav if nav else None,
                "market_price": market.market_price if market else None,
                "premium_discount": premium,
                "volume": market.volume if market else None,
                "trade_value": market.trade_value if market else None,
                "quality_status": fund.quality_status,
                "last_data_at": fund.last_data_at,
                "mapping_status": mapping.match_status if mapping else "unmatched",
            }
        )
    return {"items": items, "count": len(items)}


@router.get("/v1/economy/inflation", tags=["economy"])
def inflation(
    session: SessionDependency,
    indicator_code: str | None = None,
    limit: int = Query(default=120, ge=1, le=500),
) -> dict[str, Any]:
    statement = (
        select(InflationObservation, InflationSeries, DataSource)
        .join(InflationSeries, InflationSeries.id == InflationObservation.series_id)
        .outerjoin(DataSource, DataSource.id == InflationObservation.source_id)
        .order_by(InflationObservation.publication_date.desc())
    )
    if indicator_code:
        statement = statement.where(InflationSeries.indicator_code == indicator_code)
    rows = session.execute(statement.limit(limit)).all()
    return {
        "items": [
            {
                "indicator_code": series.indicator_code,
                "indicator_name": series.indicator_name,
                "base_year": series.base_year,
                "period": observation.period,
                "period_type": observation.period_type,
                "monthly_inflation": observation.monthly_inflation,
                "point_to_point_inflation": observation.point_to_point_inflation,
                "annual_inflation": observation.annual_inflation,
                "consumer_price_index": observation.consumer_price_index,
                "publication_date": observation.publication_date,
                "quality_status": observation.quality_status,
                "source_name": source.name if source else None,
            }
            for observation, series, source in rows
        ],
        "count": len(rows),
    }


@router.get("/v1/bank-products", tags=["banking"])
def bank_products(
    session: SessionDependency,
    include_unverified: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    statement = (
        select(BankProductVersion, BankProduct, DataSource)
        .join(BankProduct, BankProduct.id == BankProductVersion.bank_product_id)
        .outerjoin(DataSource, DataSource.id == BankProductVersion.source_id)
        .order_by(BankProductVersion.valid_from.desc())
    )
    if not include_unverified:
        statement = statement.where(
            BankProductVersion.verification_status.in_(("official_verified", "manual_verified")),
            (BankProductVersion.valid_until.is_(None))
            | (BankProductVersion.valid_until >= date.today()),
        )
    rows = session.execute(statement.limit(limit)).all()
    return {
        "items": [
            {
                "bank_name": product.bank_name,
                "product_name": product.product_name,
                "product_type": version.product_type,
                "nominal_rate": version.nominal_rate,
                "effective_rate": version.effective_rate,
                "minimum_deposit_toman": version.minimum_deposit_toman,
                "term_months": version.term_months,
                "valid_from": version.valid_from,
                "valid_until": version.valid_until,
                "verification_status": version.verification_status,
                "source_url": version.source_url,
                "source_name": source.name if source else None,
            }
            for version, product, source in rows
        ],
        "count": len(rows),
        "notice": "Only currently verified terms are returned by default; rates are not forecasts.",
    }


@router.get("/v1/asset-classes/comparison", tags=["analytics"])
def asset_class_comparison(session: SessionDependency) -> dict[str, Any]:
    sources = {
        source.name: source
        for source in session.scalars(select(DataSource).where(DataSource.status == "valid")).all()
    }
    classes = [
        "cash",
        "bank_deposit",
        "fixed_income_fund",
        "gold_fund",
        "equity_fund",
        "index_fund",
        "mixed_fund",
        "leveraged_fund",
        "market_index",
        "short_term_trading",
    ]
    latest_observations = [
        source.last_valid_observation_at
        for source in sources.values()
        if source.last_valid_observation_at is not None
    ]
    return {
        "items": [
            {
                "asset_class": item,
                "historical_return": None,
                "real_return": None,
                "volatility": None,
                "maximum_drawdown": None,
                "quality_status": "valid" if sources else "missing",
                "latest_data_at": max(latest_observations, default=None),
                "value_kind": "historical_observation",
            }
            for item in classes
        ],
        "notice": "Missing metrics stay null; no future return is inferred.",
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
            item.metric_name: float(item.value) if item.value is not None else None
            for item in metrics
        },
    }


@router.post(
    "/v1/admin/data-refresh",
    dependencies=[Depends(require_admin_key)],
    tags=["admin"],
)
def admin_refresh(
    session: SessionDependency,
    dataset: str = Query(
        default="funds",
        pattern="^(funds|fund_history|market_indices|market_instruments|inflation|bank_products|all)$",
    ),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        if dataset == "market_indices":
            return refresh_market_indices(session, settings.market_index_csv_path)
        if dataset == "market_instruments":
            return refresh_market_instruments(session, settings.instrument_market_csv_path)
        if dataset == "inflation":
            return refresh_inflation(session, settings.inflation_csv_path)
        if dataset == "bank_products":
            return refresh_bank_products(session, settings.bank_product_csv_path)
        if dataset == "all":
            results: dict[str, Any] = {}
            jobs = {
                "market_indices": (refresh_market_indices, settings.market_index_csv_path),
                "market_instruments": (
                    refresh_market_instruments,
                    settings.instrument_market_csv_path,
                ),
                "inflation": (refresh_inflation, settings.inflation_csv_path),
                "bank_products": (refresh_bank_products, settings.bank_product_csv_path),
            }
            for name, (refresh, path) in jobs.items():
                try:
                    results[name] = refresh(session, path)
                except (FileNotFoundError, ValueError) as exc:
                    results[name] = {"status": "failed", "error": str(exc)}
            return {"dataset": "all", "results": results}
        if settings.fund_provider == "fipiran":
            return refresh_from_fipiran(
                session,
                base_url=settings.fipiran_base_url,
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
                min_interval_seconds=settings.provider_min_interval_seconds,
                history_limit=settings.fund_history_limit,
                catalog_path=settings.fipiran_catalog_path,
                history_path=settings.fipiran_history_path,
                user_agent=settings.fipiran_user_agent,
                failure_threshold=settings.provider_circuit_failures,
                cooldown_seconds=settings.provider_circuit_cooldown_seconds,
            )
        return refresh_from_configured_csv(
            session,
            csv_path=settings.fund_csv_path,
            max_retries=settings.provider_max_retries,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(exc)) from exc
    except (HTTPError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(exc)) from exc
    except RefreshAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/v1/admin/funds/backfill/{run_id}", dependencies=[Depends(require_admin_key)], tags=["admin"])
def backfill_status(run_id: str, session: SessionDependency) -> dict[str, Any]:
    run = session.scalar(select(BackfillRun).where(BackfillRun.run_id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="backfill run not found")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "funds_completed": run.funds_completed,
        "rows_written": run.rows_written,
        "errors": run.errors_json,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


@router.post(
    "/v1/admin/funds/backfill",
    dependencies=[Depends(require_admin_key)],
    tags=["admin"],
)
def start_fund_backfill(
    session: SessionDependency,
    limit: int = Query(default=10, ge=1, le=25),
    fund_type: str | None = Query(default=None),
) -> dict[str, object]:
    settings = get_settings()
    running = session.scalar(select(BackfillRun.id).where(BackfillRun.status == "running"))
    if running is not None:
        raise HTTPException(status_code=409, detail="a backfill is already running")
    with FipiranFundProvider(
        base_url=settings.fipiran_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        min_interval_seconds=settings.provider_min_interval_seconds,
        catalog_path=settings.fipiran_catalog_path,
        history_path=settings.fipiran_history_path,
        user_agent=settings.fipiran_user_agent,
        failure_threshold=settings.provider_circuit_failures,
        cooldown_seconds=settings.provider_circuit_cooldown_seconds,
        retries=settings.provider_max_retries,
    ) as provider:
        return backfill_fund_history(
            session,
            provider,
            limit=limit,
            fund_type=fund_type,
        )
