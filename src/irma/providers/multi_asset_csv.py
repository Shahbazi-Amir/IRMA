"""Strict provenance-aware CSV fallbacks for multi-asset datasets."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar, TypeVar

from irma.providers.base import (
    BankProductRecord,
    DataQuality,
    InflationRecord,
    InstrumentMarketRecord,
    MarketIndexRecord,
    ProviderMetadata,
)

T = TypeVar("T")


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    parsed = float(value)
    if parsed < 0:
        raise ValueError("financial observations cannot be negative")
    return parsed


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("counts cannot be negative")
    return parsed


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


class _CsvProvider:
    required_columns: ClassVar[set[str]]
    source_name: str

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self, convert: Callable[[dict[str, str], ProviderMetadata], T]) -> list[T]:
        if not self.path.exists():
            raise FileNotFoundError(f"{self.source_name} CSV not found: {self.path}")
        raw = self.path.read_bytes()
        raw_hash = hashlib.sha256(raw).hexdigest()
        fetched_at = datetime.now(UTC)
        records: list[T] = []
        seen: set[str] = set()
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = self.required_columns - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")
            for row in reader:
                source_identifier = row["source_identifier"].strip()
                observed_at = _datetime(row["observed_at"])
                unique_key = f"{source_identifier}:{row.get('period', observed_at.date())}"
                if unique_key in seen:
                    raise ValueError(f"duplicate CSV observation: {unique_key}")
                seen.add(unique_key)
                metadata = ProviderMetadata(
                    source_name=self.source_name,
                    source_identifier=source_identifier,
                    fetched_at=fetched_at,
                    observed_at=observed_at,
                    unit=(row.get("unit") or "").strip() or None,
                    quality=DataQuality.VALID,
                    data_version=(row.get("data_version") or "").strip() or None,
                    raw_hash=raw_hash,
                )
                records.append(convert(row, metadata))
        return records


class CsvMarketIndexProvider(_CsvProvider):
    source_name = "market-index-csv"
    required_columns: ClassVar[set[str]] = {
        "source_identifier",
        "index_code",
        "name_fa",
        "observation_date",
        "observed_at",
    }

    def fetch(self) -> list[MarketIndexRecord]:
        def convert(row: dict[str, str], metadata: ProviderMetadata) -> MarketIndexRecord:
            observation = _datetime(row["observation_date"])
            values = [_optional_float(row.get(field)) for field in ("open", "high", "low", "close")]
            if all(value is None for value in values):
                raise ValueError("an index observation needs at least one value")
            return MarketIndexRecord(
                index_code=row["index_code"].strip(),
                name_fa=row["name_fa"].strip(),
                name_en=(row.get("name_en") or "").strip() or None,
                observation_date=observation,
                open_value=values[0],
                high_value=values[1],
                low_value=values[2],
                close_value=values[3],
                change_value=_optional_float(row.get("change")),
                change_percent=_optional_float(row.get("change_percent")),
                metadata=metadata,
            )

        return self._read(convert)


class CsvInstrumentMarketProvider(_CsvProvider):
    source_name = "instrument-market-csv"
    required_columns: ClassVar[set[str]] = {
        "source_identifier",
        "stable_id",
        "symbol",
        "name_fa",
        "instrument_type",
        "observation_date",
        "observed_at",
    }

    def fetch(self) -> list[InstrumentMarketRecord]:
        def convert(row: dict[str, str], metadata: ProviderMetadata) -> InstrumentMarketRecord:
            prices = [
                _optional_float(row.get(field))
                for field in ("open", "high", "low", "close", "last")
            ]
            if all(value is None for value in prices):
                raise ValueError("an instrument observation needs a market price")
            return InstrumentMarketRecord(
                stable_id=row["stable_id"].strip(),
                symbol=row["symbol"].strip(),
                name_fa=row["name_fa"].strip(),
                instrument_type=row["instrument_type"].strip(),
                observation_date=_datetime(row["observation_date"]),
                open_price=prices[0],
                high_price=prices[1],
                low_price=prices[2],
                close_price=prices[3],
                last_price=prices[4],
                volume=_optional_float(row.get("volume")),
                trade_value=_optional_float(row.get("trade_value")),
                trade_count=_optional_int(row.get("trade_count")),
                best_bid=_optional_float(row.get("best_bid")),
                best_ask=_optional_float(row.get("best_ask")),
                market_status=(row.get("market_status") or "").strip() or None,
                metadata=metadata,
            )

        return self._read(convert)


class CsvInflationProvider(_CsvProvider):
    source_name = "official-inflation-csv"
    required_columns: ClassVar[set[str]] = {
        "source_identifier",
        "indicator_code",
        "indicator_name",
        "period",
        "period_type",
        "base_year",
        "publication_date",
        "observed_at",
    }

    def fetch(self) -> list[InflationRecord]:
        def convert(row: dict[str, str], metadata: ProviderMetadata) -> InflationRecord:
            publication_date = date.fromisoformat(row["publication_date"])
            if publication_date > date.today():
                raise ValueError("inflation publication date cannot be in the future")
            values = [
                _optional_float(row.get(field))
                for field in (
                    "monthly_inflation",
                    "point_to_point_inflation",
                    "annual_inflation",
                    "consumer_price_index",
                )
            ]
            if all(value is None for value in values):
                raise ValueError("inflation observation cannot be empty")
            return InflationRecord(
                indicator_code=row["indicator_code"].strip(),
                indicator_name=row["indicator_name"].strip(),
                period=row["period"].strip(),
                period_type=row["period_type"].strip(),
                monthly_inflation=values[0],
                point_to_point_inflation=values[1],
                annual_inflation=values[2],
                consumer_price_index=values[3],
                base_year=row["base_year"].strip(),
                publication_date=publication_date.isoformat(),
                metadata=metadata,
            )

        return self._read(convert)


class CsvBankProductProvider(_CsvProvider):
    source_name = "verified-bank-product-csv"
    required_columns: ClassVar[set[str]] = {
        "source_identifier",
        "bank_name",
        "product_name",
        "product_type",
        "source_url",
        "publication_date",
        "valid_from",
        "verification_status",
        "observed_at",
    }
    accepted_statuses: ClassVar[set[str]] = {"official_verified", "manual_verified"}

    def fetch(self) -> list[BankProductRecord]:
        def convert(row: dict[str, str], metadata: ProviderMetadata) -> BankProductRecord:
            status = row["verification_status"].strip()
            if status not in {
                "official_verified",
                "official_outdated",
                "manual_verified",
                "unverified",
                "expired",
            }:
                raise ValueError(f"invalid bank verification status: {status}")
            source_url = row["source_url"].strip()
            if not source_url.startswith("https://"):
                raise ValueError("bank product source_url must use https")
            nominal = _optional_float(row.get("nominal_rate"))
            effective = _optional_float(row.get("effective_rate"))
            if nominal is None and effective is None:
                raise ValueError("bank product needs a verified rate")
            return BankProductRecord(
                bank_name=row["bank_name"].strip(),
                product_name=row["product_name"].strip(),
                product_type=row["product_type"].strip(),
                nominal_rate=nominal,
                effective_rate=effective,
                minimum_deposit_toman=_optional_float(row.get("minimum_deposit_toman")),
                term_months=_optional_int(row.get("term_months")),
                early_withdrawal_rate=_optional_float(row.get("early_withdrawal_rate")),
                payment_frequency=(row.get("payment_frequency") or "").strip() or None,
                conditions_summary=(row.get("conditions_summary") or "").strip() or None,
                source_url=source_url,
                publication_date=date.fromisoformat(row["publication_date"]).isoformat(),
                valid_from=date.fromisoformat(row["valid_from"]).isoformat(),
                valid_until=(row.get("valid_until") or "").strip() or None,
                verification_status=status,
                metadata=metadata,
            )

        return self._read(convert)
