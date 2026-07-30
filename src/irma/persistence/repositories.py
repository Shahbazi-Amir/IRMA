"""Small repositories used by API services."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import DataSource, Fund, FundMetric


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
    return [
        {
            "id": fund.id,
            "symbol": fund.symbol,
            "name_fa": fund.name_fa,
            "fund_type": fund.fund_type,
            "inception_date": fund.inception_date,
            "is_etf": fund.is_etf,
            "manager": fund.manager,
            "market_maker": fund.market_maker,
            "quality_status": fund.quality_status,
            "last_data_at": fund.last_data_at,
        }
        for fund in funds
    ]


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
