"""Coverage and horizon-eligibility audit for normalized historical series."""

from __future__ import annotations

from collections import Counter
from datetime import date
from itertools import pairwise
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from irma.persistence.models import HistoricalObservation, HistoricalSeries

HORIZONS = {"1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095, "5y": 1825}
TOLERANCE = {"daily": 7, "weekly": 14, "monthly": 45, "quarterly": 120, "annual": 400}


def audit_dates(dates: list[date], frequency: str) -> dict[str, Any]:
    if not dates:
        return {"rows": 0, "coverage_start": None, "coverage_end": None, "gaps": 0}
    ordered = sorted(dates)
    expected = {"daily": 7, "weekly": 14, "monthly": 45, "quarterly": 120, "annual": 400}[frequency]
    gaps = sum((right - left).days > expected for left, right in pairwise(ordered))
    duplicate_dates = sum(count - 1 for count in Counter(ordered).values() if count > 1)
    return {
        "rows": len(ordered),
        "coverage_start": ordered[0],
        "coverage_end": ordered[-1],
        "coverage_days": (ordered[-1] - ordered[0]).days,
        "gaps": gaps,
        "duplicate_dates": duplicate_dates,
    }


def eligible_horizons(dates: list[date], frequency: str) -> dict[str, bool]:
    if len(dates) < 3:
        return {name: False for name in HORIZONS}
    coverage = (max(dates) - min(dates)).days
    minimum_samples = {"daily": 20, "weekly": 8, "monthly": 6, "quarterly": 6, "annual": 6}
    return {
        name: (frequency != "annual" or days >= 365)
        and coverage >= days * 2
        and len(dates) >= minimum_samples[frequency]
        for name, days in HORIZONS.items()
    }


def real_return_if_aligned(
    nominal_return: float,
    inflation_return: float,
    *,
    nominal_frequency: str,
    inflation_frequency: str,
) -> float:
    if nominal_frequency != inflation_frequency:
        raise ValueError("nominal and inflation periods are not aligned")
    if inflation_return <= -1:
        raise ValueError("inflation return must exceed -100%")
    return (1 + nominal_return) / (1 + inflation_return) - 1


def audit_historical_database(session: Session) -> list[dict[str, Any]]:
    report = []
    for series in session.scalars(select(HistoricalSeries).order_by(HistoricalSeries.code)):
        rows = list(
            session.scalars(
                select(HistoricalObservation)
                .where(HistoricalObservation.series_id == series.id)
                .order_by(HistoricalObservation.valid_at)
            )
        )
        dates = [row.valid_at for row in rows if row.valid_at is not None]
        audit = audit_dates(dates, series.frequency)
        report.append(
            {
                "dataset": series.code,
                "name_fa": series.name_fa,
                "frequency": series.frequency,
                "unit": series.unit,
                **audit,
                "eligible_horizons": eligible_horizons(dates, series.frequency),
                "quality": "valid"
                if rows and all(row.quality_status == "valid" for row in rows)
                else "insufficient",
            }
        )
    return report
