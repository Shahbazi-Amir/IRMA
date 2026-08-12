"""Minimal configurable refresh scheduler."""

import logging
import random
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from irma.config import get_settings
from irma.persistence.database import SessionLocal
from irma.persistence.models import RefreshControl
from irma.services.adaptive_refresh import (
    AdaptivePlanner,
    observations,
    prune_telemetry,
)
from irma.services.data_refresh import refresh_from_settings

logger = logging.getLogger(__name__)


def run() -> None:
    settings = get_settings()
    if not settings.refresh_enabled:
        logger.warning("scheduler disabled; set IRMA_REFRESH_ENABLED=true to enable")
        return
    while True:
        with SessionLocal() as session:
            try:
                refresh_from_settings(session, settings)
            except (OSError, RuntimeError, ValueError):
                logger.exception("scheduled refresh failed; last healthy data remains available")
            now = datetime.now(UTC)
            items = observations(
                session,
                provider="fipiran",
                since=now - timedelta(days=settings.refresh_adaptive_lookback_days),
            )
            planner = AdaptivePlanner(
                minimum_samples=settings.refresh_minimum_samples,
                exploration_percent=settings.refresh_exploration_percent,
            )
            buckets = planner.select_daily(
                planner.scores(items),
                targets=settings.refresh_targets_per_day,
                minimum_spacing_hours=settings.refresh_minimum_spacing_hours,
                rng=random.Random(),
            )
            local_now = now.astimezone(ZoneInfo(settings.refresh_timezone))
            candidates = []
            for bucket in buckets:
                candidate = local_now.replace(hour=bucket, minute=0, second=0, microsecond=0)
                candidate += timedelta(minutes=random.randint(0, settings.refresh_jitter_minutes))
                if candidate <= local_now:
                    candidate += timedelta(days=1)
                candidates.append(candidate.astimezone(UTC))
            next_at = min(candidates)
            control = session.get(RefreshControl, "fipiran") or RefreshControl(provider="fipiran")
            session.add(control)
            control.next_scheduled_at = next_at
            session.commit()
            prune_telemetry(
                session,
                before=now - timedelta(days=settings.refresh_telemetry_retention_days),
            )
            logger.info(
                "adaptive refresh scheduled",
                extra={"next_scheduled_at": next_at.isoformat(), "buckets": buckets},
            )
        time.sleep(max(1.0, (next_at - datetime.now(UTC)).total_seconds()))


if __name__ == "__main__":
    run()
