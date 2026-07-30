from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from irma.domain.profile import InvestorProfile
from irma.persistence.models import DataSource, Fund, FundMetric, FundNavHistory
from irma.services.recommendations import create_recommendation


def test_small_capital_uses_at_most_one_ranked_instrument(session: Session) -> None:
    now = datetime.now(UTC)
    source = DataSource(
        name="fipiran",
        source_identifier="official",
        source_type="api",
        status="valid",
        unit="IRR",
        last_valid_observation_at=now,
    )
    session.add(source)
    session.flush()
    fund = Fund(
        external_id="1",
        name_fa="صندوق آزمون",
        fund_type="fixed_income",
        is_active=True,
        source_id=source.id,
        quality_status="valid",
        last_data_at=now,
    )
    session.add(fund)
    session.flush()
    start = date.today() - timedelta(days=120)
    for index in range(120):
        session.add(
            FundNavHistory(
                fund_id=fund.id,
                nav=Decimal(1000 + index),
                source_id=source.id,
                observed_at=now - timedelta(days=119 - index),
                valid_at=start + timedelta(days=index),
                quality_status="valid",
            )
        )
    for name, value in {
        "cagr": 0.3,
        "sharpe": 1.1,
        "maximum_drawdown": -0.08,
        "positive_period_ratio": 0.7,
        "data_quality_score": 0.9,
    }.items():
        session.add(
            FundMetric(
                fund_id=fund.id,
                metric_name=name,
                value=Decimal(str(value)),
                source_id=source.id,
                observed_at=now,
                valid_at=date.today(),
                quality_status="valid",
            )
        )
    session.commit()
    profile = InvestorProfile(
        capital_toman=1_000_000,
        horizon="one_to_three_years",
        risk_tolerance="conservative",
        max_drawdown_tolerance=0.1,
        liquidity_need="medium",
        experience="beginner",
        trading_experience="none",
        investment_style="passive",
        goal="حفظ سرمایه",
    )
    result = create_recommendation(profile, session=session)
    fixed_income = next(item for item in result.allocations if item.category == "fixed_income")
    assert len(fixed_income.instruments) == 1
    assert result.data_used[0].source == "fipiran"
