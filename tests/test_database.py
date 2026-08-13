from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from irma.persistence.models import Base, DataSource
from irma.persistence.repositories import data_source_status


def test_all_required_tables_exist(session: Session) -> None:
    names = set(inspect(session.get_bind()).get_table_names())
    required = {
        "data_sources",
        "data_ingestion_runs",
        "assets",
        "asset_prices",
        "funds",
        "fund_nav_history",
        "fund_market_history",
        "fund_metrics",
        "bank_products",
        "economic_indicators",
        "investor_profiles",
        "recommendation_runs",
        "recommendation_allocations",
        "strategy_definitions",
        "backtest_runs",
        "backtest_metrics",
        "market_indices",
        "market_index_history",
        "market_instruments",
        "instrument_market_history",
        "fund_instrument_mappings",
        "inflation_series",
        "inflation_observations",
        "bank_product_versions",
        "data_quality_events",
        "portfolio_rebalance_plans",
        "provider_health_events",
        "fund_field_provenance",
        "fund_data_conflicts",
        "backfill_runs",
        "backfill_checkpoints",
        "refresh_controls",
        "refresh_telemetry",
        "historical_series",
        "historical_observations",
    }
    assert required <= names
    assert required == set(Base.metadata.tables)


def test_stale_source_is_labeled(session: Session) -> None:
    source = DataSource(
        name="old",
        source_identifier="test",
        source_type="manual",
        status="valid",
    )
    session.add(source)
    session.commit()
    assert data_source_status(session)[0]["status"] == "valid"


def test_sqlite_naive_source_timestamp_is_safely_labeled_stale(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'status.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(
            DataSource(
                name="fipiran",
                source_identifier="https://www.fipiran.com",
                source_type="api",
                status="valid",
                last_valid_observation_at=datetime.now(UTC) - timedelta(days=3),
            )
        )
        session.commit()
    with factory() as session:
        stored = session.scalar(select(DataSource))
        assert stored is not None
        assert stored.last_valid_observation_at is not None
        assert stored.last_valid_observation_at.tzinfo is None
        assert data_source_status(session)[0]["status"] == "stale"
    engine.dispose()
