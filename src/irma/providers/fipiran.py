"""FIPIRAN adapter isolated from the domain and validated at its boundary."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self.client = client
        self.sleep = sleep
        self._last_request_at = 0.0

    def _request(self, method: str, path: str, **kwargs: Any) -> bytes:
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            self.sleep(wait)
        headers = {
            "Referer": "https://www.fipiran.com/",
            "User-Agent": "IRMA/1.0 (+https://github.com/Shahbazi-Amir/IRMA)",
        }
        client = self.client or httpx.Client(timeout=self.timeout_seconds, headers=headers)
        close = self.client is None
        try:
            response = client.request(method, f"{self.base_url}/{path.lstrip('/')}", **kwargs)
            self._last_request_at = time.monotonic()
            response.raise_for_status()
            return response.content
        finally:
            if close:
                client.close()

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
            "fund/fundcompare/",
            json={"regNos": [], "showMarketMakers": False},
        )
        payload = _FundResponse.model_validate_json(raw)
        if payload.status != 200:
            raise ValueError(f"FIPIRAN returned status {payload.status}")
        records: list[FundRecord] = []
        seen: set[str] = set()
        for item in payload.items:
            if item.reg_no in seen:
                raise ValueError(f"duplicate FIPIRAN regNo: {item.reg_no}")
            seen.add(item.reg_no)
            fund_type = FUND_TYPES.get(item.fund_type)
            if fund_type is None:
                continue
            nav = item.statistical_nav or item.cancel_nav
            if nav is not None and nav <= 0:
                raise ValueError(f"non-positive NAV for FIPIRAN fund {item.reg_no}")
            records.append(
                FundRecord(
                    external_id=item.reg_no,
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
        return records

    def fetch_nav_history(self, external_id: str) -> list[FundNavRecord]:
        raw = self._request("GET", f"chart/getfundchart?regno={external_id}&showAll=true")
        items = TypeAdapter(list[_NavItem]).validate_json(raw)
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
                    metadata=self._metadata(raw, observed_at, external_id),
                )
            )
        return records

    def schema_fingerprint(self, payload: dict[str, Any]) -> str:
        """Stable helper used by monitoring to detect upstream key changes."""
        keys = sorted(payload)
        return hashlib.sha256(json.dumps(keys).encode()).hexdigest()
