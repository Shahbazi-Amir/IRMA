"""Persistent, transparent planning and freshness policy for FIPIRAN."""

from __future__ import annotations

import math
import random
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from irma.persistence.models import DataSource, RefreshControl, RefreshTelemetry

TEHRAN = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class FreshnessDecision:
    status: str
    last_success_at: datetime | None
    source_observed_at: datetime | None
    should_refresh: bool
    reason: str


@dataclass(frozen=True)
class BucketScore:
    bucket: int
    samples: int
    success_rate: float
    timeout_rate: float
    median_latency_ms: int | None
    score: float | None


def freshness_decision(
    source: DataSource | None, *, now: datetime, fresh_for: timedelta, latest: bool
) -> FreshnessDecision:
    if source is None or source.last_fetched_at is None:
        return FreshnessDecision("never_synced", None, None, latest, "no valid snapshot")
    age = now - source.last_fetched_at.replace(tzinfo=source.last_fetched_at.tzinfo or UTC)
    fresh = age <= fresh_for
    status = "fresh" if fresh else "stale"
    return FreshnessDecision(
        status,
        source.last_fetched_at,
        source.last_valid_observation_at,
        latest and not fresh,
        "within freshness threshold" if fresh else "snapshot exceeds freshness threshold",
    )


class AdaptivePlanner:
    """Scores hourly Tehran buckets from a bounded rolling observation window."""

    def __init__(self, *, minimum_samples: int = 4, exploration_percent: int = 15) -> None:
        self.minimum_samples = minimum_samples
        self.exploration_percent = exploration_percent

    def scores(self, observations: list[RefreshTelemetry]) -> list[BucketScore]:
        result: list[BucketScore] = []
        for bucket in range(24):
            items = [item for item in observations if item.bucket == bucket]
            successes = [item for item in items if item.status in {"success", "partial_success"}]
            timeouts = [item for item in items if item.timeout]
            latencies = [item.latency_ms for item in successes]
            enough = len(items) >= self.minimum_samples
            success_rate = len(successes) / len(items) if items else 0.0
            timeout_rate = len(timeouts) / len(items) if items else 0.0
            completion = [
                float(item.history_success_ratio)
                for item in successes
                if item.history_success_ratio is not None
            ]
            completion_score = sum(completion) / len(completion) if completion else 1.0
            latency_score = 1 / (1 + (median(latencies) if latencies else 0) / 10_000)
            score = (
                round(
                    0.6 * success_rate
                    + 0.2 * (1 - timeout_rate)
                    + 0.1 * completion_score
                    + 0.1 * latency_score,
                    4,
                )
                if enough
                else None
            )
            result.append(
                BucketScore(
                    bucket,
                    len(items),
                    success_rate,
                    timeout_rate,
                    int(median(latencies)) if latencies else None,
                    score,
                )
            )
        return result

    def select_daily(
        self,
        scores: list[BucketScore],
        *,
        targets: int,
        minimum_spacing_hours: int,
        rng: random.Random,
    ) -> list[int]:
        eligible = [item for item in scores if item.score is not None]
        bootstrap = [6, 14, 22]
        ranked = sorted(eligible, key=lambda item: (-float(item.score or 0), item.bucket))
        if not ranked:
            return bootstrap[:targets]
        if rng.randrange(100) < self.exploration_percent:
            unseen = [item for item in scores if item.score is None]
            if unseen:
                ranked = [rng.choice(unseen), *ranked]
        chosen: list[int] = []
        for item in ranked + [scores[bucket] for bucket in bootstrap]:
            distance = (
                min(min((item.bucket - other) % 24, (other - item.bucket) % 24) for other in chosen)
                if chosen
                else 24
            )
            if item.bucket not in chosen and distance >= minimum_spacing_hours:
                chosen.append(item.bucket)
            if len(chosen) == targets:
                break
        return sorted(chosen)


def retry_delay(
    attempt: int, *, base: float = 1.0, maximum: float = 60.0, jitter: float = 0.2
) -> float:
    return float(min(maximum, base * 2**attempt * (1 + jitter)))


def acquire_lease(session: Session, *, provider: str, seconds: int, now: datetime) -> str | None:
    owner = f"{socket.gethostname()}:{random.getrandbits(48):012x}"
    control = session.get(RefreshControl, provider)
    if control is None:
        control = RefreshControl(provider=provider)
        session.add(control)
        session.commit()
    result = session.execute(
        update(RefreshControl)
        .where(
            RefreshControl.provider == provider,
            (RefreshControl.lease_expires_at.is_(None)) | (RefreshControl.lease_expires_at <= now),
        )
        .values(lease_owner=owner, lease_expires_at=now + timedelta(seconds=seconds))
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return owner if cast(CursorResult[Any], result).rowcount == 1 else None


def release_lease(session: Session, *, provider: str, owner: str) -> None:
    session.execute(
        update(RefreshControl)
        .where(RefreshControl.provider == provider, RefreshControl.lease_owner == owner)
        .values(lease_owner=None, lease_expires_at=None)
    )
    session.commit()


def record_outcome(
    session: Session,
    *,
    provider: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    error: Exception | None = None,
    history_success_ratio: float | None = None,
    retry_count: int = 0,
) -> None:
    category = type(error).__name__ if error else None
    session.add(
        RefreshTelemetry(
            provider=provider,
            bucket=started_at.astimezone(TEHRAN).hour,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            failure_category=category,
            timeout=bool(category and "timeout" in category.lower()),
            latency_ms=max(0, math.ceil((finished_at - started_at).total_seconds() * 1000)),
            history_success_ratio=history_success_ratio,
            retry_count=retry_count,
        )
    )
    control = session.get(RefreshControl, provider) or RefreshControl(
        provider=provider,
        mode="online_preferred",
        consecutive_failures=0,
        consecutive_successes=0,
    )
    session.add(control)
    control.last_attempt_at = finished_at
    if status in {"success", "partial_success"}:
        control.last_success_at = finished_at
        control.consecutive_successes = (control.consecutive_successes or 0) + 1
        control.consecutive_failures = 0
        control.last_failure_reason = None
        if control.mode == "daily_fallback":
            control.mode = "recovering"
        elif control.mode == "recovering" and control.consecutive_successes >= 3:
            control.mode = "online_preferred"
    else:
        control.last_failure_at = finished_at
        control.last_failure_reason = category
        control.consecutive_failures = (control.consecutive_failures or 0) + 1
        control.consecutive_successes = 0
        if control.consecutive_failures >= 6:
            control.mode = "daily_fallback"
        elif control.consecutive_failures >= 3:
            control.mode = "degraded"
    session.commit()


def observations(session: Session, *, provider: str, since: datetime) -> list[RefreshTelemetry]:
    return list(
        session.scalars(
            select(RefreshTelemetry).where(
                RefreshTelemetry.provider == provider, RefreshTelemetry.started_at >= since
            )
        )
    )


def prune_telemetry(session: Session, *, before: datetime) -> int:
    result = session.execute(delete(RefreshTelemetry).where(RefreshTelemetry.started_at < before))
    session.commit()
    return int(cast(CursorResult[Any], result).rowcount or 0)


def status_payload(
    session: Session, settings: Any, *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    source = session.scalar(select(DataSource).where(DataSource.name == "fipiran"))
    control = session.get(RefreshControl, "fipiran")
    decision = freshness_decision(
        source, now=now, fresh_for=timedelta(minutes=settings.refresh_fresh_minutes), latest=False
    )
    items = observations(
        session,
        provider="fipiran",
        since=now - timedelta(days=settings.refresh_adaptive_lookback_days),
    )
    scores = AdaptivePlanner(
        minimum_samples=settings.refresh_minimum_samples,
        exploration_percent=settings.refresh_exploration_percent,
    ).scores(items)
    source_status = source.status if source else "unavailable"
    if control and control.mode in {"degraded", "daily_fallback", "recovering"}:
        source_status = "degraded"
    return {
        "application_status": "healthy",
        "source_status": source_status,
        "data_freshness": decision.status,
        "mode": control.mode if control else "online_preferred",
        "last_attempt_at": control.last_attempt_at if control else None,
        "last_success_at": decision.last_success_at,
        "last_source_observation_at": decision.source_observed_at,
        "last_failure_at": control.last_failure_at if control else None,
        "last_failure_reason": control.last_failure_reason if control else None,
        "next_scheduled_attempt_at": control.next_scheduled_at if control else None,
        "adaptive_confidence": "insufficient"
        if len(items) < settings.refresh_minimum_samples
        else "low"
        if len(items) < settings.refresh_minimum_samples * 3
        else "medium",
        "buckets": [item.__dict__ for item in scores],
    }
