"""Explicit unavailable adapters for sources requiring future legal and technical review."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnavailableProvider:
    name: str
    reason: str
    manual_format: str | None = None

    def status(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "status": "missing",
            "reason": self.reason,
            "manual_format": self.manual_format,
        }


PROVIDERS = [
    UnavailableProvider(
        "central-bank-rates",
        "No stable machine-readable adapter is configured in this release.",
        "bank-products.csv",
    ),
    UnavailableProvider(
        "statistical-centre-inflation",
        "No stable machine-readable adapter is configured in this release.",
        "economic-indicators.csv",
    ),
    UnavailableProvider(
        "real-estate",
        "City and district coverage requires a separately validated data source.",
        "real-estate.csv",
    ),
    UnavailableProvider(
        "foreign-exchange",
        "No legally and technically stable automatic source is configured.",
        "fx.csv",
    ),
]
