"""Allow duplicate fund symbols for composite FIPIRAN identities.

Revision ID: 0005_fipiran_catalogue_identity
Revises: 0004_resilient_fund_providers
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_fipiran_catalogue_identity"
down_revision: str | None = "0004_resilient_fund_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("funds")
        if constraint.get("name") and constraint.get("column_names") == ["symbol"]
    }
    with op.batch_alter_table("funds") as batch:
        for name in unique_names:
            batch.drop_constraint(name, type_="unique")
        symbol_index = next(
            (
                index
                for index in inspector.get_indexes("funds")
                if index.get("column_names") == ["symbol"]
            ),
            None,
        )
        if symbol_index and symbol_index.get("unique"):
            batch.drop_index(symbol_index["name"])
            batch.create_index("ix_funds_symbol", ["symbol"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("funds") as batch:
        batch.drop_index("ix_funds_symbol")
        batch.create_index("ix_funds_symbol", ["symbol"], unique=True)
