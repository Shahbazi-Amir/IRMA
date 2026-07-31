"""Ordered, provenance-preserving provider fallback."""

from __future__ import annotations

from dataclasses import dataclass

from irma.providers.base import FundNavRecord, FundProvider, FundRecord, HistoricalFundProvider


@dataclass(frozen=True)
class ProviderChainResult:
    records: list[FundRecord]
    status: str
    provider: str
    errors: list[str]


class FundDataProviderChain:
    """Use the first provider returning a non-empty validated dataset."""

    def __init__(self, providers: list[tuple[str, FundProvider]]) -> None:
        self.providers = providers
        self.last_result: ProviderChainResult | None = None
        self.selected_provider: FundProvider | None = None

    def fetch(self) -> list[FundRecord]:
        errors: list[str] = []
        for index, (name, provider) in enumerate(self.providers):
            try:
                records = provider.fetch()
                if not records:
                    raise ValueError("empty dataset")
                self.last_result = ProviderChainResult(
                    records=records,
                    status="live" if index == 0 else "official_file",
                    provider=name,
                    errors=errors,
                )
                self.selected_provider = provider
                return records
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(f"{name}: {type(exc).__name__}")
        self.last_result = ProviderChainResult([], "unavailable", "", errors)
        raise RuntimeError("all fund providers unavailable: " + ", ".join(errors))

    def fetch_nav_history(self, external_id: str) -> list[FundNavRecord]:
        """Delegate history only when the selected source supports it."""
        if isinstance(self.selected_provider, HistoricalFundProvider):
            return self.selected_provider.fetch_nav_history(external_id)
        return []

    def close(self) -> None:
        """Close providers that own network clients."""
        for _, provider in self.providers:
            close = getattr(provider, "close", None)
            if callable(close):
                close()
