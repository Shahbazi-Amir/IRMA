"""Backfill live FIPIRAN NAV history with checkpoints."""

from __future__ import annotations

import argparse
from datetime import date

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.providers.fipiran import FipiranFundProvider
from irma.services.fund_backfill import backfill_fund_history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--fund-type")
    parser.add_argument("--resume", metavar="RUN_ID")
    parser.add_argument("--from-date", type=date.fromisoformat)
    args = parser.parse_args()
    settings = get_settings()
    with (
        FipiranFundProvider(
            base_url=settings.fipiran_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            min_interval_seconds=settings.provider_min_interval_seconds,
            catalog_path=settings.fipiran_catalog_path,
            history_path=settings.fipiran_history_path,
            user_agent=settings.fipiran_user_agent,
            failure_threshold=settings.provider_circuit_failures,
            cooldown_seconds=settings.provider_circuit_cooldown_seconds,
            retries=settings.provider_max_retries,
        ) as provider,
        SessionLocal() as session,
    ):
        print(
            backfill_fund_history(
                session,
                provider,
                limit=args.limit,
                fund_type=args.fund_type,
                from_date=args.from_date,
                run_id=args.resume,
            )
        )


if __name__ == "__main__":
    main()
