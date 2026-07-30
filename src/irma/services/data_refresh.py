"""Synchronous refresh coordinator with bounded retries and overlap protection."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from httpx import HTTPError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.analytics.funds import calculate_fund_analytics
from irma.persistence.models import (
    DataIngestionRun,
    DataSource,
    Fund,
    FundMarketHistory,
    FundMetric,
    FundNavHistory,
)
from irma.providers.base import FundNavRecord, FundProvider, FundRecord, HistoricalFundProvider
from irma.providers.csv_provider import CsvFundProvider
from irma.providers.fipiran import FipiranFundProvider

logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()


class RefreshAlreadyRunningError(RuntimeError):
    pass


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class RefreshCoordinator:
    def __init__(
        self, *, max_retries: int = 2, sleep: Callable[[float], None] = time.sleep
    ) -> None:
        self.max_retries = max_retries
        self.sleep = sleep

    def fetch_with_retry(self, provider: FundProvider) -> list[FundRecord]:
        error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return provider.fetch()
            except (OSError, HTTPError, ValueError) as exc:
                error = exc
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, 4))
        assert error is not None
        raise error

    def fetch_history_with_retry(
        self, provider: HistoricalFundProvider, external_id: str
    ) -> list[FundNavRecord]:
        error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return provider.fetch_nav_history(external_id)
            except (OSError, HTTPError, ValueError) as exc:
                error = exc
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, 4))
        assert error is not None
        raise error

    def refresh_funds(
        self,
        session: Session,
        provider: FundProvider,
        *,
        history_limit: int = 0,
    ) -> dict[str, int | str]:
        if not _refresh_lock.acquire(blocking=False):
            raise RefreshAlreadyRunningError("a data refresh is already running")
        run = DataIngestionRun(status="running")
        session.add(run)
        session.commit()
        try:
            records = self.fetch_with_retry(provider)
            run.records_received = len(records)
            written = 0
            history_written = 0
            for record in records:
                source = session.scalar(
                    select(DataSource).where(DataSource.name == record.metadata.source_name)
                )
                if source is None:
                    source = DataSource(
                        name=record.metadata.source_name,
                        source_identifier=record.metadata.source_identifier,
                        source_type="api"
                        if record.metadata.source_name == "fipiran"
                        else "manual_csv",
                        unit=record.metadata.unit,
                    )
                    session.add(source)
                    session.flush()
                source.status = record.metadata.quality.value
                source.last_fetched_at = record.metadata.fetched_at
                source.last_valid_observation_at = record.metadata.observed_at
                source.last_error = None
                source.data_version = record.metadata.data_version
                source.raw_hash = record.metadata.raw_hash

                fund = session.scalar(select(Fund).where(Fund.external_id == record.external_id))
                if record.symbol:
                    fund = fund or session.scalar(select(Fund).where(Fund.symbol == record.symbol))
                if fund is None:
                    fund = session.scalar(
                        select(Fund).where(
                            Fund.name_fa == record.name_fa,
                            Fund.fund_type == record.fund_type,
                        )
                    )
                if fund is None:
                    fund = Fund(name_fa=record.name_fa, fund_type=record.fund_type)
                    session.add(fund)
                fund.external_id = record.external_id
                fund.name_fa = record.name_fa
                fund.fund_type = record.fund_type
                fund.symbol = record.symbol
                fund.is_etf = record.is_etf
                fund.inception_date = _parse_date(record.inception_date)
                fund.manager = record.manager
                fund.market_maker = record.market_maker
                fund.is_active = record.is_active
                fund.asset_allocation_json = record.asset_allocation
                fund.source_id = source.id
                fund.quality_status = record.metadata.quality.value
                fund.last_data_at = record.metadata.observed_at
                session.flush()
                observed_at = record.metadata.observed_at or datetime.now(UTC)
                existing_nav = session.scalar(
                    select(FundNavHistory).where(
                        FundNavHistory.fund_id == fund.id,
                        FundNavHistory.valid_at == observed_at.date(),
                    )
                )
                if record.nav is not None and existing_nav is None:
                    session.add(
                        FundNavHistory(
                            fund_id=fund.id,
                            nav=Decimal(str(record.nav)),
                            total_net_assets=Decimal(str(record.total_net_assets))
                            if record.total_net_assets is not None
                            else None,
                            source_id=source.id,
                            observed_at=observed_at,
                            valid_at=observed_at.date(),
                            quality_status=record.metadata.quality.value,
                        )
                    )
                    history_written += 1
                existing_market = session.scalar(
                    select(FundMarketHistory).where(
                        FundMarketHistory.fund_id == fund.id,
                        FundMarketHistory.valid_at == observed_at.date(),
                    )
                )
                if (
                    record.market_price is not None
                    or record.volume is not None
                    or record.trade_value is not None
                ) and existing_market is None:
                    session.add(
                        FundMarketHistory(
                            fund_id=fund.id,
                            market_price=(
                                Decimal(str(record.market_price))
                                if record.market_price is not None
                                else None
                            ),
                            volume=Decimal(str(record.volume))
                            if record.volume is not None
                            else None,
                            trade_value=Decimal(str(record.trade_value))
                            if record.trade_value is not None
                            else None,
                            source_id=source.id,
                            observed_at=observed_at,
                            valid_at=observed_at.date(),
                            quality_status=record.metadata.quality.value,
                        )
                    )
                source.record_count += 1
                written += 1
            if isinstance(provider, HistoricalFundProvider) and history_limit > 0:
                history_counts: dict[str, int] = {}
                for record in records:
                    if not record.is_active:
                        continue
                    history_counts[record.external_id] = (
                        session.scalar(
                            select(func.count(FundNavHistory.id))
                            .join(Fund, Fund.id == FundNavHistory.fund_id)
                            .where(Fund.external_id == record.external_id)
                        )
                        or 0
                    )
                eligible = sorted(
                    (record for record in records if record.is_active),
                    key=lambda record: (history_counts[record.external_id], record.external_id),
                )[:history_limit]
                for record in eligible:
                    fund = session.scalar(
                        select(Fund).where(Fund.external_id == record.external_id)
                    )
                    assert fund is not None
                    for nav_record in self.fetch_history_with_retry(provider, record.external_id):
                        existing = session.scalar(
                            select(FundNavHistory.id).where(
                                FundNavHistory.fund_id == fund.id,
                                FundNavHistory.valid_at == nav_record.observed_at.date(),
                            )
                        )
                        if existing is not None:
                            continue
                        session.add(
                            FundNavHistory(
                                fund_id=fund.id,
                                nav=Decimal(str(nav_record.nav)),
                                total_net_assets=Decimal(str(nav_record.total_net_assets))
                                if nav_record.total_net_assets is not None
                                else None,
                                source_id=fund.source_id,
                                observed_at=nav_record.observed_at,
                                valid_at=nav_record.observed_at.date(),
                                quality_status=nav_record.metadata.quality.value,
                            )
                        )
                        history_written += 1
                    session.flush()
                    _refresh_metrics(session, fund)
            run.records_written = written
            run.status = "success"
            run.finished_at = datetime.now(UTC)
            session.commit()
            logger.info("fund refresh completed", extra={"records_written": written})
            return {
                "status": "success",
                "records_received": len(records),
                "records_written": written,
                "history_written": history_written,
            }
        except Exception as exc:
            session.rollback()
            current = session.get(DataIngestionRun, run.id)
            if current is not None:
                current.status = "error"
                current.error = str(exc)
                current.finished_at = datetime.now(UTC)
                session.commit()
            logger.exception("fund refresh failed")
            raise
        finally:
            _refresh_lock.release()


def refresh_from_configured_csv(
    session: Session,
    *,
    csv_path: str,
    max_retries: int,
) -> dict[str, int | str]:
    provider = CsvFundProvider(Path(csv_path))
    return RefreshCoordinator(max_retries=max_retries).refresh_funds(session, provider)


def refresh_from_fipiran(
    session: Session,
    *,
    base_url: str,
    timeout_seconds: int,
    max_retries: int,
    min_interval_seconds: float,
    history_limit: int,
) -> dict[str, int | str]:
    provider = FipiranFundProvider(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        min_interval_seconds=min_interval_seconds,
    )
    return RefreshCoordinator(max_retries=max_retries).refresh_funds(
        session, provider, history_limit=history_limit
    )


def _refresh_metrics(session: Session, fund: Fund) -> None:
    observations = session.scalars(
        select(FundNavHistory)
        .where(FundNavHistory.fund_id == fund.id, FundNavHistory.nav.is_not(None))
        .order_by(FundNavHistory.valid_at)
    ).all()
    if len(observations) < 2:
        return
    result = calculate_fund_analytics(
        dates=[item.valid_at for item in observations if item.valid_at is not None],
        nav_values=[float(item.nav) for item in observations if item.nav is not None],
    )
    values = {
        "total_return": result.total_return,
        "cagr": result.cagr,
        "volatility": result.volatility,
        "maximum_drawdown": result.maximum_drawdown,
        "recovery_periods": result.recovery_periods,
        "sharpe": result.sharpe,
        "positive_period_ratio": result.positive_period_ratio,
        "data_quality_score": result.data_quality_score,
    }
    session.query(FundMetric).filter(FundMetric.fund_id == fund.id).delete()
    last = observations[-1]
    for name, value in values.items():
        session.add(
            FundMetric(
                fund_id=fund.id,
                metric_name=name,
                value=Decimal(str(value)) if value is not None else None,
                period_label="all_available",
                source_id=fund.source_id,
                observed_at=last.observed_at,
                valid_at=last.valid_at,
                quality_status=fund.quality_status,
            )
        )
