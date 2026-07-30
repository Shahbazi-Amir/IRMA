"""add multi-asset market data

Revision ID: 0003_multi_asset_market_data
Revises: 0002_fund_identity
"""

from collections.abc import Sequence

from alembic import op

from irma.persistence.models import (
    BankProductVersion,
    DataQualityEvent,
    FundInstrumentMapping,
    InflationObservation,
    InflationSeries,
    InstrumentMarketHistory,
    MarketIndex,
    MarketIndexHistory,
    MarketInstrument,
    PortfolioRebalancePlan,
)

revision: str = "0003_multi_asset_market_data"
down_revision: str | None = "0002_fund_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    MarketIndex,
    MarketIndexHistory,
    MarketInstrument,
    InstrumentMarketHistory,
    FundInstrumentMapping,
    InflationSeries,
    InflationObservation,
    BankProductVersion,
    DataQualityEvent,
    PortfolioRebalancePlan,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=True)
