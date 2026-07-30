"""Documented data-quality rules and recommendation gating."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class QualityFinding:
    rule_code: str
    severity: Severity
    message: str

    @property
    def recommendation_allowed(self) -> bool:
        return self.severity in {Severity.INFO, Severity.WARNING}


def validate_ohlcv(
    *,
    open_price: float | None,
    high_price: float | None,
    low_price: float | None,
    close_price: float | None,
) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    values = [
        value for value in (open_price, high_price, low_price, close_price) if value is not None
    ]
    if not values:
        return [QualityFinding("missing_price", Severity.ERROR, "No price is available.")]
    if any(value <= 0 for value in values):
        findings.append(
            QualityFinding("impossible_price", Severity.CRITICAL, "Price must be positive.")
        )
    if high_price is not None and low_price is not None and high_price < low_price:
        findings.append(QualityFinding("invalid_range", Severity.ERROR, "High is below low."))
    if high_price is not None and close_price is not None and close_price > high_price:
        findings.append(
            QualityFinding("close_outside_range", Severity.ERROR, "Close exceeds high.")
        )
    if low_price is not None and close_price is not None and close_price < low_price:
        findings.append(
            QualityFinding("close_outside_range", Severity.ERROR, "Close is below low.")
        )
    return findings
