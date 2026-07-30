"""Provider contracts and provenance models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class DataQuality(StrEnum):
    VALID = "valid"
    STALE = "stale"
    MISSING = "missing"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    source_name: str
    source_identifier: str
    fetched_at: datetime
    observed_at: datetime | None
    unit: str | None
    quality: DataQuality
    data_version: str | None = None
    raw_hash: str | None = None


@dataclass(frozen=True, slots=True)
class FundRecord:
    external_id: str
    name_fa: str
    symbol: str | None
    fund_type: str
    is_etf: bool
    inception_date: str | None
    nav: float | None
    market_price: float | None
    volume: float | None
    trade_value: float | None
    total_net_assets: float | None
    manager: str | None
    market_maker: str | None
    is_active: bool
    asset_allocation: dict[str, float | None]
    metadata: ProviderMetadata


class FundProvider(Protocol):
    def fetch(self) -> list[FundRecord]: ...


@dataclass(frozen=True, slots=True)
class FundNavRecord:
    external_id: str
    observed_at: datetime
    nav: float
    total_net_assets: float | None
    metadata: ProviderMetadata


@runtime_checkable
class HistoricalFundProvider(FundProvider, Protocol):
    def fetch_nav_history(self, external_id: str) -> list[FundNavRecord]: ...
