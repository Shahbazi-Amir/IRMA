"""Add stable provider identity and fund status fields.

Revision ID: 0002_fund_identity
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_fund_identity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("funds")}
    indexes = {index["name"] for index in inspector.get_indexes("funds")}
    with op.batch_alter_table("funds") as batch:
        if "external_id" not in columns:
            batch.add_column(sa.Column("external_id", sa.String(length=80), nullable=True))
        if "is_active" not in columns:
            batch.add_column(
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
            )
        if "asset_allocation_json" not in columns:
            batch.add_column(
                sa.Column("asset_allocation_json", sa.JSON(), nullable=False, server_default="{}")
            )
        if "ix_funds_external_id" not in indexes:
            batch.create_index("ix_funds_external_id", ["external_id"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("funds")}
    indexes = {index["name"] for index in inspector.get_indexes("funds")}
    with op.batch_alter_table("funds") as batch:
        if "ix_funds_external_id" in indexes:
            batch.drop_index("ix_funds_external_id")
        if "asset_allocation_json" in columns:
            batch.drop_column("asset_allocation_json")
        if "is_active" in columns:
            batch.drop_column("is_active")
        if "external_id" in columns:
            batch.drop_column("external_id")
