"""Run isolated PostgreSQL/API/Streamlit E2E and emit validation artifacts."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
COMPOSE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml"]


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout if capture else ""


def request(path: str) -> tuple[dict[str, object], float]:
    started = time.perf_counter()
    with urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=10) as response:
        payload = json.load(response)
    return payload, (time.perf_counter() - started) * 1000


def refresh() -> dict[str, object]:
    request_object = urllib.request.Request(
        "http://127.0.0.1:8000/v1/admin/data-refresh",
        method="POST",
        headers={"X-IRMA-Admin-Key": "e2e-admin-key"},
    )
    with urllib.request.urlopen(request_object, timeout=30) as response:
        return json.load(response)


def recommendation(profile: dict[str, object]) -> dict[str, object]:
    request_object = urllib.request.Request(
        "http://127.0.0.1:8000/v1/recommendations",
        data=json.dumps(profile).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request_object, timeout=30) as response:
        return json.load(response)


def profile_result(payload: dict[str, object], capital: int) -> dict[str, object]:
    allocations = payload["allocations"]
    assert isinstance(allocations, list)
    percentages = sum(int(item["percent"]) for item in allocations)
    amounts = sum(int(item["amount_toman"]) for item in allocations)
    instrument_count = sum(len(item["instruments"]) for item in allocations)
    if percentages != 100 or amounts != capital:
        raise RuntimeError("recommendation totals are inconsistent")
    return {
        "class_count": sum(1 for item in allocations if item["percent"] > 0),
        "instrument_count": instrument_count,
        "percent_total": percentages,
        "amount_total": amounts,
        "withheld": instrument_count == 0,
        "warnings": payload["warnings"],
    }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    report: dict[str, object] = {
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "run_at": datetime.now(UTC).isoformat(),
        "environment": "e2e",
        "provider": "sanitized-test-fixture",
        "live_provider": False,
        "errors": [],
        "warnings": [],
    }
    try:
        run("up", "-d", "--build", "--wait", "database", "api", "web")
        ready, latency = request("/ready")
        first_refresh = refresh()
        second_refresh = refresh()
        report["database"] = ready.get("database")
        report["api_response_ms"] = round(latency, 2)
        report["metrics"] = request("/metrics")[0]
        report["funds"] = request("/v1/funds")[0]
        report["first_refresh"] = first_refresh
        report["second_refresh"] = second_refresh
        report["idempotent"] = second_refresh.get("history_written") == 0
        base_profile: dict[str, object] = {
            "monthly_contribution_toman": 0,
            "horizon": "one_to_three_years",
            "risk_tolerance": "moderate",
            "max_drawdown_tolerance": 0.2,
            "needs_monthly_income": False,
            "liquidity_need": "medium",
            "experience": "beginner",
            "trading_experience": "none",
            "investment_style": "balanced",
            "wants_trading": False,
            "max_trading_percent": 0,
            "has_emergency_fund": True,
            "goal": "validation",
            "current_assets": [],
        }
        profiles = {
            "small": {
                **base_profile,
                "capital_toman": 1_000_000,
                "monthly_contribution_toman": 500_000,
                "liquidity_need": "high",
            },
            "medium": {
                **base_profile,
                "capital_toman": 50_000_000,
                "monthly_contribution_toman": 5_000_000,
                "wants_trading": True,
                "max_trading_percent": 3,
                "trading_experience": "beginner",
            },
            "large": {
                **base_profile,
                "capital_toman": 1_000_000_000,
                "horizon": "three_to_five_years",
                "risk_tolerance": "aggressive",
                "max_drawdown_tolerance": 0.5,
                "experience": "advanced",
                "trading_experience": "advanced",
                "wants_trading": True,
                "max_trading_percent": 10,
            },
            "conservative": {
                **base_profile,
                "capital_toman": 200_000_000,
                "horizon": "six_to_twelve_months",
                "risk_tolerance": "conservative",
                "max_drawdown_tolerance": 0.1,
                "needs_monthly_income": True,
                "liquidity_need": "high",
            },
        }
        report["profiles"] = {
            name: profile_result(recommendation(profile), int(profile["capital_toman"]))
            for name, profile in profiles.items()
        }
        run(
            "exec",
            "-T",
            "database",
            "sh",
            "-c",
            "pg_dump -U irma -d irma_e2e -Fc -f /tmp/irma.dump && "
            "createdb -U irma irma_restore_test && "
            "pg_restore -U irma -d irma_restore_test --no-owner /tmp/irma.dump && "
            "psql -U irma -d irma_restore_test -Atc 'select count(*) from funds'",
        )
        report["backup_restore"] = "passed"
        report["streamlit"] = (
            urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=10).status == 200
        )
        logs = run("logs", "--no-color", capture=True)
        report["critical_log_errors"] = logs.lower().count("critical")
        report["result"] = (
            "passed" if report["critical_log_errors"] == 0 and report["idempotent"] else "failed"
        )
        if report["result"] != "passed":
            raise RuntimeError("critical log entry detected")
    except Exception as exc:
        report["result"] = "failed"
        report["errors"] = [str(exc)]
        raise
    finally:
        (ARTIFACTS / "e2e-validation-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        summary = "\n".join(
            [
                "# IRMA E2E validation",
                "",
                f"- Result: **{report.get('result', 'failed')}**",
                f"- Environment: `{report['environment']}`",
                "- Data: sanitized offline fixture (not live data)",
                f"- PostgreSQL: `{report.get('database', 'unknown')}`",
                f"- Streamlit: `{report.get('streamlit', False)}`",
                f"- API response: `{report.get('api_response_ms', 'unknown')} ms`",
            ]
        )
        (ARTIFACTS / "e2e-validation-summary.md").write_text(summary + "\n", encoding="utf-8")
        run("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
