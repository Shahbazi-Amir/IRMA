"""Synchronous refresh coordinator with bounded retries and overlap protection."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import (
    DataIngestionRun,
    DataSource,
    Fund,
    FundMarketHistory,
    FundNavHistory,
)
from irma.providers.base import FundProvider, FundRecord
from irma.providers.csv_provider import CsvFundProvider

logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()


class RefreshAlreadyRunningError(RuntimeError):
    pass


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class RefreshCoordinator:
    def __init__(self, *, max_retries: int = 2, sleep: Callable[[float], None] = time.sleep) -> None:
        self.max_retries = max_retries
        self.sleep = sleep

    def fetch_with_retry(self, provider: FundProvider) -> list[FundRecord]:
        error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return provider.fetch()
            except (OSError, ValueError) as exc:
                error = exc
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, 4))
        assert error is not None
        raise error

    def refresh_funds(self, session: Session, provider: FundProvider) -> dict[str, int | str]:
        if not _refresh_lock.acquire(blocking=False):
            raise RefreshAlreadyRunningError("a data refresh is already running")
        run = DataIngestionRun(status="running")
        session.add(run)
        session.commit()
        try:
            records = self.fetch_with_retry(provider)
            run.records_received = len(records)
            written = 0
            for record in records:
                source = session.scalar(
                    select(DataSource).where(DataSource.name == record.metadata.source_name)
                )
                if source is None:
                    source = DataSource(
                        name=record.metadata.source_name,
                        source_identifier=record.metadata.source_identifier,
                        source_type="manual_csv",
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

                fund = None
                if record.symbol:
                    fund = session.scalar(select(Fund).where(Fund.symbol == record.symbol))
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
                fund.symbol = record.symbol
                fund.is_etf = record.is_etf
                fund.inception_date = _parse_date(record.inception_date)
                fund.manager = record.manager
                fund.market_maker = record.market_maker
                fund.source_id = source.id
                fund.quality_status = record.metadata.quality.value
                fund.last_data_at = record.metadata.observed_at
                session.flush()
                if record.nav is not None:
                    session.add(
                        FundNavHistory(
                            fund_id=fund.id,
                            nav=Decimal(str(record.nav)),
                            source_id=source.id,
                            observed_at=record.metadata.observed_at or datetime.now(UTC),
                            valid_at=(record.metadata.observed_at or datetime.now(UTC)).date(),
                            quality_status=record.metadata.quality.value,
                        )
                    )
                if record.market_price is not None or record.volume is not None:
                    session.add(
                        FundMarketHistory(
                            fund_id=fund.id,
                            market_price=(
                                Decimal(str(record.market_price))
                                if record.market_price is not None
                                else None
                            ),
                            volume=Decimal(str(record.volume)) if record.volume is not None else None,
                            source_id=source.id,
                            observed_at=record.metadata.observed_at or datetime.now(UTC),
                            valid_at=(record.metadata.observed_at or datetime.now(UTC)).date(),
                            quality_status=record.metadata.quality.value,
                        )
                    )
                source.record_count += 1
                written += 1
            run.records_written = written
            run.status = "success"
            run.finished_at = datetime.now(UTC)
            session.commit()
            logger.info("fund refresh completed", extra={"records_written": written})
            return {"status": "success", "records_received": len(records), "records_written": written}
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
