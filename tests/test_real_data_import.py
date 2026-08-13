import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from irma.persistence.models import HistoricalObservation
from irma.services.historical_audit import (
    audit_dates,
    audit_historical_database,
    eligible_horizons,
    real_return_if_aligned,
)
from irma.services.world_bank_import import import_world_bank_file, parse_world_bank_payload


def _payload(indicator: str, values: dict[int, float | None]) -> bytes:
    return json.dumps(
        [
            {"lastupdated": "2026-07-13"},
            [
                {
                    "indicator": {"id": indicator},
                    "countryiso3code": "IRN",
                    "date": str(year),
                    "value": value,
                }
                for year, value in values.items()
            ],
        ]
    ).encode()


def test_world_bank_contract_filters_nulls_and_rejects_identity() -> None:
    _, rows = parse_world_bank_payload(
        _payload("FP.CPI.TOTL.ZG", {2024: 32.5, 2025: None}), "FP.CPI.TOTL.ZG"
    )
    assert rows == [{"year": 2024, "value": 32.5}]
    with pytest.raises(ValueError, match="identity"):
        parse_world_bank_payload(_payload("WRONG", {2024: 1}), "FP.CPI.TOTL.ZG")
    _, deflation = parse_world_bank_payload(
        _payload("FP.CPI.TOTL.ZG", {1966: -0.4}),
        "FP.CPI.TOTL.ZG",
        allow_negative=True,
    )
    assert deflation[0]["value"] < 0


def test_real_data_import_is_idempotent_and_detects_conflicts(
    session: Session, tmp_path: Path
) -> None:
    path = tmp_path / "inflation.json"
    path.write_bytes(_payload("FP.CPI.TOTL.ZG", {2022: 40.0, 2023: 44.6, 2024: 32.5}))
    first = import_world_bank_file(session, path, "inflation_annual")
    second = import_world_bank_file(session, path, "inflation_annual")
    assert first["rows_written"] == 3
    assert second["rows_written"] == 0
    assert second["duplicates"] == 3
    assert session.query(HistoricalObservation).count() == 3
    path.write_bytes(_payload("FP.CPI.TOTL.ZG", {2022: 40.1, 2023: 44.6, 2024: 32.5}))
    with pytest.raises(ValueError, match="conflicting published value"):
        import_world_bank_file(session, path, "inflation_annual")


def test_annual_frequency_gates_short_horizons(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "fx.json"
    path.write_bytes(_payload("PA.NUS.FCRF", {year: 42_000 + year for year in range(2018, 2025)}))
    import_world_bank_file(session, path, "fx_official_annual")
    report = audit_historical_database(session)[0]
    assert report["unit"] == "IRR per USD"
    assert report["eligible_horizons"]["1w"] is False
    assert report["eligible_horizons"]["6m"] is False
    assert report["eligible_horizons"]["1y"] is True


def test_gap_and_duplicate_audit() -> None:
    from datetime import date

    dates = [date(2024, 1, 1), date(2024, 1, 1), date(2024, 4, 1)]
    audit = audit_dates(dates, "monthly")
    assert audit["duplicate_dates"] == 1
    assert audit["gaps"] == 1
    assert eligible_horizons(dates, "monthly")["1m"] is False


def test_real_return_requires_aligned_periods() -> None:
    assert real_return_if_aligned(
        0.30, 0.20, nominal_frequency="annual", inflation_frequency="annual"
    ) == pytest.approx(1.3 / 1.2 - 1)
    with pytest.raises(ValueError, match="not aligned"):
        real_return_if_aligned(
            0.03, 0.20, nominal_frequency="monthly", inflation_frequency="annual"
        )


def test_failed_reimport_preserves_last_known_good(session: Session, tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_bytes(_payload("FP.CPI.TOTL.ZG", {2023: 44.6, 2024: 32.5}))
    import_world_bank_file(session, valid, "inflation_annual")
    before = session.query(HistoricalObservation).count()
    broken = tmp_path / "broken.json"
    broken.write_text('{"contract": "changed"}', encoding="utf-8")
    with pytest.raises(ValueError, match="contract"):
        import_world_bank_file(session, broken, "inflation_annual")
    session.rollback()
    assert session.query(HistoricalObservation).count() == before
