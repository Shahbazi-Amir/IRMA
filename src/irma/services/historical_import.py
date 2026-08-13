"""Auditable canonical CSV importer for verified historical source exports."""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import (
    DataSource,
    HistoricalObservation,
    HistoricalSeries,
)

REQUIRED_COLUMNS = {"observation_date", "value"}


def import_historical_csv(
    session: Session,
    path: Path,
    *,
    code: str,
    name_fa: str,
    asset_class: str,
    frequency: str,
    unit: str,
    geography: str | None,
    source_name: str,
    source_identifier: str,
    methodology_note: str,
) -> dict[str, int | str]:
    raw = path.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows or not set(rows[0]) >= REQUIRED_COLUMNS:
        raise ValueError("historical CSV requires observation_date and value")
    source = session.scalar(select(DataSource).where(DataSource.name == source_name))
    if source is None:
        source = DataSource(
            name=source_name,
            source_identifier=source_identifier,
            source_type="official_file",
            status="valid",
        )
        session.add(source)
        session.flush()
    series = session.scalar(select(HistoricalSeries).where(HistoricalSeries.code == code))
    if series is None:
        series = HistoricalSeries(
            code=code,
            name_fa=name_fa,
            asset_class=asset_class,
            frequency=frequency,
            unit=unit,
            geography=geography,
            source_id=source.id,
            methodology_note=methodology_note,
        )
        session.add(series)
        session.flush()
    written = 0
    latest: date | None = None
    for row in rows:
        observed = date.fromisoformat(row["observation_date"])
        value = Decimal(row["value"])
        if value <= 0:
            raise ValueError("historical values must be positive")
        latest = max(latest, observed) if latest else observed
        exists = session.scalar(
            select(HistoricalObservation.id).where(
                HistoricalObservation.series_id == series.id,
                HistoricalObservation.valid_at == observed,
            )
        )
        if exists is not None:
            continue
        session.add(
            HistoricalObservation(
                series_id=series.id,
                value=value,
                source_id=source.id,
                observed_at=datetime.now(UTC),
                valid_at=observed,
                publication_date=date.fromisoformat(row["publication_date"])
                if row.get("publication_date")
                else None,
                currency=unit,
                quality_status="valid",
                raw_hash=file_hash,
            )
        )
        written += 1
    source.last_fetched_at = datetime.now(UTC)
    source.last_valid_observation_at = (
        datetime.combine(latest, datetime.min.time(), tzinfo=UTC) if latest else None
    )
    source.raw_hash = file_hash
    source.record_count = len(rows)
    session.commit()
    return {
        "status": "success",
        "rows_received": len(rows),
        "rows_written": written,
        "sha256": file_hash,
    }
