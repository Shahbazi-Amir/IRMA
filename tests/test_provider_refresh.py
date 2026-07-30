from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.config import Settings
from irma.persistence.models import DataIngestionRun, DataSource, Fund
from irma.providers.base import DataQuality, FundRecord, ProviderMetadata
from irma.providers.csv_provider import CsvFundProvider
from irma.services.data_refresh import RefreshCoordinator, refresh_from_settings


def test_csv_provider_preserves_missing_values(tmp_path: Path) -> None:
    path = tmp_path / "funds.csv"
    path.write_text(
        "name_fa,fund_type,source_identifier,observed_at,nav\n"
        "صندوق معتبر,fixed_income,official:test,2026-07-01T12:00:00+00:00,\n",
        encoding="utf-8",
    )
    record = CsvFundProvider(path).fetch()[0]
    assert record.nav is None
    assert record.metadata.raw_hash is not None


def test_csv_provider_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("name_fa\nصندوق\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        CsvFundProvider(path).fetch()


class FlakyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self) -> list[FundRecord]:
        self.calls += 1
        if self.calls < 3:
            raise OSError("temporary")
        now = datetime.now(UTC)
        return [
            FundRecord(
                external_id="TEST-1",
                name_fa="صندوق منبع‌دار",
                symbol="TEST",
                fund_type="gold",
                is_etf=True,
                inception_date="2020-01-01",
                nav=1000,
                market_price=1010,
                volume=100000,
                trade_value=101000000,
                total_net_assets=500000000,
                manager="مدیر",
                market_maker=None,
                is_active=True,
                asset_allocation={"commodity": 95.0},
                metadata=ProviderMetadata(
                    source_name="test-source",
                    source_identifier="official:test",
                    fetched_at=now,
                    observed_at=now,
                    unit="TOMAN",
                    quality=DataQuality.VALID,
                ),
            )
        ]


def test_refresh_retries_and_persists(session: Session) -> None:
    provider = FlakyProvider()
    result = RefreshCoordinator(max_retries=2, sleep=lambda _: None).refresh_funds(
        session, provider
    )
    assert provider.calls == 3
    assert result["records_written"] == 1
    assert session.scalar(select(Fund).where(Fund.symbol == "TEST")) is not None
    source = session.scalar(select(DataSource).where(DataSource.name == "test-source"))
    assert source is not None and source.status == "valid"
    run = session.scalar(select(DataIngestionRun))
    assert run is not None and run.status == "success"


def test_refresh_records_provider_error(session: Session) -> None:
    class Broken:
        def fetch(self) -> list[FundRecord]:
            raise OSError("broken")

    with pytest.raises(OSError):
        RefreshCoordinator(max_retries=0).refresh_funds(session, Broken())
    run = session.scalar(select(DataIngestionRun))
    assert run is not None and run.status == "error"


def test_configured_csv_provider_is_selected(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "funds.csv"
    path.write_text(
        "external_id,name_fa,fund_type,source_identifier,observed_at,nav\n"
        "CSV-1,صندوق واقعی فایل,fixed_income,official:file,"
        "2026-07-01T12:00:00+00:00,1000\n",
        encoding="utf-8",
    )
    settings = Settings(
        fund_provider="csv",
        fund_csv_path=str(path),
        fund_history_limit=0,
        provider_max_retries=0,
    )
    result = refresh_from_settings(session, settings)
    assert result["provider"] == "csv"
    assert result["records_received"] == 1
    assert result["records_written"] == 1


def test_configured_fipiran_provider_is_selected(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeFipiran(FlakyProvider):
        def __init__(self, **_: object) -> None:
            super().__init__()
            self.calls = 2

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("irma.services.data_refresh.FipiranFundProvider", FakeFipiran)
    result = refresh_from_settings(
        session,
        Settings(fund_provider="fipiran", fund_history_limit=0, provider_max_retries=0),
    )
    assert result["provider"] == "fipiran"
    assert result["records_received"] == 1


def test_configured_chain_falls_back_to_official_file(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenFipiran:
        def __init__(self, **_: object) -> None:
            pass

        def fetch(self) -> list[FundRecord]:
            raise OSError("offline")

        def close(self) -> None:
            pass

    official = tmp_path / "official.csv"
    official.write_text(
        "external_id,name_fa,fund_type,source_identifier,observed_at,nav\n"
        "CHAIN-1,صندوق رسمی جایگزین,gold,official:file,"
        "2026-07-01T12:00:00+00:00,2000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("irma.services.data_refresh.FipiranFundProvider", BrokenFipiran)
    result = refresh_from_settings(
        session,
        Settings(
            fund_provider="chain",
            official_fund_file_path=str(official),
            fund_history_limit=0,
            provider_max_retries=0,
        ),
    )
    assert result["selected_source"] == "official-file"
    assert result["fallback_errors"] == ["fipiran: OSError"]
    assert result["records_written"] == 1


def test_configured_refresh_reports_provider_failure(session: Session, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="csv refresh failed"):
        refresh_from_settings(
            session,
            Settings(
                fund_provider="csv",
                fund_csv_path=str(tmp_path / "missing.csv"),
                provider_max_retries=0,
            ),
        )
