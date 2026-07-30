from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from irma.analytics.series import (
    calculate_series_metrics,
    correlation,
    information_ratio,
    periodic_returns,
    real_total_return,
    tracking_error,
)
from irma.providers.multi_asset_csv import (
    CsvBankProductProvider,
    CsvInflationProvider,
    CsvInstrumentMarketProvider,
    CsvMarketIndexProvider,
)
from irma.services.data_quality import Severity, validate_ohlcv
from irma.services.multi_asset_refresh import (
    refresh_bank_products,
    refresh_inflation,
    refresh_market_indices,
    refresh_market_instruments,
)
from irma.services.portfolio_plans import rebalance_plan, staged_entry_plan


def write_csv(path: Path, header: str, row: str) -> Path:
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")
    return path


def index_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "indices.csv",
        "source_identifier,index_code,name_fa,name_en,observation_date,observed_at,"
        "open,high,low,close,change,change_percent,unit,data_version",
        "https://example.ir/official,tedpix,شاخص کل,TEDPIX,2026-07-29T12:30:00+03:30,"
        "2026-07-29T13:00:00+03:30,100,110,95,108,8,8,INDEX_POINT,v1",
    )


def instrument_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "instruments.csv",
        "source_identifier,stable_id,symbol,name_fa,instrument_type,observation_date,"
        "observed_at,open,high,low,close,last,volume,trade_value,trade_count,best_bid,"
        "best_ask,market_status,unit,data_version",
        "https://example.ir/official,ins-1,طلا,صندوق طلا,gold_fund,"
        "2026-07-29T12:30:00+03:30,2026-07-29T13:00:00+03:30,"
        "100,110,95,108,109,1000,108000,20,108,109,open,IRR,v1",
    )


def inflation_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "inflation.csv",
        "source_identifier,indicator_code,indicator_name,period,period_type,base_year,"
        "publication_date,observed_at,monthly_inflation,point_to_point_inflation,"
        "annual_inflation,consumer_price_index,unit,data_version",
        "https://amar.org.ir/cpi,cpi_all,شاخص قیمت مصرف‌کننده,1405-04,monthly,1400,"
        "2026-07-25,2026-07-25T12:00:00+03:30,2.5,35,30,220,PERCENT_INDEX,v1",
    )


def bank_csv(tmp_path: Path) -> Path:
    return write_csv(
        tmp_path / "bank.csv",
        "source_identifier,bank_name,product_name,product_type,source_url,publication_date,"
        "valid_from,valid_until,verification_status,observed_at,nominal_rate,effective_rate,"
        "minimum_deposit_toman,term_months,early_withdrawal_rate,payment_frequency,"
        "conditions_summary,unit,data_version",
        "bank-1,بانک نمونه,سپرده یک‌ساله,term_deposit,https://bank.example/product,"
        "2026-07-01,2026-07-01,2026-12-31,official_verified,"
        "2026-07-01T12:00:00+03:30,20,21,1000000,12,10,monthly,شرایط رسمی,PERCENT,v1",
    )


def test_csv_providers_and_validation(tmp_path: Path) -> None:
    assert CsvMarketIndexProvider(index_csv(tmp_path)).fetch()[0].close_value == 108
    assert CsvInstrumentMarketProvider(instrument_csv(tmp_path)).fetch()[0].symbol == "طلا"
    inflation = CsvInflationProvider(inflation_csv(tmp_path)).fetch()[0]
    assert inflation.base_year == "1400"
    assert inflation.monthly_inflation == 2.5
    bank = CsvBankProductProvider(bank_csv(tmp_path)).fetch()[0]
    assert bank.verification_status == "official_verified"
    assert bank.minimum_deposit_toman == 1_000_000


def test_csv_rejects_missing_duplicate_and_impossible_data(tmp_path: Path) -> None:
    missing = write_csv(tmp_path / "missing.csv", "source_identifier", "x")
    with pytest.raises(ValueError, match="missing columns"):
        CsvMarketIndexProvider(missing).fetch()
    invalid = write_csv(
        tmp_path / "invalid.csv",
        "source_identifier,index_code,name_fa,observation_date,observed_at,close",
        "x,t,t,2026-01-01T00:00:00+00:00,2026-01-01T00:00:00+00:00,-1",
    )
    with pytest.raises(ValueError, match="cannot be negative"):
        CsvMarketIndexProvider(invalid).fetch()
    with pytest.raises(FileNotFoundError):
        CsvInflationProvider(tmp_path / "absent.csv").fetch()


def test_multi_asset_refresh_is_idempotent(session: Session, tmp_path: Path) -> None:
    paths = (
        (refresh_market_indices, index_csv(tmp_path)),
        (refresh_market_instruments, instrument_csv(tmp_path)),
        (refresh_inflation, inflation_csv(tmp_path)),
        (refresh_bank_products, bank_csv(tmp_path)),
    )
    for refresh, path in paths:
        first = refresh(session, path)
        second = refresh(session, path)
        assert first["received"] == 1
        assert first["written"] == 1
        assert second["written"] == 0


def test_series_metrics_and_relative_analytics() -> None:
    dates = [date(2025, 1, 1) + timedelta(days=index * 30) for index in range(13)]
    values = [100 + index * 3 for index in range(13)]
    metrics = calculate_series_metrics(dates, values, periods_per_year=12)
    assert metrics.observation_count == 13
    assert metrics.cagr is not None
    assert metrics.maximum_drawdown == 0
    assert metrics.positive_period_ratio == 1
    returns = periodic_returns(values)
    assert correlation(returns, returns) == pytest.approx(1)
    assert tracking_error(returns, returns) is None
    assert information_ratio(returns, returns) is None
    assert real_total_return(0.5, 0.25) == pytest.approx(0.2)
    with pytest.raises(ValueError):
        periodic_returns([1])
    with pytest.raises(ValueError):
        correlation([1], [1])


def test_quality_and_portfolio_plans() -> None:
    assert (
        validate_ohlcv(open_price=None, high_price=None, low_price=None, close_price=None)[
            0
        ].severity
        is Severity.ERROR
    )
    findings = validate_ohlcv(open_price=100, high_price=90, low_price=95, close_price=110)
    assert any(not item.recommendation_allowed for item in findings)
    plan = staged_entry_plan(
        amount_toman=Decimal("1000000"),
        risk="aggressive",
        volatility=0.35,
        data_quality="valid",
        liquidity="high",
    )
    assert plan["stage_count"] == 4
    assert sum(plan["amounts_toman"]) == Decimal("1000000")  # type: ignore[arg-type]
    disabled = staged_entry_plan(
        amount_toman=Decimal("100"),
        risk="moderate",
        volatility=None,
        data_quality="error",
        liquidity="low",
    )
    assert disabled["enabled"] is False
    rebalance = rebalance_plan(
        target_weights={"cash": 20, "equity": 80},
        current_weights={"cash": 30, "equity": 70},
        monthly_contribution_toman=Decimal("100000"),
    )
    assert rebalance["items"][1]["action"] == "direct_new_contribution"  # type: ignore[index]


def test_multi_asset_api(client: TestClient, session: Session, tmp_path: Path) -> None:
    refresh_market_indices(session, index_csv(tmp_path))
    refresh_market_instruments(session, instrument_csv(tmp_path))
    refresh_inflation(session, inflation_csv(tmp_path))
    refresh_bank_products(session, bank_csv(tmp_path))
    assert client.get("/ready").status_code == 200
    assert client.get("/v1/market/indices").json()["count"] == 1
    assert client.get("/v1/market/indices/tedpix").status_code == 200
    instruments = client.get("/v1/market/instruments").json()
    assert instruments["items"][0]["symbol"] == "طلا"
    instrument_id = instruments["items"][0]["instrument_id"]
    assert client.get(f"/v1/market/instruments/{instrument_id}").status_code == 200
    assert client.get("/v1/economy/inflation").json()["count"] == 1
    assert client.get("/v1/bank-products").json()["count"] == 1
    assert len(client.get("/v1/asset-classes/comparison").json()["items"]) == 10
    rebalance = client.post(
        "/v1/recommendations/rebalance",
        json={
            "target_weights": {"cash": 20, "equity": 80},
            "current_weights": {"cash": 25, "equity": 75},
        },
    )
    assert rebalance.status_code == 200
    assert client.get("/v1/market/gold-funds").json()["items"] == []
    assert client.get("/v1/market/indices/missing").status_code == 404
    assert client.get("/v1/market/instruments/999").status_code == 404
