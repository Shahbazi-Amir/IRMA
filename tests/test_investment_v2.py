from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from irma.presentation import (
    ASSET_LABELS,
    format_percent,
    format_toman,
    human_toman,
    rial_to_toman,
)
from irma.services.historical_import import import_historical_csv
from irma.services.historical_intelligence import historical_report, rolling_returns
from irma.services.investment_decisions import SimpleDecisionRequest, create_simple_decision


def test_persian_formatting_and_labels() -> None:
    assert format_toman(100_000_000) == "۱۰۰٬۰۰۰٬۰۰۰ تومان"
    assert human_toman(500_000_000) == "۵۰۰٫۰ میلیون تومان"
    assert format_percent(0.125, ratio=True) == "۱۲٫۵٪"
    assert ASSET_LABELS["fixed_income"] == "صندوق درآمد ثابت"
    assert rial_to_toman(1_000_000) == Decimal("100000")


def test_rial_conversion_rejects_silent_rounding() -> None:
    import pytest

    with pytest.raises(ValueError, match="divisible"):
        rial_to_toman(101)


def test_rolling_historical_distribution_is_deterministic() -> None:
    values = [100, 110, 99, 120, 130]
    assert rolling_returns(values, 2) == [
        -0.010000000000000009,
        0.09090909090909083,
        0.31313131313131315,
    ]
    report = historical_report([date(2025, month, 1) for month in range(1, 6)], values, 2)
    distribution = report["window_distribution"]
    assert distribution["sample_count"] == 3
    assert distribution["positive_ratio"] == 2 / 3
    assert "پیش‌بینی" in report["notice"]


def test_beginner_decision_has_amounts_reasons_trace_and_freshness(session: Session) -> None:
    result = create_simple_decision(
        SimpleDecisionRequest(
            capital_toman=Decimal("500000000"),
            horizon="three_to_six_months",
            risk="moderate",
        ),
        session,
    )
    assert sum(item["percent"] for item in result["allocation"]) == 100
    assert sum(item["amount_toman"] for item in result["allocation"]) == Decimal("500000000")
    assert all(item["label"] and item["reason"] for item in result["allocation"])
    assert result["input"]["risk_label"] == "متوسط"
    assert result["decision_trace"]
    assert result["data_freshness"]["status"] == "missing"


def test_v2_api_works_with_empty_database(client: TestClient) -> None:
    response = client.post(
        "/v2/investment-decision",
        json={
            "capital_toman": 500_000_000,
            "horizon": "three_to_six_months",
            "risk": "moderate",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input"]["risk_label"] == "متوسط"
    assert body["data_freshness"]["status"] == "missing"
    assert all(item["label"] not in {"cash", "fixed_income"} for item in body["allocation"])
    assert "تومان" not in str(body["input"]["capital_toman"])
    assert client.get("/v2/historical/not-imported").status_code == 404


def test_streamlit_has_only_three_beginner_navigation_areas() -> None:
    text = Path("apps/streamlit_app/app.py").read_text(encoding="utf-8")
    for label in ["سرمایه‌گذاری من", "بازار و تاریخچه", "پروفایل و روش تحلیل"]:
        assert label in text
    assert "ارتباط با API ناموفق بود:" not in text
    assert "deployable-v1" not in text


def test_historical_import_is_auditable_and_idempotent(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "official.csv"
    path.write_text(
        "observation_date,value,publication_date\n"
        "2025-01-01,100,2025-01-10\n2025-02-01,110,2025-02-10\n",
        encoding="utf-8",
    )
    kwargs = {
        "code": "official-test",
        "name_fa": "سری رسمی آزمایشی",
        "asset_class": "inflation",
        "frequency": "monthly",
        "unit": "index",
        "geography": "Iran",
        "source_name": "official-test-source",
        "source_identifier": "official:test",
        "methodology_note": "Deterministic contract test only.",
    }
    first = import_historical_csv(session, path, **kwargs)
    second = import_historical_csv(session, path, **kwargs)
    assert first["rows_written"] == 2
    assert second["rows_written"] == 0
    assert len(first["sha256"]) == 64

    response = client.get("/v2/historical/official-test?horizon_periods=1")
    assert response.status_code == 200
    assert response.json()["report"]["observation_count"] == 2
    assert "پیش‌بینی" in response.json()["report"]["notice"]
