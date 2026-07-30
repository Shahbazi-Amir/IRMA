from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.persistence.models import BackfillCheckpoint, DataSource, Fund, FundNavHistory
from irma.providers.base import DataQuality, FundNavRecord, ProviderMetadata
from irma.services.fund_backfill import backfill_fund_history


class HistoryProvider:
    source_name = "official-history"

    def __init__(self, *, broken: set[str] | None = None) -> None:
        self.broken = broken or set()

    def fetch(self):  # type: ignore[no-untyped-def]
        return []

    def fetch_nav_history(self, external_id: str) -> list[FundNavRecord]:
        if external_id in self.broken:
            raise OSError("source unavailable")
        now = datetime.now(UTC)
        metadata = ProviderMetadata(
            source_name=self.source_name,
            source_identifier="official:test",
            fetched_at=now,
            observed_at=now,
            unit="IRR",
            quality=DataQuality.VALID,
        )
        return [
            FundNavRecord(
                external_id=external_id,
                observed_at=now - timedelta(days=2 - index),
                nav=1000 + index,
                total_net_assets=None,
                metadata=metadata,
            )
            for index in range(3)
        ]


def funds(session: Session) -> None:
    source = DataSource(
        name="official-history",
        source_identifier="official:test",
        source_type="official_file",
    )
    session.add(source)
    session.flush()
    session.add_all(
        [
            Fund(
                external_id="A",
                name_fa="الف",
                fund_type="fixed_income",
                source_id=source.id,
                is_active=True,
            ),
            Fund(
                external_id="B",
                name_fa="ب",
                fund_type="fixed_income",
                source_id=source.id,
                is_active=True,
            ),
        ]
    )
    session.commit()


def test_backfill_is_resumable_and_prevents_duplicates(session: Session) -> None:
    funds(session)
    first = backfill_fund_history(session, HistoryProvider(), limit=2, run_id="resume-1")
    second = backfill_fund_history(session, HistoryProvider(), limit=2, run_id="resume-1")
    assert first["rows_written"] == 6
    assert second["rows_written"] == 6
    assert session.scalar(select(func.count(FundNavHistory.id))) == 6
    checkpoints = session.scalars(select(BackfillCheckpoint)).all()
    assert {item.status for item in checkpoints} == {"completed"}


def test_backfill_continues_after_partial_failure(session: Session) -> None:
    funds(session)
    result = backfill_fund_history(
        session,
        HistoryProvider(broken={"A"}),
        limit=2,
        from_date=date.today() - timedelta(days=10),
    )
    assert result["status"] == "completed_with_errors"
    assert result["funds_completed"] == 1
    assert result["rows_written"] == 3
    checkpoints = session.scalars(select(BackfillCheckpoint)).all()
    assert {item.status for item in checkpoints} == {"completed", "error"}
