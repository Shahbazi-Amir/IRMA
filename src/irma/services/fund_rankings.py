"""Versioned, evidence-gated fund ranking from persisted sourced history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import Fund, FundMetric, FundNavHistory

RANKING_VERSION = "2026.07.2"
MIN_OBSERVATIONS = 90
MAX_STALENESS_DAYS = 7
WEIGHTS = {
    "cagr": 0.25,
    "sharpe": 0.20,
    "maximum_drawdown": 0.20,
    "stability": 0.15,
    "history": 0.10,
    "data_quality": 0.10,
}


def _metric_map(session: Session, fund_id: int) -> dict[str, float | None]:
    rows = session.scalars(select(FundMetric).where(FundMetric.fund_id == fund_id)).all()
    return {row.metric_name: float(row.value) if row.value is not None else None for row in rows}


def rank_funds(session: Session, fund_type: str) -> dict[str, Any]:
    funds = session.scalars(
        select(Fund).where(Fund.fund_type == fund_type, Fund.is_active.is_(True))
    ).all()
    candidates: list[dict[str, Any]] = []
    exclusions: dict[str, int] = {}
    now = datetime.now(UTC)
    for fund in funds:
        history = session.scalars(
            select(FundNavHistory)
            .where(FundNavHistory.fund_id == fund.id, FundNavHistory.nav.is_not(None))
            .order_by(FundNavHistory.valid_at)
        ).all()
        reason = None
        if fund.quality_status != "valid":
            reason = "invalid_quality"
        elif len(history) < MIN_OBSERVATIONS:
            reason = "insufficient_history"
        elif fund.last_data_at is None:
            reason = "missing_timestamp"
        else:
            last_data_at = fund.last_data_at.replace(tzinfo=fund.last_data_at.tzinfo or UTC)
            if (now - last_data_at).days > MAX_STALENESS_DAYS:
                reason = "stale"
        metrics = _metric_map(session, fund.id)
        required = ("cagr", "sharpe", "maximum_drawdown", "positive_period_ratio")
        if reason is None and any(metrics.get(name) is None for name in required):
            reason = "missing_metrics"
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        first_date = history[0].valid_at
        last_date = history[-1].valid_at
        assert first_date is not None and last_date is not None
        age_days = max(1, (last_date - first_date).days)
        cagr = metrics["cagr"] or 0
        sharpe = metrics["sharpe"] or 0
        drawdown = metrics["maximum_drawdown"] or 0
        stability = metrics["positive_period_ratio"] or 0
        quality = metrics.get("data_quality_score") or 0
        components = {
            "cagr": max(-1.0, min(1.0, cagr)),
            "sharpe": max(-1.0, min(2.0, sharpe)) / 2,
            "maximum_drawdown": 1 - min(1.0, abs(drawdown)),
            "stability": stability,
            "history": min(1.0, age_days / (365.25 * 3)),
            "data_quality": quality,
        }
        score = sum(components[name] * WEIGHTS[name] for name in WEIGHTS)
        candidates.append(
            {
                "fund_id": fund.id,
                "name_fa": fund.name_fa,
                "symbol": fund.symbol,
                "fund_type": fund.fund_type,
                "score": round(score, 6),
                "ranking_version": RANKING_VERSION,
                "components": components,
                "observation_count": len(history),
                "history_from": history[0].valid_at,
                "history_to": history[-1].valid_at,
                "quality_status": fund.quality_status,
                "source_id": fund.source_id,
                "last_data_at": fund.last_data_at,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["name_fa"]))
    for position, item in enumerate(candidates, start=1):
        item["rank"] = position
    return {
        "fund_type": fund_type,
        "ranking_version": RANKING_VERSION,
        "weights": WEIGHTS,
        "items": candidates,
        "eligible_count": len(candidates),
        "known_count": len(funds),
        "exclusions": exclusions,
        "data_notice": (
            "Ranking compares only active funds of the same type with at least "
            f"{MIN_OBSERVATIONS} valid observations and fresh sourced data."
        ),
    }
