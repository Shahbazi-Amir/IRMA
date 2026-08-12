import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.config import Settings
from irma.persistence.models import DataSource, RefreshControl, RefreshTelemetry
from irma.services.adaptive_refresh import (
    AdaptivePlanner,
    acquire_lease,
    freshness_decision,
    record_outcome,
    release_lease,
    retry_delay,
    status_payload,
)

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


def observation(
    bucket: int,
    *,
    status: str = "success",
    timeout: bool = False,
    latency: int = 1000,
) -> RefreshTelemetry:
    return RefreshTelemetry(
        provider="fipiran",
        bucket=bucket,
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=1),
        status=status,
        timeout=timeout,
        latency_ms=latency,
        history_success_ratio=Decimal("1"),
    )


def test_bootstrap_is_spaced_and_reports_insufficient_samples(session: Session) -> None:
    planner = AdaptivePlanner(minimum_samples=4)
    scores = planner.scores([])
    assert planner.select_daily(
        scores, targets=3, minimum_spacing_hours=5, rng=random.Random(1)
    ) == [6, 14, 22]
    payload = status_payload(session, Settings(), now=NOW)
    assert payload["adaptive_confidence"] == "insufficient"
    assert payload["data_freshness"] == "never_synced"
    assert payload["application_status"] == "healthy"


def test_reliable_morning_beats_unreliable_evening_and_degrades() -> None:
    planner = AdaptivePlanner(minimum_samples=4, exploration_percent=0)
    observations = [observation(6) for _ in range(5)] + [
        observation(18, status="failed", timeout=True) for _ in range(5)
    ]
    scores = planner.scores(observations)
    assert scores[6].score is not None and scores[18].score is not None
    assert scores[6].score > scores[18].score
    prior = scores[6].score
    observations.extend(observation(6, status="failed", timeout=True) for _ in range(5))
    assert planner.scores(observations)[6].score < prior


def test_exploration_can_sample_unseen_window_and_jitter_backoff_are_bounded() -> None:
    planner = AdaptivePlanner(minimum_samples=1, exploration_percent=50)
    scores = planner.scores([observation(6)])
    selected = planner.select_daily(
        scores, targets=1, minimum_spacing_hours=1, rng=random.Random(1)
    )
    assert selected != [6]
    assert 0 <= selected[0] <= 23
    assert retry_delay(0) == 1.2
    assert retry_delay(20) == 60.0


def test_persisted_telemetry_survives_planner_restart(session: Session) -> None:
    for _ in range(4):
        session.add(observation(7))
    session.commit()
    persisted = list(session.scalars(select(RefreshTelemetry)))
    scores = AdaptivePlanner(minimum_samples=4).scores(persisted)
    assert scores[7].samples == 4
    assert scores[7].score is not None


def test_db_lease_allows_only_one_logical_refresh(session: Session) -> None:
    owner = acquire_lease(session, provider="fipiran", seconds=60, now=NOW)
    assert owner is not None
    assert acquire_lease(session, provider="fipiran", seconds=60, now=NOW) is None
    release_lease(session, provider="fipiran", owner=owner)
    assert acquire_lease(session, provider="fipiran", seconds=60, now=NOW) is not None


def test_freshness_preserves_source_observation_and_lkg() -> None:
    source = DataSource(
        name="fipiran",
        source_identifier="https://www.fipiran.com",
        source_type="api",
        status="valid",
        last_fetched_at=NOW - timedelta(hours=5),
        last_valid_observation_at=NOW - timedelta(days=1),
    )
    decision = freshness_decision(source, now=NOW, fresh_for=timedelta(hours=3), latest=True)
    assert decision.status == "stale"
    assert decision.should_refresh
    assert decision.last_success_at != decision.source_observed_at


def test_mode_enters_fallback_and_recovers_without_restart(session: Session) -> None:
    for index in range(6):
        started = NOW + timedelta(minutes=index)
        record_outcome(
            session,
            provider="fipiran",
            started_at=started,
            finished_at=started + timedelta(seconds=1),
            status="failed",
            error=TimeoutError("offline"),
        )
    control = session.get(RefreshControl, "fipiran")
    assert control is not None and control.mode == "daily_fallback"
    degraded = status_payload(session, Settings(), now=NOW + timedelta(hours=1))
    assert degraded["application_status"] == "healthy"
    assert degraded["source_status"] == "degraded"
    for index in range(3):
        started = NOW + timedelta(hours=1, minutes=index)
        record_outcome(
            session,
            provider="fipiran",
            started_at=started,
            finished_at=started + timedelta(seconds=1),
            status="success",
        )
    session.refresh(control)
    assert control.mode == "online_preferred"
    assert session.scalar(select(func.count(RefreshTelemetry.id))) == 9
