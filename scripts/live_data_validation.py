"""Bounded live FIPIRAN validation that records source failures honestly."""

from __future__ import annotations

import json
import subprocess
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
        "contract_selected": settings.fipiran_contract,
        "fallback_used": False,
    }
    subprocess.run(
        [
            "python",
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
        with SessionLocal() as session:
            first = refresh_from_fipiran(
                session,
                base_url=settings.fipiran_base_url,
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
                min_interval_seconds=settings.provider_min_interval_seconds,
                history_limit=settings.fund_history_limit,
                catalog_path=settings.fipiran_catalog_path,
                history_path=settings.fipiran_history_path,
                user_agent=settings.fipiran_user_agent,
                failure_threshold=settings.provider_circuit_failures,
                cooldown_seconds=settings.provider_circuit_cooldown_seconds,
            )
            second = refresh_from_fipiran(
                session,
                base_url=settings.fipiran_base_url,
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
                min_interval_seconds=settings.provider_min_interval_seconds,
                history_limit=settings.fund_history_limit,
                catalog_path=settings.fipiran_catalog_path,
                history_path=settings.fipiran_history_path,
                user_agent=settings.fipiran_user_agent,
                failure_threshold=settings.provider_circuit_failures,
                cooldown_seconds=settings.provider_circuit_cooldown_seconds,
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
            report["eligible_funds"] = report["ranked_count"]
            report["recommended_real_instruments"] = 0
    except Exception as exc:
        report.update(
            {
                "status": "source_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "fund_count": 0,
                "history_count": 0,
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
