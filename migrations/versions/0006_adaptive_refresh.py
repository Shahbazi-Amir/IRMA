"""adaptive refresh telemetry and control

Revision ID: 0006_adaptive_refresh
Revises: 0005_fipiran_catalogue_identity
"""

from collections.abc import Sequence

from alembic import op

from irma.persistence.models import RefreshControl, RefreshTelemetry

revision: str = "0006_adaptive_refresh"
down_revision: str | None = "0005_fipiran_catalogue_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    RefreshTelemetry.__table__.create(bind, checkfirst=True)
    RefreshControl.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    RefreshControl.__table__.drop(bind, checkfirst=True)
    RefreshTelemetry.__table__.drop(bind, checkfirst=True)
