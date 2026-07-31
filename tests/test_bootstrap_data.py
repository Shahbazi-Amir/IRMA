from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from irma.persistence.models import Fund, FundNavHistory


def test_bootstrap_empty_database_is_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "funds.csv"
    csv_path.write_text(
        "external_id,name_fa,fund_type,source_identifier,observed_at,nav\n"
        "BOOT-1,صندوق بوت‌استرپ,fixed_income,official:test,"
        "2026-07-01T12:00:00+00:00,1000\n",
        encoding="utf-8",
    )
    database = tmp_path / "bootstrap.db"
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "IRMA_APP_ENV": "test",
        "IRMA_DATABASE_URL": f"sqlite:///{database}",
        "IRMA_FUND_PROVIDER": "csv",
        "IRMA_FUND_CSV_PATH": str(csv_path),
        "IRMA_FUND_HISTORY_LIMIT": "0",
    }
    first = subprocess.run(
        [sys.executable, "scripts/bootstrap_data.py"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [sys.executable, "scripts/bootstrap_data.py"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        assert session.scalar(select(func.count(Fund.id))) == 1
        assert session.scalar(select(func.count(FundNavHistory.id))) == 1
    engine.dispose()
