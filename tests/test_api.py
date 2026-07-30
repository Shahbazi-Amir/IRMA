from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from irma.persistence.models import (
    DataSource,
    Fund,
    FundDataConflict,
    FundFieldProvenance,
)


def recommendation_payload() -> dict[str, object]:
    return {
        "capital_toman": 1_000_000,
        "monthly_contribution_toman": 0,
        "horizon": "one_to_three_years",
        "risk_tolerance": "moderate",
        "max_drawdown_tolerance": 0.2,
        "needs_monthly_income": False,
        "liquidity_need": "medium",
        "experience": "beginner",
        "trading_experience": "none",
        "investment_style": "balanced",
        "wants_trading": False,
        "max_trading_percent": 0,
        "has_emergency_fund": False,
        "goal": "growth",
        "current_assets": [],
    }


def test_health_and_info(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    info = client.get("/v1/info").json()
    assert info["version"] == "1.0.0"
    assert info["trade_execution"] is False


def test_recommendation_endpoint(client: TestClient) -> None:
    response = client.post("/v1/recommendations", json=recommendation_payload())
    assert response.status_code == 200
    body = response.json()
    assert sum(item["percent"] for item in body["allocations"]) == 100
    assert body["experimental"] is True


def test_recommendation_rejects_low_capital(client: TestClient) -> None:
    payload = recommendation_payload()
    payload["capital_toman"] = 999_999
    assert client.post("/v1/recommendations", json=payload).status_code == 422


def test_compound_endpoint(client: TestClient) -> None:
    response = client.post(
        "/v1/compound-interest",
        json={
            "principal_toman": 1_000_000,
            "monthly_contribution_toman": 100_000,
            "annual_rate": 0.2,
            "annual_inflation": 0.4,
            "months": 12,
            "compounding": "monthly",
        },
    )
    assert response.status_code == 200
    assert "assumption" in response.json()["assumption_notice"].lower()


def test_empty_funds_are_explicit(client: TestClient) -> None:
    body = client.get("/v1/funds").json()
    assert body["items"] == []
    assert "synthetic" in body["data_notice"]


def test_data_status_lists_unavailable_adapters(client: TestClient) -> None:
    body = client.get("/v1/data-sources/status").json()
    assert body["database_sources"] == []
    assert any(item["name"] == "real-estate" for item in body["unavailable_adapters"])


def test_fund_provider_status_and_sanitized_diagnostics(client: TestClient) -> None:
    status = client.get("/v1/providers/funds/status")
    assert status.status_code == 200
    assert status.json()["contract"] == "auto"
    diagnostics = client.get("/v1/providers/funds/diagnostics")
    assert diagnostics.status_code == 200
    assert diagnostics.json()["items"] == []
    assert "tokens" in diagnostics.json()["notice"].lower()


def test_missing_fund_eligibility_and_provenance_are_404(client: TestClient) -> None:
    assert client.get("/v1/funds/999/eligibility").status_code == 404
    assert client.get("/v1/funds/999/provenance").status_code == 404


def test_fund_eligibility_reason_and_provenance(client: TestClient, session: Session) -> None:
    source = DataSource(
        name="official-file",
        source_identifier="official:file",
        source_type="official_file",
    )
    session.add(source)
    session.flush()
    fund = Fund(
        external_id="REG-1",
        name_fa="صندوق رسمی",
        fund_type="fixed_income",
        source_id=source.id,
        quality_status="valid",
    )
    session.add(fund)
    session.flush()
    session.add(
        FundFieldProvenance(
            fund_id=fund.id,
            field_name="nav",
            source_id=source.id,
            value_hash="a" * 64,
        )
    )
    session.add(
        FundDataConflict(
            fund_id=fund.id,
            field_name="nav",
            primary_source_id=source.id,
            secondary_source_id=source.id,
            difference_percent=0.5,
            severity="warning",
        )
    )
    session.commit()
    eligibility = client.get(f"/v1/funds/{fund.id}/eligibility").json()
    assert eligibility["eligible"] is False
    assert eligibility["reason"] == "insufficient_history"
    provenance = client.get(f"/v1/funds/{fund.id}/provenance").json()
    assert provenance["fields"][0]["field"] == "nav"
    assert provenance["conflicts"][0]["difference_percent"] == 0.5


def test_admin_refresh_is_disabled_without_key(client: TestClient) -> None:
    response = client.post("/v1/admin/data-refresh")
    assert response.status_code == 503


def test_backtest_endpoints(client: TestClient) -> None:
    start = date(2025, 1, 1)
    bars = [
        {
            "date": str(start + timedelta(days=index)),
            "close": 100 + index,
            "volume": 100000,
            "trade_value": 10000000,
            "spread_percent": 0.001,
            "tradable": True,
        }
        for index in range(30)
    ]
    response = client.post(
        "/v1/backtests",
        json={"strategy": "moving_average", "bars": bars, "fast_window": 3, "slow_window": 10},
    )
    assert response.status_code == 200
    backtest_id = response.json()["backtest_id"]
    detail = client.get(f"/v1/backtests/{backtest_id}")
    assert detail.status_code == 200
    assert detail.json()["strategy"] == "moving_average"
