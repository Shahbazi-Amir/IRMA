"""Minimal configurable refresh scheduler."""

import logging
import time

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.services.data_refresh import refresh_from_configured_csv

logger = logging.getLogger(__name__)


def run() -> None:
    settings = get_settings()
    if not settings.refresh_enabled:
        logger.warning("scheduler disabled; set IRMA_REFRESH_ENABLED=true to enable")
        return
    while True:
        with SessionLocal() as session:
            try:
                refresh_from_configured_csv(
                    session,
                    csv_path=settings.fund_csv_path,
                    max_retries=settings.provider_max_retries,
                )
            except (OSError, ValueError):
                logger.exception("scheduled refresh failed; last healthy data remains available")
        time.sleep(settings.refresh_interval_minutes * 60)


if __name__ == "__main__":
    run()
