"""Classification helpers for live source validation."""

from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from irma.providers.fipiran import ProviderBlockedError, ProviderContractError


def classify_failure(exc: Exception) -> str:
    """Keep local schema and validation failures distinct from source outages."""
    if isinstance(exc, CommandError):
        return "migration_error"
    if isinstance(exc, SQLAlchemyError):
        return "database_error"
    if isinstance(exc, (ProviderBlockedError, ProviderContractError, OSError)):
        return "source_unavailable"
    return "validation_error"
