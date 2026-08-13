"""canonical historical intelligence series

Revision ID: 0007_historical_intelligence
Revises: 0006_adaptive_refresh
"""

from collections.abc import Sequence

from alembic import op

from irma.persistence.models import HistoricalObservation, HistoricalSeries

revision: str = "0007_historical_intelligence"
down_revision: str | None = "0006_adaptive_refresh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    HistoricalSeries.__table__.create(bind, checkfirst=True)
    HistoricalObservation.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    HistoricalObservation.__table__.drop(bind, checkfirst=True)
    HistoricalSeries.__table__.drop(bind, checkfirst=True)
