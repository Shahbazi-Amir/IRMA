"""Bounded live FIPIRAN validation with migration and deterministic replay."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic.util.exc import CommandError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.persistence.migrations import upgrade_database
from irma.persistence.models import Fund, FundMetric, FundNavHistory
from irma.providers.fipiran import ProviderBlockedError, ProviderContractError
from irma.services.data_refresh import refresh_from_fipiran
from irma.services.fund_rankings import rank_funds


def _counts(session: Session) -> dict[str, int]:
    return {
        "funds": session.scalar(select(func.count(Fund.id))) or 0,
        "history": session.scalar(select(func.count(FundNavHistory.id))) or 0,
        "metrics": session.scalar(select(func.count(FundMetric.id))) or 0,
    }


def _duplicate_counts(session: Session) -> dict[str, int]:
    fund_duplicates = select(Fund.external_id).group_by(Fund.external_id).having(func.count() > 1)
    history_duplicates = (
        select(FundNavHistory.fund_id, FundNavHistory.valid_at)
        .group_by(FundNavHistory.fund_id, FundNavHistory.valid_at)
        .having(func.count() > 1)
    )
    metric_duplicates = (
        select(FundMetric.fund_id, FundMetric.metric_name, FundMetric.period_label)
        .group_by(FundMetric.fund_id, FundMetric.metric_name, FundMetric.period_label)
        .having(func.count() > 1)
    )
    return {
        "funds": len(session.execute(fund_duplicates).all()),
        "history": len(session.execute(history_duplicates).all()),
        "metrics": len(session.execute(metric_duplicates).all()),
    }


def classify_failure(exc: Exception) -> str:
    """Keep local schema and validation failures distinct from source outages."""
    if isinstance(exc, CommandError):
        return "migration_error"
    if isinstance(exc, SQLAlchemyError):
        return "database_error"
    if isinstance(exc, (ProviderBlockedError, ProviderContractError, OSError)):
        return "source_unavailable"
    return "validation_error"


def _refresh(
    settings: Any,
    session: Session,
    *,
    history_external_ids: list[str] | None = None,
) -> dict[str, Any]:
    return refresh_from_fipiran(
        session,
        base_url=settings.fipiran_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
        min_interval_seconds=settings.provider_min_interval_seconds,
        history_limit=settings.fund_history_limit,
        history_external_ids=history_external_ids,
        catalog_path=settings.fipiran_catalog_path,
        history_path=settings.fipiran_history_path,
        user_agent=settings.fipiran_user_agent,
        failure_threshold=settings.provider_circuit_failures,
        cooldown_seconds=settings.provider_circuit_cooldown_seconds,
    )


def main() -> None:
    settings = get_settings()
    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)
    report: dict[str, object] = {
        "run_at": datetime.now(UTC).isoformat(),
        "provider": "fipiran",
        "environment": settings.app_env,
        "live": True,
        "fixture_used": False,
        "contract_selected": settings.fipiran_contract,
        "fallback_used": False,
    }
    subprocess.run(
        [
            sys.executable,
            "scripts/diagnose_fipiran.py",
            "--catalog",
            "--timeout",
            str(settings.provider_timeout_seconds),
            "--retries",
            "1",
            "--output",
            str(artifact_dir / "fipiran-diagnostics"),
        ],
        check=False,
    )
    try:
        upgrade_database(settings.database_url)
        report["migration"] = "head"
        with SessionLocal() as session:
            first = _refresh(settings, session)
            after_first = _counts(session)
            attempted = list(first["history_attempted"])
            second = _refresh(settings, session, history_external_ids=attempted)
            after_second = _counts(session)
            duplicates = _duplicate_counts(session)
            stable = after_first == after_second
            no_duplicates = not any(duplicates.values())
            history_errors = list(first["history_errors"]) + list(second["history_errors"])
            if not stable or not no_duplicates:
                status = "idempotency_failed"
            elif history_errors:
                status = "partial_history"
            else:
                status = "success"
            report.update(
                {
                    "status": status,
                    "first_refresh": first,
                    "second_refresh": second,
                    "deterministic_history_external_ids": attempted,
                    "counts_after_first": after_first,
                    "counts_after_second": after_second,
                    "counts_stable": stable,
                    "duplicate_logical_records": duplicates,
                    "fund_count": after_second["funds"],
                    "history_count": after_second["history"],
                    "metric_count": after_second["metrics"],
                    "ranked_count": sum(
                        int(rank_funds(session, kind)["eligible_count"])
                        for kind in ("fixed_income", "gold", "equity", "mixed", "index")
                    ),
                }
            )
            report["eligible_funds"] = report["ranked_count"]
            report["recommended_real_instruments"] = 0
    except Exception as exc:
        report.update(
            {
                "status": classify_failure(exc),
                "error": f"{type(exc).__name__}: {exc}",
                "fund_count": 0,
                "history_count": 0,
                "metric_count": 0,
                "ranked_count": 0,
                "eligible_funds": 0,
                "recommended_real_instruments": 0,
            }
        )
    (artifact_dir / "live-data-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (artifact_dir / "live-data-validation-summary.md").write_text(
        f"# Live FIPIRAN validation\n\n- Status: `{report['status']}`\n"
        f"- Run: `{report['run_at']}`\n"
        f"- Contract: `{report['contract_selected']}`\n"
        f"- Funds: `{report.get('fund_count', 0)}`\n"
        f"- History rows: `{report.get('history_count', 0)}`\n"
        f"- Eligible funds: `{report.get('eligible_funds', 0)}`\n"
        f"- Recommended real instruments: `{report.get('recommended_real_instruments', 0)}`\n"
        "- This is a live validation result; no fixture is substituted on failure.\n",
        encoding="utf-8",
    )
    if report["status"] != "success":
        print(f"warning: live source validation did not complete: {report.get('error')}")


if __name__ == "__main__":
    main()
