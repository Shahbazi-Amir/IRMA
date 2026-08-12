"""Migrate, ingest and verify the initial real-data database."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.persistence.migrations import upgrade_database
from irma.persistence.models import DataSource, Fund, FundMetric, FundNavHistory
from irma.services.data_refresh import refresh_from_settings


def main() -> int:
    settings = get_settings()
    started_at = datetime.now(UTC)
    report: dict[str, object] = {
        "status": "running",
        "provider": settings.fund_provider,
        "started_at": started_at.isoformat(),
    }
    try:
        upgrade_database(settings.database_url)
        with SessionLocal() as session:
            session.execute(select(1))
            refresh = refresh_from_settings(session, settings)
            report.update(
                {
                    "status": "success",
                    "migration": "head",
                    "refresh": refresh,
                    "fund_count": session.scalar(select(func.count(Fund.id))) or 0,
                    "history_count": session.scalar(select(func.count(FundNavHistory.id))) or 0,
                    "metric_count": session.scalar(select(func.count(FundMetric.id))) or 0,
                    "source_count": session.scalar(select(func.count(DataSource.id))) or 0,
                }
            )
        return_code = 0
    except Exception as exc:
        report.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        return_code = 1
    finished_at = datetime.now(UTC)
    report["finished_at"] = finished_at.isoformat()
    report["duration_seconds"] = round((finished_at - started_at).total_seconds(), 3)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
