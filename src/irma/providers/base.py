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


@dataclass(frozen=True, slots=True)
class MarketIndexRecord:
    index_code: str
    name_fa: str
    name_en: str | None
    observation_date: datetime
    open_value: float | None
    high_value: float | None
    low_value: float | None
    close_value: float | None
    change_value: float | None
    change_percent: float | None
    metadata: ProviderMetadata


@dataclass(frozen=True, slots=True)
class InstrumentMarketRecord:
    stable_id: str
    symbol: str
    name_fa: str
    instrument_type: str
    observation_date: datetime
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    last_price: float | None
    volume: float | None
    trade_value: float | None
    trade_count: int | None
    best_bid: float | None
    best_ask: float | None
    market_status: str | None
    metadata: ProviderMetadata


@dataclass(frozen=True, slots=True)
class InflationRecord:
    indicator_code: str
    indicator_name: str
    period: str
    period_type: str
    monthly_inflation: float | None
    point_to_point_inflation: float | None
    annual_inflation: float | None
    consumer_price_index: float | None
    base_year: str
    publication_date: str
    metadata: ProviderMetadata


@dataclass(frozen=True, slots=True)
class BankProductRecord:
    bank_name: str
    product_name: str
    product_type: str
    nominal_rate: float | None
    effective_rate: float | None
    minimum_deposit_toman: float | None
    term_months: int | None
    early_withdrawal_rate: float | None
    payment_frequency: str | None
    conditions_summary: str | None
    source_url: str
    publication_date: str
    valid_from: str
    valid_until: str | None
    verification_status: str
    metadata: ProviderMetadata
