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
