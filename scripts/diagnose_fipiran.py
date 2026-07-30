"""Run a bounded, sanitized FIPIRAN connectivity diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SENSITIVE = re.compile(r"(cookie|authorization|token|secret|csrf|set-cookie)", re.I)
SAFE_HEADERS = {"content-type", "content-length", "date", "server", "retry-after", "location"}


def sanitize(text: str) -> str:
    text = re.sub(
        r"(?i)(token|secret|password|cookie|authorization)[=:]\s*\S+", r"\1=[redacted]", text
    )
    return text[:500]


def diagnose(
    *,
    url: str,
    method: str,
    payload: dict[str, Any] | None,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": "https://www.fipiran.com/",
        "User-Agent": "IRMA/1.0 (+https://github.com/Shahbazi-Amir/IRMA)",
    }
    with httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10)),
        follow_redirects=False,
        headers=headers,
    ) as client:
        for attempt in range(retries + 1):
            started = time.perf_counter()
            try:
                response = client.request(method, url, json=payload)
                body = response.content
                safe_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() in SAFE_HEADERS and not SENSITIVE.search(key)
                }
                entry = {
                    "attempt": attempt + 1,
                    "status_code": response.status_code,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "redirect": response.headers.get("location"),
                    "content_type": response.headers.get("content-type"),
                    "response_bytes": len(body),
                    "response_sha256": hashlib.sha256(body).hexdigest(),
                    "headers": safe_headers,
                    "sample": sanitize(response.text),
                }
                attempts.append(entry)
                if response.status_code < 500 and response.status_code != 429:
                    break
                retry_after = response.headers.get("retry-after")
                if attempt < retries:
                    time.sleep(
                        min(
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else 2**attempt,
                            5,
                        )
                    )
            except httpx.HTTPError as exc:
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                        "error": type(exc).__name__,
                        "sample": sanitize(str(exc)),
                    }
                )
                if attempt < retries:
                    time.sleep(min(2**attempt, 5))
    return {
        "run_at": datetime.now(UTC).isoformat(),
        "url": url,
        "method": method,
        "attempts": attempts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--catalog", action="store_true")
    target.add_argument("--history", metavar="REGNO")
    parser.add_argument("--base-url", default="https://www.fipiran.com/services")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("artifacts/fipiran-diagnostics"))
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if args.catalog:
        report = diagnose(
            url=f"{base}/fund/fundcompare/",
            method="POST",
            payload={"regNos": [], "showMarketMakers": False},
            timeout=args.timeout,
            retries=args.retries,
        )
    else:
        report = diagnose(
            url=f"{base}/chart/getfundchart?regno={args.history}&showAll=true",
            method="GET",
            payload=None,
            timeout=args.timeout,
            retries=args.retries,
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "diagnostics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    last = report["attempts"][-1]
    markdown = (
        "# FIPIRAN diagnostics\n\n"
        f"- Run: `{report['run_at']}`\n"
        f"- Method: `{report['method']}`\n"
        f"- Status: `{last.get('status_code', last.get('error', 'unknown'))}`\n"
        f"- Attempts: `{len(report['attempts'])}`\n"
        "- Sensitive headers and credentials are never recorded.\n"
    )
    (args.output / "diagnostics.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
