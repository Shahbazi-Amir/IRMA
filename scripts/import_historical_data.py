"""Download and import reproducible public historical datasets into the configured DB."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from irma.persistence.database import build_engine
from irma.services.world_bank_import import DATASETS, WORLD_BANK_API, import_world_bank_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=[*DATASETS, "all"], default="all")
    parser.add_argument("--all", action="store_true", help="Import every configured dataset")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    selected = list(DATASETS) if args.all or args.dataset == "all" else [args.dataset]
    reports = []
    with tempfile.TemporaryDirectory(prefix="irma-historical-") as temporary:
        temp = Path(temporary)
        with Session(build_engine(args.database_url)) as session:
            for dataset_id in selected:
                config = DATASETS[dataset_id]
                source = (
                    args.source_dir / f"{dataset_id}.json"
                    if args.source_dir
                    else temp / f"{dataset_id}.json"
                )
                if not args.source_dir:
                    url = WORLD_BANK_API.format(indicator=config["indicator"])
                    response = httpx.get(
                        url,
                        params={"format": "json", "per_page": 1000},
                        timeout=60,
                        follow_redirects=True,
                    )
                    response.raise_for_status()
                    source.write_bytes(response.content)
                reports.append(import_world_bank_file(session, source, dataset_id))
    output = json.dumps(reports, ensure_ascii=False, indent=2, default=str)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
