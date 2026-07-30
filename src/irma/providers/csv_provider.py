"""Validated manual CSV provider for funds when stable automatic sources are unavailable."""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from irma.providers.base import DataQuality, FundRecord, ProviderMetadata

REQUIRED_COLUMNS = {"name_fa", "fund_type", "source_identifier", "observed_at"}


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def _optional_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


class CsvFundProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self) -> list[FundRecord]:
        if not self.path.exists():
            raise FileNotFoundError(f"fund CSV not found: {self.path}")
        raw = self.path.read_bytes()
        raw_hash = hashlib.sha256(raw).hexdigest()
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise ValueError(f"fund CSV missing columns: {', '.join(sorted(missing))}")
            records: list[FundRecord] = []
            fetched_at = datetime.now(UTC)
            for row in reader:
                observed_at = datetime.fromisoformat(row["observed_at"])
                if observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=UTC)
                records.append(
                    FundRecord(
                        name_fa=row["name_fa"].strip(),
                        symbol=(row.get("symbol") or "").strip() or None,
                        fund_type=row["fund_type"].strip(),
                        is_etf=_optional_bool(row.get("is_etf")),
                        inception_date=(row.get("inception_date") or "").strip() or None,
                        nav=_optional_float(row.get("nav")),
                        market_price=_optional_float(row.get("market_price")),
                        volume=_optional_float(row.get("volume")),
                        manager=(row.get("manager") or "").strip() or None,
                        market_maker=(row.get("market_maker") or "").strip() or None,
                        metadata=ProviderMetadata(
                            source_name="manual-fund-csv",
                            source_identifier=row["source_identifier"].strip(),
                            fetched_at=fetched_at,
                            observed_at=observed_at,
                            unit="TOMAN",
                            quality=DataQuality.VALID,
                            data_version=row.get("data_version") or None,
                            raw_hash=raw_hash,
                        ),
                    )
                )
        return records
