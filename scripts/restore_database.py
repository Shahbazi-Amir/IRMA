"""Restore a PostgreSQL custom-format backup into an explicitly named test database."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target-url", default=os.environ.get("IRMA_RESTORE_DATABASE_URL"))
    args = parser.parse_args()
    if not args.target_url or not args.target_url.startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        raise SystemExit(
            "set --target-url or IRMA_RESTORE_DATABASE_URL to a PostgreSQL test database"
        )
    if "production" in args.target_url.lower():
        raise SystemExit("refusing a target URL containing 'production'")
    target = args.target_url.replace("postgresql+psycopg://", "postgresql://", 1)
    subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--dbname",
            target,
            str(args.backup),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
