import json
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.persistence.models import Fund, FundNavHistory
from irma.providers.fipiran import (
    CircuitOpenError,
    FipiranFundProvider,
    HistoryIdentityError,
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
                    "groupId": 1,
                    "insCode": "IRTEST11215",
                    "name": "توسعه اطلس مفید",
                    "fundType": 23,
                    "date": "2026-07-29T00:00:00",
                    "initiationDate": "2014-12-23T00:00:00",
                    "smallSymbolName": "اطلس",
                    "typeOfInvest": "Negotiable",
                    "cancelNav": 999 + MIN_OBSERVATIONS + 29,
                    "statisticalNav": 999 + MIN_OBSERVATIONS + 29,
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
    assert record.external_id == "fipiran:11215:1"
    assert record.fund_type == "index"
    assert record.is_etf is True
    history = provider.fetch_nav_history(record.external_id)
    assert len(history) == MIN_OBSERVATIONS + 30
    assert history[0].nav == 999


def test_fipiran_provider_deduplicates_identical_identity() -> None:
    payload = json.loads(_catalogue())
    payload["items"].append(payload["items"][0].copy())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    provider = FipiranFundProvider(
        base_url="https://fixture.test/services",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )

    assert len(provider.fetch()) == 1


def test_fipiran_provider_rejects_conflicting_duplicate_identity() -> None:
    payload = json.loads(_catalogue())
    duplicate = payload["items"][0].copy()
    duplicate["name"] = "صندوق دیگر"
    payload["items"].append(duplicate)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    provider = FipiranFundProvider(
        base_url="https://fixture.test/services",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )

    with pytest.raises(ProviderContractError, match="conflicting duplicate"):
        provider.fetch()


def _multi_group_catalogue(*, include_primary: bool = True) -> bytes:
    items = [
        {
            "regNo": "12181",
            "groupId": 2,
            "insCode": "INS-G2",
            "name": "متال فرعی",
            "fundType": 5,
            "date": "2026-07-29T00:00:00",
            "smallSymbolName": "متال",
            "typeOfInvest": "Negotiable",
            "cancelNav": 27167,
            "statisticalNav": 27663,
            "netAsset": 200,
            "isCompleted": True,
        },
        {
            "regNo": "12181",
            "groupId": 3,
            "insCode": "INS-G3",
            "name": "سیمانا",
            "fundType": 5,
            "date": "2026-07-29T00:00:00",
            "smallSymbolName": "سیمانا",
            "typeOfInvest": "Negotiable",
            "cancelNav": 32446,
            "statisticalNav": 32446,
            "netAsset": 300,
            "isCompleted": True,
        },
        {
            "regNo": "12181",
            "groupId": 4,
            "insCode": None,
            "name": "مزه",
            "fundType": 5,
            "date": "2026-07-29T00:00:00",
            "smallSymbolName": "مزه",
            "typeOfInvest": "Negotiable",
            "cancelNav": 24643,
            "statisticalNav": 24643,
            "netAsset": 400,
            "isCompleted": True,
        },
    ]
    if include_primary:
        items.insert(
            0,
            {
                "regNo": "12181",
                "groupId": 1,
                "insCode": "INS-G1",
                "name": "متال اصلی",
                "fundType": 5,
                "date": "2026-07-28T00:00:00",
                "smallSymbolName": "متال",
                "typeOfInvest": "Negotiable",
                "cancelNav": 27104,
                "statisticalNav": 27196,
                "netAsset": 100,
                "isCompleted": True,
            },
        )
    return json.dumps({"status": 200, "items": items}).encode()


def _12181_history() -> bytes:
    return json.dumps(
        [
            {
                "date": "2026-07-29T00:00:00",
                "cancelNav": 27104,
                "statisticalNav": 27196,
            }
        ]
    ).encode()


def test_catalogue_preserves_real_12181_groups_and_duplicate_symbol() -> None:
    provider = FipiranFundProvider(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=_multi_group_catalogue())
            )
        ),
        min_interval_seconds=0,
    )
    records = provider.fetch()
    assert [record.external_id for record in records] == [
        "fipiran:12181:1",
        "fipiran:12181:2",
        "fipiran:12181:3",
        "fipiran:12181:4",
    ]
    assert [record.symbol for record in records].count("متال") == 2
    assert len({record.name_fa for record in records}) == 4


def test_history_is_attached_only_to_uniquely_matching_group() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_multi_group_catalogue() if request.method == "POST" else _12181_history(),
            request=request,
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    provider.fetch()
    assert provider.fetch_nav_history("fipiran:12181:1")[0].nav == 27104
    for group_id in (2, 3, 4):
        with pytest.raises(HistoryIdentityError, match="does not uniquely match"):
            provider.fetch_nav_history(f"fipiran:12181:{group_id}")


def test_history_is_not_guessed_when_primary_group_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_multi_group_catalogue(include_primary=False)
            if request.method == "POST"
            else _12181_history(),
            request=request,
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    records = provider.fetch()
    assert len(records) == 3
    with pytest.raises(HistoryIdentityError, match=r"matches=\[\]"):
        provider.fetch_nav_history(records[0].external_id)


def test_more_than_one_nonidentical_primary_identity_is_rejected() -> None:
    payload = json.loads(_multi_group_catalogue())
    duplicate = payload["items"][0].copy()
    duplicate["insCode"] = "OTHER-PRIMARY"
    payload["items"].append(duplicate)
    provider = FipiranFundProvider(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload, request=request)
            )
        ),
        min_interval_seconds=0,
    )
    with pytest.raises(ProviderContractError, match="groupId=1"):
        provider.fetch()


def test_realistic_12407_groups_are_not_signature_merged() -> None:
    payload = json.loads(_multi_group_catalogue())
    payload["items"] = payload["items"][:2]
    for item in payload["items"]:
        item["regNo"] = "12407"
    provider = FipiranFundProvider(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload, request=request)
            )
        ),
        min_interval_seconds=0,
    )
    records = provider.fetch()
    assert {record.external_id for record in records} == {
        "fipiran:12407:1",
        "fipiran:12407:2",
    }


def test_duplicate_symbols_and_multigroup_bootstrap_are_idempotent(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_multi_group_catalogue() if request.method == "POST" else _12181_history(),
            request=request,
        )

    provider = FipiranFundProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )
    coordinator = RefreshCoordinator(max_retries=0)
    first = coordinator.refresh_funds(session, provider, history_limit=None)
    second = coordinator.refresh_funds(session, provider, history_limit=None)
    assert first["records_written"] == second["records_written"] == 4
    assert session.scalar(select(func.count(Fund.id))) == 4
    assert session.scalar(select(func.count(FundNavHistory.id))) == 5
    assert len(first["history_errors"]) == 3
    assert len(second["history_errors"]) == 3


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
