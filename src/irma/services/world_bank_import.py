"""Reproducible importer for selected World Bank WDI indicators for Iran."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import DataSource, HistoricalObservation, HistoricalSeries

WORLD_BANK_API = "http://api.worldbank.org/v2/country/IRN/indicator/{indicator}"


class DatasetConfig(TypedDict):
    indicator: str
    code: str
    name_fa: str
    asset_class: str
    unit: str
    currency: str
    allow_negative: bool
    methodology: str


DATASETS: dict[str, DatasetConfig] = {
    "inflation_annual": {
        "indicator": "FP.CPI.TOTL.ZG",
        "code": "irn-wdi-inflation-annual",
        "name_fa": "تورم سالانه قیمت مصرف‌کننده ایران",
        "asset_class": "inflation",
        "unit": "percent",
        "currency": "PERCENT",
        "allow_negative": True,
        "methodology": "Annual CPI percentage change; IMF IFS, distributed by World Bank WDI.",
    },
    "fx_official_annual": {
        "indicator": "PA.NUS.FCRF",
        "code": "irn-wdi-official-usd-irr-annual-average",
        "name_fa": "نرخ رسمی متوسط سالانه ریال به دلار آمریکا",
        "asset_class": "fx_official",
        "unit": "IRR per USD",
        "currency": "IRRUSD",
        "allow_negative": False,
        "methodology": "Official exchange rate, LCU per USD, annual period average; IMF IFS via WDI.",
    },
}


def parse_world_bank_payload(
    raw: bytes, indicator: str, *, allow_negative: bool = False
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
        raise ValueError("unexpected World Bank API contract")
    metadata, records = payload
    if not isinstance(metadata, dict):
        raise ValueError("missing World Bank metadata")
    accepted: list[dict[str, Any]] = []
    seen: set[int] = set()
    for record in records:
        if (
            record.get("indicator", {}).get("id") != indicator
            or record.get("countryiso3code") != "IRN"
        ):
            raise ValueError("indicator or country identity mismatch")
        if record.get("value") is None:
            continue
        year = int(record["date"])
        value = Decimal(str(record["value"])).quantize(Decimal("0.00000001"))
        if year in seen:
            raise ValueError(f"duplicate World Bank year: {year}")
        if not allow_negative and value <= 0:
            raise ValueError(f"non-positive observation for {year}")
        seen.add(year)
        accepted.append({"year": year, "value": value})
    accepted.sort(key=lambda item: item["year"])
    if not accepted:
        raise ValueError("World Bank payload has no usable observations")
    return metadata, accepted


def import_world_bank_file(
    session: Session, path: Path, dataset_id: str, *, retrieved_at: datetime | None = None
) -> dict[str, Any]:
    config = DATASETS[dataset_id]
    raw = path.read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    metadata, records = parse_world_bank_payload(
        raw, config["indicator"], allow_negative=config["allow_negative"]
    )
    source_name = f"World Bank WDI {config['indicator']}"
    source = session.scalar(select(DataSource).where(DataSource.name == source_name))
    if source is None:
        source = DataSource(
            name=source_name,
            source_identifier=WORLD_BANK_API.format(indicator=config["indicator"]),
            source_type="international_official_api",
            unit=config["unit"],
            status="valid",
        )
        session.add(source)
        session.flush()
    series = session.scalar(select(HistoricalSeries).where(HistoricalSeries.code == config["code"]))
    if series is None:
        series = HistoricalSeries(
            code=config["code"],
            name_fa=config["name_fa"],
            asset_class=config["asset_class"],
            frequency="annual",
            unit=config["unit"],
            geography="Iran",
            source_id=source.id,
            methodology_note=config["methodology"],
        )
        session.add(series)
        session.flush()
    written = 0
    duplicates = 0
    for record in records:
        valid_at = date(record["year"], 12, 31)
        existing = session.scalar(
            select(HistoricalObservation).where(
                HistoricalObservation.series_id == series.id,
                HistoricalObservation.valid_at == valid_at,
            )
        )
        if existing is not None:
            if existing.value != record["value"]:
                raise ValueError(f"conflicting published value for {valid_at}")
            duplicates += 1
            continue
        session.add(
            HistoricalObservation(
                series_id=series.id,
                value=record["value"],
                source_id=source.id,
                observed_at=retrieved_at or datetime.now(UTC),
                valid_at=valid_at,
                publication_date=None,
                currency=config["currency"],
                quality_status="valid",
                raw_hash=raw_hash,
            )
        )
        written += 1
    latest = date(records[-1]["year"], 12, 31)
    source.last_fetched_at = retrieved_at or datetime.now(UTC)
    source.last_valid_observation_at = datetime.combine(latest, datetime.min.time(), tzinfo=UTC)
    source.data_version = str(metadata.get("lastupdated") or "unknown")
    source.raw_hash = raw_hash
    source.record_count = len(records)
    session.commit()
    return {
        "dataset_id": dataset_id,
        "indicator": config["indicator"],
        "rows_received": len(records),
        "rows_written": written,
        "duplicates": duplicates,
        "coverage_start": str(records[0]["year"]),
        "coverage_end": str(records[-1]["year"]),
        "frequency": "annual",
        "unit": config["unit"],
        "sha256": raw_hash,
        "source_version": source.data_version,
        "quality_status": "valid",
    }
