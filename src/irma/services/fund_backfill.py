"""Resumable, per-fund NAV backfill with small commits."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import BackfillCheckpoint, BackfillRun, Fund, FundNavHistory
from irma.providers.base import HistoricalFundProvider


def backfill_fund_history(
    session: Session,
    provider: HistoricalFundProvider,
    *,
    limit: int = 10,
    fund_type: str | None = None,
    from_date: date | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    identifier = run_id or uuid.uuid4().hex
    run = session.scalar(select(BackfillRun).where(BackfillRun.run_id == identifier))
    if run is None:
        run = BackfillRun(
            run_id=identifier,
            provider=str(getattr(provider, "source_name", type(provider).__name__)),
            status="running",
        )
        session.add(run)
        session.commit()
    query = select(Fund).where(Fund.is_active.is_(True), Fund.external_id.is_not(None))
    if fund_type:
        query = query.where(Fund.fund_type == fund_type)
    funds = session.scalars(query.order_by(Fund.id).limit(limit)).all()
    errors: list[str] = list(run.errors_json)
    for fund in funds:
        assert fund.external_id is not None
        checkpoint = session.scalar(
            select(BackfillCheckpoint).where(
                BackfillCheckpoint.run_id == identifier,
                BackfillCheckpoint.fund_external_id == fund.external_id,
            )
        )
        if checkpoint is not None and checkpoint.status == "completed":
            continue
        checkpoint = checkpoint or BackfillCheckpoint(
            run_id=identifier, fund_external_id=fund.external_id
        )
        session.add(checkpoint)
        try:
            written = 0
            latest = checkpoint.last_date
            for record in provider.fetch_nav_history(fund.external_id):
                valid_at = record.observed_at.date()
                if from_date and valid_at < from_date:
                    continue
                if latest and valid_at <= latest:
                    continue
                exists = session.scalar(
                    select(FundNavHistory.id).where(
                        FundNavHistory.fund_id == fund.id,
                        FundNavHistory.valid_at == valid_at,
                    )
                )
                if exists is None:
                    session.add(
                        FundNavHistory(
                            fund_id=fund.id,
                            nav=Decimal(str(record.nav)),
                            total_net_assets=None,
                            source_id=fund.source_id,
                            observed_at=record.observed_at,
                            valid_at=valid_at,
                            quality_status=record.metadata.quality.value,
                        )
                    )
                    written += 1
                checkpoint.last_date = max(checkpoint.last_date or valid_at, valid_at)
            checkpoint.status = "completed"
            run.funds_completed += 1
            run.rows_written += written
            session.commit()
        except Exception as exc:
            session.rollback()
            checkpoint = session.scalar(
                select(BackfillCheckpoint).where(
                    BackfillCheckpoint.run_id == identifier,
                    BackfillCheckpoint.fund_external_id == fund.external_id,
                )
            ) or BackfillCheckpoint(run_id=identifier, fund_external_id=fund.external_id)
            checkpoint.status = "error"
            checkpoint.error = type(exc).__name__
            session.add(checkpoint)
            errors.append(f"{fund.external_id}: {type(exc).__name__}")
            run = session.scalar(select(BackfillRun).where(BackfillRun.run_id == identifier))
            assert run is not None
            run.errors_json = errors
            session.commit()
    run = session.scalar(select(BackfillRun).where(BackfillRun.run_id == identifier))
    assert run is not None
    run.status = "completed_with_errors" if errors else "completed"
    run.finished_at = datetime.now(UTC)
    session.commit()
    return {
        "run_id": identifier,
        "status": run.status,
        "funds_completed": run.funds_completed,
        "rows_written": run.rows_written,
        "errors": errors,
    }
