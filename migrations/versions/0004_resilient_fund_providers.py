"""resilient fund provider state

Revision ID: 0004_resilient_fund_providers
Revises: 0003_multi_asset_market_data
"""

from collections.abc import Sequence

from alembic import op

from irma.persistence.models import (
    BackfillCheckpoint,
    BackfillRun,
    FundDataConflict,
    FundFieldProvenance,
    ProviderHealthEvent,
)

revision: str = "0004_resilient_fund_providers"
down_revision: str | None = "0003_multi_asset_market_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    ProviderHealthEvent,
    FundFieldProvenance,
    FundDataConflict,
    BackfillRun,
    BackfillCheckpoint,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=True)
