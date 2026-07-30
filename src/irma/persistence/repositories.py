"""Small repositories used by API services."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.persistence.models import DataSource, Fund, FundMetric, FundNavHistory


def list_funds(
    session: Session,
    *,
    fund_type: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    statement = select(Fund).order_by(Fund.name_fa)
    if fund_type:
        statement = statement.where(Fund.fund_type == fund_type)
    if query:
        statement = statement.where(Fund.name_fa.contains(query))
    funds = session.scalars(statement).all()
    results = []
    for fund in funds:
        latest_nav = session.scalar(
            select(FundNavHistory)
            .where(FundNavHistory.fund_id == fund.id)
            .order_by(FundNavHistory.valid_at.desc())
            .limit(1)
        )
        source = session.get(DataSource, fund.source_id) if fund.source_id else None
        observation_count = (
            session.scalar(
                select(func.count(FundNavHistory.id)).where(FundNavHistory.fund_id == fund.id)
            )
            or 0
        )
        now = datetime.now(UTC)
        last_data_at = fund.last_data_at
        if last_data_at is not None:
            last_data_at = last_data_at.replace(tzinfo=last_data_at.tzinfo or UTC)
        freshness = (
            "unavailable"
            if last_data_at is None
            else "stale"
            if now - last_data_at > timedelta(days=7)
            else "live"
            if source and source.source_type == "api"
            else "official_file"
        )
        results.append(
            {
                "id": fund.id,
                "external_id": fund.external_id,
                "symbol": fund.symbol,
                "name_fa": fund.name_fa,
                "fund_type": fund.fund_type,
                "inception_date": fund.inception_date,
                "is_etf": fund.is_etf,
                "manager": fund.manager,
                "market_maker": fund.market_maker,
                "is_active": fund.is_active,
                "asset_allocation": fund.asset_allocation_json,
                "latest_nav": float(latest_nav.nav)
                if latest_nav is not None and latest_nav.nav is not None
                else None,
                "total_net_assets": float(latest_nav.total_net_assets)
                if latest_nav is not None and latest_nav.total_net_assets is not None
                else None,
                "quality_status": fund.quality_status,
                "last_data_at": fund.last_data_at,
                "source_id": fund.source_id,
                "source": source.name if source else None,
                "source_status": freshness,
                "observation_count": observation_count,
            }
        )
    return results


def get_fund(session: Session, fund_id: int) -> dict[str, Any] | None:
    fund = session.get(Fund, fund_id)
    if fund is None:
        return None
    metrics = session.scalars(
        select(FundMetric).where(FundMetric.fund_id == fund_id).order_by(FundMetric.metric_name)
    ).all()
    payload = list_funds(session, query=fund.name_fa)
    result = next((item for item in payload if item["id"] == fund_id), None)
    if result is None:
        return None
    result["metrics"] = [
        {
            "name": metric.metric_name,
            "value": float(metric.value) if metric.value is not None else None,
            "period": metric.period_label,
            "quality_status": metric.quality_status,
            "valid_at": metric.valid_at,
        }
        for metric in metrics
    ]
    return result


def data_source_status(session: Session, *, stale_after_hours: int = 48) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    sources = session.scalars(select(DataSource).order_by(DataSource.name)).all()
    results: list[dict[str, Any]] = []
    for source in sources:
        status = source.status
        if source.last_valid_observation_at and (
            now - source.last_valid_observation_at > timedelta(hours=stale_after_hours)
        ):
            status = "stale"
        results.append(
            {
                "id": source.id,
                "name": source.name,
                "source_identifier": source.source_identifier,
                "status": status,
                "last_fetched_at": source.last_fetched_at,
                "last_valid_observation_at": source.last_valid_observation_at,
                "record_count": source.record_count,
                "last_error": source.last_error,
                "data_version": source.data_version,
                "raw_hash": source.raw_hash,
            }
        )
    return results
