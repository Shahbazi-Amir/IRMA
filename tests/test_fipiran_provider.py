import json
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session

from irma.providers.fipiran import FipiranFundProvider
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
