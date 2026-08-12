"""FIPIRAN adapter isolated from the domain and validated at its boundary."""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from irma.providers.base import DataQuality, FundNavRecord, FundRecord, ProviderMetadata

FUND_TYPES = {
    4: "fixed_income",
    5: "gold",
    6: "equity",
    7: "mixed",
    21: "equity",
    22: "leveraged",
    23: "index",
}


class _FundItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reg_no: str = Field(alias="regNo")
    group_id: int = Field(alias="groupId")
    ins_code: str | None = Field(default=None, alias="insCode")
    name: str
    fund_type: int = Field(alias="fundType")
    date: datetime
    initiation_date: datetime | None = Field(default=None, alias="initiationDate")
    small_symbol_name: str | None = Field(default=None, alias="smallSymbolName")
    type_of_invest: str | None = Field(default=None, alias="typeOfInvest")
    cancel_nav: float | None = Field(default=None, alias="cancelNav")
    statistical_nav: float | None = Field(default=None, alias="statisticalNav")
    net_asset: float | None = Field(default=None, alias="netAsset")
    manager: str | None = None
    is_completed: bool = Field(default=True, alias="isCompleted")
    stock: float | None = None
    bond: float | None = None
    cash: float | None = None
    deposit: float | None = None
    commodity: float | None = None


class _FundResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: int
    items: list[_FundItem]


class _NavItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: datetime
    cancel_nav: float = Field(alias="cancelNav")
    statistical_nav: float = Field(alias="statisticalNav")


class ProviderBlockedError(ValueError):
    """The upstream returned an HTML block, captcha, or gateway page."""


class ProviderContractError(ValueError):
    """The upstream response no longer matches a validated contract."""


class HistoryIdentityError(ValueError):
    """History cannot be assigned to exactly one catalogue identity."""


class CircuitOpenError(RuntimeError):
    """Requests are paused after repeated recoverable failures."""


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    reason: str | None = None

    @property
    def state(self) -> str:
        return "open" if self.opened_at is not None else "closed"


class FipiranFundProvider:
    """Fetch official fund catalogue and NAV history with bounded network behavior."""

    source_name = "fipiran"

    def __init__(
        self,
        *,
        base_url: str = "https://www.fipiran.com/services",
        timeout_seconds: float = 15,
        min_interval_seconds: float = 0.25,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        catalog_path: str = "fund/fundcompare/",
        history_path: str = "chart/getfundchart",
        user_agent: str = "IRMA/1.0 (+https://github.com/Shahbazi-Amir/IRMA)",
        failure_threshold: int = 3,
        cooldown_seconds: float = 300,
        retries: int = 2,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self.catalog_path = catalog_path
        self.history_path = history_path
        self.user_agent = user_agent
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.retries = retries
        self.random_value = random_value
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10)),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "Referer": "https://www.fipiran.com/",
                "User-Agent": user_agent,
            },
        )
        self._owns_client = client is None
        self.sleep = sleep
        self._last_request_at = 0.0
        self.circuit = CircuitState()
        self._catalogue_by_reg_no: dict[str, list[_FundItem]] = {}

    @staticmethod
    def _external_id(item: _FundItem) -> str:
        return f"fipiran:{item.reg_no}:{item.group_id}"

    @staticmethod
    def _parse_external_id(external_id: str) -> tuple[str, int]:
        parts = external_id.split(":")
        if len(parts) != 3 or parts[0] != "fipiran":
            raise HistoryIdentityError(f"invalid FIPIRAN external_id: {external_id}")
        try:
            return parts[1], int(parts[2])
        except ValueError as exc:
            raise HistoryIdentityError(f"invalid FIPIRAN external_id: {external_id}") from exc

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> FipiranFundProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def status(self) -> dict[str, object]:
        return {
            "provider": self.source_name,
            "contract": "services-v1",
            "circuit": self.circuit.state,
            "failures": self.circuit.failures,
            "last_success_at": self.circuit.last_success_at,
            "last_failure_at": self.circuit.last_failure_at,
            "reason": self.circuit.reason,
        }

    def _check_circuit(self) -> None:
        if self.circuit.opened_at is None:
            return
        if time.monotonic() - self.circuit.opened_at < self.cooldown_seconds:
            raise CircuitOpenError(self.circuit.reason or "FIPIRAN circuit is open")
        self.circuit.opened_at = None

    def _record_failure(self, exc: Exception) -> None:
        self.circuit.failures += 1
        self.circuit.last_failure_at = datetime.now(UTC)
        self.circuit.reason = type(exc).__name__
        if self.circuit.failures >= self.failure_threshold:
            self.circuit.opened_at = time.monotonic()

    def _record_success(self) -> None:
        self.circuit.failures = 0
        self.circuit.opened_at = None
        self.circuit.reason = None
        self.circuit.last_success_at = datetime.now(UTC)

    def _request(self, method: str, path: str, **kwargs: Any) -> bytes:
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            self.sleep(wait)
        self._check_circuit()
        error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.request(
                    method, f"{self.base_url}/{path.lstrip('/')}", **kwargs
                )
                self._last_request_at = time.monotonic()
                content_type = response.headers.get("content-type", "").lower()
                sample = response.text[:500].lower()
                if "text/html" in content_type or "<html" in sample:
                    marker = (
                        "captcha"
                        if "captcha" in sample
                        else "block"
                        if "access denied" in sample or "forbidden" in sample
                        else "html_error"
                    )
                    raise ProviderBlockedError(f"FIPIRAN returned {marker} page")
                response.raise_for_status()
                if "json" not in content_type and content_type:
                    raise ProviderContractError(
                        f"unexpected content type: {content_type or 'missing'}"
                    )
                self._record_success()
                return response.content
            except (httpx.HTTPError, ProviderBlockedError, ProviderContractError) as exc:
                error = exc
                self._record_failure(exc)
                if isinstance(exc, (ProviderBlockedError, ProviderContractError)):
                    break
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 0
                if status and status not in {408, 425, 429, 500, 502, 503, 504}:
                    break
                if attempt < self.retries and self.circuit.state != "open":
                    retry_after = (
                        exc.response.headers.get("retry-after")
                        if isinstance(exc, httpx.HTTPStatusError)
                        else None
                    )
                    delay = (
                        float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                    )
                    self.sleep(min(delay + self.random_value() * 0.25, 30))
        assert error is not None
        raise error

    @staticmethod
    def _metadata(raw: bytes, observed_at: datetime, external_id: str) -> ProviderMetadata:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return ProviderMetadata(
            source_name="fipiran",
            source_identifier=f"https://www.fipiran.com/mf/profile/{external_id}",
            fetched_at=datetime.now(UTC),
            observed_at=observed_at,
            unit="IRR",
            quality=DataQuality.VALID,
            data_version="services-v1",
            raw_hash=hashlib.sha256(raw).hexdigest(),
        )

    def fetch(self) -> list[FundRecord]:
        raw = self._request(
            "POST",
            self.catalog_path,
            json={"regNos": [], "showMarketMakers": False},
        )
        try:
            payload = _FundResponse.model_validate_json(raw)
        except ValueError as exc:
            raise ProviderContractError("catalogue schema mismatch") from exc
        if payload.status != 200:
            raise ValueError(f"FIPIRAN returned status {payload.status}")
        records: list[FundRecord] = []
        seen: dict[tuple[str, int], _FundItem] = {}
        catalogue_by_reg_no: dict[str, list[_FundItem]] = {}
        for item in payload.items:
            identity = (item.reg_no, item.group_id)
            previous = seen.get(identity)
            if previous is not None:
                if previous != item:
                    raise ProviderContractError(
                        "conflicting duplicate FIPIRAN catalogue identity: "
                        f"regNo={item.reg_no}, groupId={item.group_id}"
                    )
                continue
            seen[identity] = item
            catalogue_by_reg_no.setdefault(item.reg_no, []).append(item)
            fund_type = FUND_TYPES.get(item.fund_type)
            if fund_type is None:
                continue
            nav = item.statistical_nav or item.cancel_nav
            if nav is not None and nav <= 0:
                raise ValueError(f"non-positive NAV for FIPIRAN fund {item.reg_no}")
            records.append(
                FundRecord(
                    external_id=self._external_id(item),
                    name_fa=item.name.strip(),
                    symbol=(item.small_symbol_name or "").strip() or None,
                    fund_type=fund_type,
                    is_etf=(item.type_of_invest or "").lower() == "negotiable",
                    inception_date=item.initiation_date.date().isoformat()
                    if item.initiation_date
                    else None,
                    nav=nav,
                    market_price=None,
                    volume=None,
                    trade_value=None,
                    total_net_assets=item.net_asset,
                    manager=item.manager,
                    market_maker=None,
                    is_active=item.is_completed,
                    asset_allocation={
                        "stock": item.stock,
                        "bond": item.bond,
                        "cash": item.cash,
                        "deposit": item.deposit,
                        "commodity": item.commodity,
                    },
                    metadata=self._metadata(raw, item.date, item.reg_no),
                )
            )
        self._catalogue_by_reg_no = catalogue_by_reg_no
        return records

    def fetch_nav_history(self, external_id: str) -> list[FundNavRecord]:
        reg_no, group_id = self._parse_external_id(external_id)
        candidates = self._catalogue_by_reg_no.get(reg_no)
        if not candidates:
            raise HistoryIdentityError(
                f"catalogue identity not loaded for FIPIRAN history: {external_id}"
            )
        raw = self._request("GET", f"{self.history_path}?regno={reg_no}&showAll=true")
        try:
            items = TypeAdapter(list[_NavItem]).validate_json(raw)
        except ValueError as exc:
            raise ProviderContractError("history schema mismatch") from exc
        if not items:
            raise HistoryIdentityError(f"empty FIPIRAN history for {external_id}")
        latest = max(items, key=lambda value: value.date)
        matches = [
            item
            for item in candidates
            if item.cancel_nav == latest.cancel_nav
            and item.statistical_nav == latest.statistical_nav
        ]
        requested = next((item for item in candidates if item.group_id == group_id), None)
        if requested is None or len(matches) != 1 or matches[0] != requested:
            raise HistoryIdentityError(
                "FIPIRAN regNo history does not uniquely match catalogue identity: "
                f"{external_id}; matches={[self._external_id(item) for item in matches]}"
            )
        records: list[FundNavRecord] = []
        seen: set[datetime] = set()
        for item in sorted(items, key=lambda value: value.date):
            observed_at = item.date.replace(tzinfo=item.date.tzinfo or UTC)
            if observed_at in seen:
                continue
            seen.add(observed_at)
            if item.cancel_nav <= 0:
                raise ValueError(f"non-positive historical NAV for FIPIRAN fund {external_id}")
            records.append(
                FundNavRecord(
                    external_id=external_id,
                    observed_at=observed_at,
                    nav=item.cancel_nav,
                    total_net_assets=None,
                    metadata=self._metadata(raw, observed_at, reg_no),
                )
            )
        return records

    def schema_fingerprint(self, payload: dict[str, Any]) -> str:
        """Stable helper used by monitoring to detect upstream key changes."""
        keys = sorted(payload)
        return hashlib.sha256(json.dumps(keys).encode()).hexdigest()
