"""Create and prune compressed PostgreSQL custom-format backups."""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="backups")
    parser.add_argument("--retention-days", type=int, default=14)
    args = parser.parse_args()
    database_url = os.environ.get("IRMA_DATABASE_URL")
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("IRMA_DATABASE_URL must identify PostgreSQL")
    pg_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"irma-{timestamp}.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--compress=9", "--file", str(destination), pg_url],
        check=True,
    )
    cutoff = datetime.now(UTC) - timedelta(days=args.retention_days)
    for candidate in output_dir.glob("irma-*.dump"):
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
        if modified < cutoff:
            candidate.unlink()
    print(destination)


if __name__ == "__main__":
    main()
