"""Print a product/engineering coverage report for normalized historical datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from irma.persistence.database import build_engine
from irma.services.historical_audit import audit_historical_database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with Session(build_engine(args.database_url)) as session:
        output = json.dumps(
            audit_historical_database(session), ensure_ascii=False, indent=2, default=str
        )
        if args.report:
            args.report.write_text(output + "\n", encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
