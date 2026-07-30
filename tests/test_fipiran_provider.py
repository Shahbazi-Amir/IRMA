import json
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session

from irma.providers.fipiran import (
    CircuitOpenError,
    FipiranFundProvider,
    ProviderBlockedError,
    ProviderContractError,
)
from irma.services.data_refresh import RefreshCoordinator
from irma.services.fund_rankings import MIN_OBSERVATIONS, rank_funds


def _catalogue() -> bytes:
    return json.dumps(
        {
            "status": 200,
            "items": [
                {
                    "regNo": "11215",
                    "name": "توسعه اطلس مفید",
                    "fundType": 23,
                    "date": "2026-07-29T00:00:00",
                    "initiationDate": "2014-12-23T00:00:00",
                    "smallSymbolName": "اطلس",
                    "typeOfInvest": "Negotiable",
                    "cancelNav": 63875,
                    "statisticalNav": 63875,
                    "netAsset": 42529338176194,
                    "manager": "سبدگردان مفید",
                    "isCompleted": True,
                    "stock": 93.63,
                    "bond": 0,
                    "cash": 0,
                    "deposit": 2.84,
                    "commodity": None,
                }
            ],
        }
    ).encode()


def _history() -> bytes:
    start = date(2026, 4, 1)
    return json.dumps(
        [
            {
                "date": (start + timedelta(days=index)).isoformat() + "T00:00:00",
                "issueNav": 1000 + index,
                "cancelNav": 999 + index,
                "statisticalNav": 999 + index,
            }
            for index in range(MIN_OBSERVATIONS + 30)
        ]
    ).encode()


def test_fipiran_provider_parses_catalogue_and_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = _catalogue() if request.method == "POST" else _history()
        return httpx.Response(200, content=content, request=request)

    provider = FipiranFundProvider(
        base_url="https://fixture.test/services",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    record = provider.fetch()[0]
    assert record.external_id == "11215"
    assert record.fund_type == "index"
    assert record.is_etf is True
    history = provider.fetch_nav_history(record.external_id)
    assert len(history) == MIN_OBSERVATIONS + 30
    assert history[0].nav == 999


def test_fipiran_provider_rejects_duplicate_identity() -> None:
    payload = json.loads(_catalogue())
    payload["items"].append(payload["items"][0])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    provider = FipiranFundProvider(
        base_url="https://fixture.test/services",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    with pytest.raises(ValueError, match="duplicate"):
        provider.fetch()


def test_refresh_is_idempotent_and_produces_ranking(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_catalogue() if request.method == "POST" else _history(),
            request=request,
        )

    provider = FipiranFundProvider(
        base_url="https://fixture.test/services",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    coordinator = RefreshCoordinator(max_retries=0)
    first = coordinator.refresh_funds(session, provider, history_limit=1)
    second = coordinator.refresh_funds(session, provider, history_limit=1)
    assert first["history_written"] == MIN_OBSERVATIONS + 30
    assert second["history_written"] == 0
    ranking = rank_funds(session, "index")
    assert ranking["eligible_count"] == 1
    assert ranking["items"][0]["ranking_version"]


def test_provider_reuses_session_and_records_success() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, content=_catalogue(), headers={"content-type": "application/json"}, request=request
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FipiranFundProvider(client=client, min_interval_seconds=0, retries=0)
    provider.fetch()
    provider.fetch()
    assert calls == 2
    assert provider.status()["circuit"] == "closed"
    assert provider.status()["last_success_at"] is not None


def test_provider_context_manager_preserves_injected_client() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    with FipiranFundProvider(client=client) as provider:
        assert provider.client is client
    assert client.is_closed is False
    client.close()


@pytest.mark.parametrize(
    ("content_type", "body", "error"),
    [
        ("text/html", b"<html>gateway error</html>", ProviderBlockedError),
        ("text/html", b"<html>captcha challenge</html>", ProviderBlockedError),
        ("text/plain", b"not json", ProviderContractError),
    ],
)
def test_provider_rejects_non_json_boundaries(
    content_type: str, body: bytes, error: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": content_type}, request=request
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
        retries=0,
    )
    with pytest.raises(error):
        provider.fetch()


def test_circuit_opens_and_half_open_recovers() -> None:
    responses = [503, 503, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        status_code = responses.pop(0)
        return httpx.Response(
            status_code,
            content=_catalogue() if status_code == 200 else b"{}",
            headers={"content-type": "application/json"},
            request=request,
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
        retries=0,
        failure_threshold=2,
        cooldown_seconds=0,
    )
    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch()
    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch()
    assert provider.status()["circuit"] == "open"
    assert provider.fetch()
    assert provider.status()["circuit"] == "closed"


def test_open_circuit_rejects_request_during_cooldown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, content=b"{}", headers={"content-type": "application/json"}, request=request
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
        retries=0,
        failure_threshold=1,
        cooldown_seconds=60,
    )
    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch()
    with pytest.raises(CircuitOpenError):
        provider.fetch()
