from irma.config import Settings


def test_fixture_data_is_forbidden_in_production() -> None:
    assert Settings(app_env="production", fixture_data_enabled=True).fixtures_allowed() is False
    assert Settings(app_env="e2e", fixture_data_enabled=True).fixtures_allowed() is True


def test_operational_endpoints_and_headers(client) -> None:  # type: ignore[no-untyped-def]
    ready = client.get("/ready", headers={"X-Request-ID": "test-request"})
    assert ready.status_code == 200
    assert ready.headers["X-Request-ID"] == "test-request"
    assert ready.headers["X-Content-Type-Options"] == "nosniff"
    assert ready.headers["X-Frame-Options"] == "DENY"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json() == {
        "ingestion_success_total": 0,
        "ingestion_failure_total": 0,
        "stale_records_total": 0,
        "recommendations_total": 0,
        "recommendations_with_warnings_total": 0,
        "records_rejected_total": 0,
    }
