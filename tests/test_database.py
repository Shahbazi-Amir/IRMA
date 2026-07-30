from sqlalchemy import inspect
from sqlalchemy.orm import Session

from irma.persistence.models import Base, DataSource
from irma.persistence.repositories import data_source_status


def test_all_required_tables_exist(session: Session) -> None:
    names = set(inspect(session.get_bind()).get_table_names())
    required = {
        "data_sources", "data_ingestion_runs", "assets", "asset_prices", "funds",
        "fund_nav_history", "fund_market_history", "fund_metrics", "bank_products",
        "economic_indicators", "investor_profiles", "recommendation_runs",
        "recommendation_allocations", "strategy_definitions", "backtest_runs", "backtest_metrics",
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
