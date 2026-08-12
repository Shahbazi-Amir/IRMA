"""Database migration entry point shared by operational scripts."""

from alembic import command
from alembic.config import Config


def upgrade_database(database_url: str) -> None:
    """Upgrade the configured database to the current schema."""
    alembic_config = Config("alembic.ini")
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")
