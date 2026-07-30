"""Database models for sourced financial data and auditable analysis runs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProvenanceMixin:
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="TOMAN")
    quality_status: Mapped[str] = mapped_column(String(20), default="missing")


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_identifier: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40))
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="missing")
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_valid_observation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)


class DataIngestionRun(Base):
    __tablename__ = "data_ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name_fa: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(40), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AssetPrice(Base, ProvenanceMixin):
    __tablename__ = "asset_prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)
    trade_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)
    market_status: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Fund(Base, TimestampMixin):
    __tablename__ = "funds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(
        String(80), unique=True, nullable=True, index=True
    )
    symbol: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True, index=True)
    name_fa: Mapped[str] = mapped_column(String(200), index=True)
    fund_type: Mapped[str] = mapped_column(String(40), index=True)
    inception_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_etf: Mapped[bool] = mapped_column(Boolean, default=False)
    manager: Mapped[str | None] = mapped_column(String(200), nullable=True)
    market_maker: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    asset_allocation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(20), default="missing")
    last_data_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FundNavHistory(Base, ProvenanceMixin):
    __tablename__ = "fund_nav_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    total_net_assets: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)


class FundMarketHistory(Base, ProvenanceMixin):
    __tablename__ = "fund_market_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)
    trade_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)


class FundMetric(Base, ProvenanceMixin):
    __tablename__ = "fund_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(60), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(40), nullable=True)


class BankProduct(Base, ProvenanceMixin, TimestampMixin):
    __tablename__ = "bank_products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_name: Mapped[str] = mapped_column(String(160), index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    nominal_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    effective_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    withdrawal_terms: Mapped[str | None] = mapped_column(Text, nullable=True)


class EconomicIndicator(Base, ProvenanceMixin):
    __tablename__ = "economic_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_name: Mapped[str] = mapped_column(String(120), index=True)
    period_label: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class InvestorProfileRecord(Base):
    __tablename__ = "investor_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investor_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("investor_profiles.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ruleset_version: Mapped[str] = mapped_column(String(40))
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class RecommendationAllocation(Base):
    __tablename__ = "recommendation_allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_run_id: Mapped[int] = mapped_column(ForeignKey("recommendation_runs.id"))
    category: Mapped[str] = mapped_column(String(50))
    percent: Mapped[int] = mapped_column(Integer)
    amount_toman: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    reason: Mapped[str] = mapped_column(Text)


class StrategyDefinition(Base, TimestampMixin):
    __tablename__ = "strategy_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(30))
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    research_only: Mapped[bool] = mapped_column(Boolean, default=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64))
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class BacktestMetric(Base):
    __tablename__ = "backtest_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)


class MarketIndex(Base, TimestampMixin):
    __tablename__ = "market_indices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name_fa: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketIndexHistory(Base, ProvenanceMixin):
    __tablename__ = "market_index_history"
    __table_args__ = (UniqueConstraint("market_index_id", "valid_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_index_id: Mapped[int] = mapped_column(ForeignKey("market_indices.id"), index=True)
    open_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    high_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    low_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    close_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    change_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    change_percent: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    raw_hash: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MarketInstrument(Base, TimestampMixin):
    __tablename__ = "market_instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stable_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    name_fa: Mapped[str] = mapped_column(String(200))
    instrument_type: Mapped[str] = mapped_column(String(40), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)


class InstrumentMarketHistory(Base, ProvenanceMixin):
    __tablename__ = "instrument_market_history"
    __table_args__ = (UniqueConstraint("instrument_id", "valid_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), index=True)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)
    trade_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 4), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    market_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_hash: Mapped[str] = mapped_column(String(64))


class FundInstrumentMapping(Base, TimestampMixin):
    __tablename__ = "fund_instrument_mappings"
    __table_args__ = (UniqueConstraint("fund_id", "instrument_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("market_instruments.id"), index=True)
    match_status: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class InflationSeries(Base, TimestampMixin):
    __tablename__ = "inflation_series"
    __table_args__ = (UniqueConstraint("indicator_code", "base_year"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_code: Mapped[str] = mapped_column(String(80), index=True)
    indicator_name: Mapped[str] = mapped_column(String(200))
    base_year: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)


class InflationObservation(Base, ProvenanceMixin):
    __tablename__ = "inflation_observations"
    __table_args__ = (UniqueConstraint("series_id", "period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("inflation_series.id"), index=True)
    period: Mapped[str] = mapped_column(String(40), index=True)
    period_type: Mapped[str] = mapped_column(String(20))
    monthly_inflation: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    point_to_point_inflation: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    annual_inflation: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    consumer_price_index: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    publication_date: Mapped[date] = mapped_column(Date)
    raw_hash: Mapped[str] = mapped_column(String(64))


class BankProductVersion(Base, ProvenanceMixin):
    __tablename__ = "bank_product_versions"
    __table_args__ = (UniqueConstraint("bank_product_id", "valid_from"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_product_id: Mapped[int] = mapped_column(ForeignKey("bank_products.id"), index=True)
    product_type: Mapped[str] = mapped_column(String(60))
    nominal_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    effective_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    minimum_deposit_toman: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    early_withdrawal_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    payment_frequency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    conditions_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(500))
    publication_date: Mapped[date] = mapped_column(Date)
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), index=True)
    raw_hash: Mapped[str] = mapped_column(String(64))


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    dataset: Mapped[str] = mapped_column(String(80), index=True)
    record_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PortfolioRebalancePlan(Base):
    __tablename__ = "portfolio_rebalance_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    method: Mapped[str] = mapped_column(String(40))
    threshold_points: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class ProviderHealthEvent(Base):
    __tablename__ = "provider_health_events"
    __table_args__ = (Index("ix_provider_health_provider_observed", "provider", "observed_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sanitized_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FundFieldProvenance(Base):
    __tablename__ = "fund_field_provenance"
    __table_args__ = (UniqueConstraint("fund_id", "field_name", "observed_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    value_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FundDataConflict(Base):
    __tablename__ = "fund_data_conflicts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80), index=True)
    primary_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    secondary_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    difference_percent: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BackfillRun(Base):
    __tablename__ = "backfill_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), index=True, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    funds_completed: Mapped[int] = mapped_column(Integer, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class BackfillCheckpoint(Base):
    __tablename__ = "backfill_checkpoints"
    __table_args__ = (UniqueConstraint("run_id", "fund_external_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    fund_external_id: Mapped[str] = mapped_column(String(80), index=True)
    last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
