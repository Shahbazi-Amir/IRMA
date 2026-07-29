"""Boundary for future verified market-data providers."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MarketObservation:
    """One sourced market observation."""

    symbol: str
    value: float
    observed_at: datetime
    source: str


class MarketDataProvider(Protocol):
    """Protocol implemented by future verified Iranian data providers."""

    def latest(self, symbol: str) -> MarketObservation | None:
        """Return the latest sourced observation, or None when unavailable."""

        ...
