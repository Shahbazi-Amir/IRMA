from pathlib import Path

from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError

from irma.persistence.migrations import upgrade_database
from irma.providers.fipiran import ProviderBlockedError
from irma.services.live_validation import classify_failure


def test_upgrade_database_prepares_a_fresh_sqlite_database(tmp_path: Path) -> None:
    database = tmp_path / "fresh-live-validation.db"
    database_url = f"sqlite:///{database}"

    upgrade_database(database_url)

    inspector = inspect(create_engine(database_url))
    assert "data_ingestion_runs" in inspector.get_table_names()
    assert "alembic_version" in inspector.get_table_names()


def test_live_validation_failure_classification_is_specific() -> None:
    assert classify_failure(CommandError("broken revision")) == "migration_error"
    assert classify_failure(OperationalError("select", {}, Exception("missing table"))) == (
        "database_error"
    )
    assert classify_failure(ProviderBlockedError("gateway")) == "source_unavailable"
    assert classify_failure(ValueError("invalid acceptance result")) == "validation_error"
