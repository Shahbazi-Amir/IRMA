"""Bounded live FIPIRAN validation that records source failures honestly."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.persistence.models import Fund, FundMetric, FundNavHistory
from irma.services.data_refresh import refresh_from_fipiran
from irma.services.fund_rankings import rank_funds


def main() -> None:
    settings = get_settings()
    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)
    report: dict[str, object] = {
        "run_at": datetime.now(UTC).isoformat(),
        "provider": "fipiran",
        "environment": settings.app_env,
        "live": True,
    }
    try:
        with SessionLocal() as session:
            first = refresh_from_fipiran(
                session,
                base_url=settings.fipiran_base_url,
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
                min_interval_seconds=settings.provider_min_interval_seconds,
                history_limit=settings.fund_history_limit,
            )
            second = refresh_from_fipiran(
                session,
                base_url=settings.fipiran_base_url,
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
                min_interval_seconds=settings.provider_min_interval_seconds,
                history_limit=settings.fund_history_limit,
            )
            report.update(
                {
                    "status": "success",
                    "first_refresh": first,
                    "second_refresh": second,
                    "fund_count": session.scalar(select(func.count(Fund.id))) or 0,
                    "history_count": session.scalar(select(func.count(FundNavHistory.id))) or 0,
                    "metric_count": session.scalar(select(func.count(FundMetric.id))) or 0,
                    "ranked_count": sum(
                        int(rank_funds(session, kind)["eligible_count"])
                        for kind in ("fixed_income", "gold", "equity", "mixed", "index")
                    ),
                }
            )
    except Exception as exc:
        report.update({"status": "source_unavailable", "error": str(exc)})
    (artifact_dir / "live-data-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (artifact_dir / "live-data-validation-summary.md").write_text(
        f"# Live FIPIRAN validation\n\n- Status: `{report['status']}`\n"
        f"- Run: `{report['run_at']}`\n"
        "- This is a live validation result; no fixture is substituted on failure.\n",
        encoding="utf-8",
    )
    if report["status"] != "success":
        print(f"warning: live source validation did not complete: {report.get('error')}")


if __name__ == "__main__":
    main()
