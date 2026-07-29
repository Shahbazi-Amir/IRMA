from fastapi.testclient import TestClient

from irma.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "irma"}


def test_info_endpoint_states_mvp_boundaries() -> None:
    response = client.get("/v1/info")

    assert response.status_code == 200
    assert response.json() == {
        "version": "0.1.0",
        "stage": "experimental-mvp",
        "live_market_data": False,
        "trade_execution": False,
        "price_prediction": False,
    }


def test_recommendation_endpoint() -> None:
    response = client.post(
        "/v1/recommendations",
        json={
            "capital_toman": 1_000_000,
            "monthly_contribution_toman": 100_000,
            "horizon_months": 24,
            "risk_tolerance": "moderate",
            "max_drawdown_tolerance": 0.2,
            "needs_monthly_income": False,
            "liquidity_need": "medium",
            "wants_trading": False,
            "experience": "beginner",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["experimental"] is True
    assert sum(payload["allocations_percent"].values()) == 100
    assert "guaranteed return" in payload["disclaimer"]


def test_recommendation_rejects_low_capital() -> None:
    response = client.post(
        "/v1/recommendations",
        json={
            "capital_toman": 999_999,
            "monthly_contribution_toman": 0,
            "horizon_months": 12,
            "risk_tolerance": "conservative",
            "max_drawdown_tolerance": 0.1,
            "needs_monthly_income": False,
            "liquidity_need": "high",
            "wants_trading": False,
            "experience": "none",
        },
    )

    assert response.status_code == 422
