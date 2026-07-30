"""Idempotent persistence for validated multi-asset CSV adapters."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import (
    BankProduct,
    BankProductVersion,
    DataSource,
    InflationObservation,
    InflationSeries,
    InstrumentMarketHistory,
    MarketIndex,
    MarketIndexHistory,
    MarketInstrument,
)
from irma.providers.base import ProviderMetadata
from irma.providers.multi_asset_csv import (
    CsvBankProductProvider,
    CsvInflationProvider,
    CsvInstrumentMarketProvider,
    CsvMarketIndexProvider,
)


def _decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _source(session: Session, metadata: ProviderMetadata, source_type: str) -> DataSource:
    source = session.scalar(select(DataSource).where(DataSource.name == metadata.source_name))
    if source is None:
        source = DataSource(
            name=metadata.source_name,
            source_identifier=metadata.source_identifier,
            source_type=source_type,
            unit=metadata.unit,
        )
        session.add(source)
        session.flush()
    source.status = metadata.quality.value
    source.last_fetched_at = metadata.fetched_at
    source.last_valid_observation_at = metadata.observed_at
    source.last_error = None
    source.data_version = metadata.data_version
    source.raw_hash = metadata.raw_hash
    return source


def refresh_market_indices(session: Session, path: str | Path) -> dict[str, int | str]:
    records = CsvMarketIndexProvider(path).fetch()
    written = 0
    for record in records:
        source = _source(session, record.metadata, "official_csv")
        index = session.scalar(
            select(MarketIndex).where(MarketIndex.index_code == record.index_code)
        )
        if index is None:
            index = MarketIndex(index_code=record.index_code, name_fa=record.name_fa)
            session.add(index)
        index.name_fa = record.name_fa
        index.name_en = record.name_en
        index.source_id = source.id
        session.flush()
        existing = session.scalar(
            select(MarketIndexHistory.id).where(
                MarketIndexHistory.market_index_id == index.id,
                MarketIndexHistory.valid_at == record.observation_date.date(),
            )
        )
        if existing is None:
            session.add(
                MarketIndexHistory(
                    market_index_id=index.id,
                    open_value=_decimal(record.open_value),
                    high_value=_decimal(record.high_value),
                    low_value=_decimal(record.low_value),
                    close_value=_decimal(record.close_value),
                    change_value=_decimal(record.change_value),
                    change_percent=_decimal(record.change_percent),
                    source_id=source.id,
                    observed_at=record.observation_date,
                    valid_at=record.observation_date.date(),
                    currency="INDEX_POINT",
                    quality_status=record.metadata.quality.value,
                    raw_hash=record.metadata.raw_hash or "",
                    data_version=record.metadata.data_version,
                )
            )
            written += 1
        source.record_count += 1
    session.commit()
    return {"dataset": "market_indices", "received": len(records), "written": written}


def refresh_market_instruments(session: Session, path: str | Path) -> dict[str, int | str]:
    records = CsvInstrumentMarketProvider(path).fetch()
    written = 0
    for record in records:
        source = _source(session, record.metadata, "official_csv")
        instrument = session.scalar(
            select(MarketInstrument).where(MarketInstrument.stable_id == record.stable_id)
        )
        if instrument is None:
            instrument = MarketInstrument(
                stable_id=record.stable_id,
                symbol=record.symbol,
                name_fa=record.name_fa,
                instrument_type=record.instrument_type,
            )
            session.add(instrument)
        instrument.symbol = record.symbol
        instrument.name_fa = record.name_fa
        instrument.instrument_type = record.instrument_type
        instrument.source_id = source.id
        session.flush()
        existing = session.scalar(
            select(InstrumentMarketHistory.id).where(
                InstrumentMarketHistory.instrument_id == instrument.id,
                InstrumentMarketHistory.valid_at == record.observation_date.date(),
            )
        )
        if existing is None:
            session.add(
                InstrumentMarketHistory(
                    instrument_id=instrument.id,
                    open_price=_decimal(record.open_price),
                    high_price=_decimal(record.high_price),
                    low_price=_decimal(record.low_price),
                    close_price=_decimal(record.close_price),
                    last_price=_decimal(record.last_price),
                    volume=_decimal(record.volume),
                    trade_value=_decimal(record.trade_value),
                    trade_count=record.trade_count,
                    best_bid=_decimal(record.best_bid),
                    best_ask=_decimal(record.best_ask),
                    market_status=record.market_status,
                    source_id=source.id,
                    observed_at=record.observation_date,
                    valid_at=record.observation_date.date(),
                    currency=record.metadata.unit or "IRR",
                    quality_status=record.metadata.quality.value,
                    raw_hash=record.metadata.raw_hash or "",
                )
            )
            written += 1
        source.record_count += 1
    session.commit()
    return {"dataset": "market_instruments", "received": len(records), "written": written}


def refresh_inflation(session: Session, path: str | Path) -> dict[str, int | str]:
    records = CsvInflationProvider(path).fetch()
    written = 0
    for record in records:
        source = _source(session, record.metadata, "official_csv")
        series = session.scalar(
            select(InflationSeries).where(
                InflationSeries.indicator_code == record.indicator_code,
                InflationSeries.base_year == record.base_year,
            )
        )
        if series is None:
            series = InflationSeries(
                indicator_code=record.indicator_code,
                indicator_name=record.indicator_name,
                base_year=record.base_year,
                source_id=source.id,
            )
            session.add(series)
            session.flush()
        existing = session.scalar(
            select(InflationObservation.id).where(
                InflationObservation.series_id == series.id,
                InflationObservation.period == record.period,
            )
        )
        if existing is None:
            session.add(
                InflationObservation(
                    series_id=series.id,
                    period=record.period,
                    period_type=record.period_type,
                    monthly_inflation=_decimal(record.monthly_inflation),
                    point_to_point_inflation=_decimal(record.point_to_point_inflation),
                    annual_inflation=_decimal(record.annual_inflation),
                    consumer_price_index=_decimal(record.consumer_price_index),
                    publication_date=date.fromisoformat(record.publication_date),
                    source_id=source.id,
                    observed_at=record.metadata.observed_at or record.metadata.fetched_at,
                    valid_at=None,
                    currency="PERCENT_INDEX",
                    quality_status=record.metadata.quality.value,
                    raw_hash=record.metadata.raw_hash or "",
                )
            )
            written += 1
        source.record_count += 1
    session.commit()
    return {"dataset": "inflation", "received": len(records), "written": written}


def refresh_bank_products(session: Session, path: str | Path) -> dict[str, int | str]:
    records = CsvBankProductProvider(path).fetch()
    written = 0
    for record in records:
        source = _source(session, record.metadata, "verified_csv")
        product = session.scalar(
            select(BankProduct).where(
                BankProduct.bank_name == record.bank_name,
                BankProduct.product_name == record.product_name,
            )
        )
        if product is None:
            product = BankProduct(bank_name=record.bank_name, product_name=record.product_name)
            session.add(product)
            session.flush()
        existing = session.scalar(
            select(BankProductVersion.id).where(
                BankProductVersion.bank_product_id == product.id,
                BankProductVersion.valid_from == date.fromisoformat(record.valid_from),
            )
        )
        if existing is None:
            session.add(
                BankProductVersion(
                    bank_product_id=product.id,
                    product_type=record.product_type,
                    nominal_rate=_decimal(record.nominal_rate),
                    effective_rate=_decimal(record.effective_rate),
                    minimum_deposit_toman=_decimal(record.minimum_deposit_toman),
                    term_months=record.term_months,
                    early_withdrawal_rate=_decimal(record.early_withdrawal_rate),
                    payment_frequency=record.payment_frequency,
                    conditions_summary=record.conditions_summary,
                    source_url=record.source_url,
                    publication_date=date.fromisoformat(record.publication_date),
                    valid_from=date.fromisoformat(record.valid_from),
                    valid_until=date.fromisoformat(record.valid_until)
                    if record.valid_until
                    else None,
                    verification_status=record.verification_status,
                    source_id=source.id,
                    observed_at=record.metadata.observed_at or record.metadata.fetched_at,
                    valid_at=date.fromisoformat(record.valid_from),
                    currency="TOMAN",
                    quality_status=record.metadata.quality.value,
                    raw_hash=record.metadata.raw_hash or "",
                )
            )
            written += 1
        source.record_count += 1
    session.commit()
    return {"dataset": "bank_products", "received": len(records), "written": written}
