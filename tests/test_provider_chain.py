from datetime import UTC, datetime

from irma.providers.base import DataQuality, FundRecord, ProviderMetadata
from irma.providers.chain import FundDataProviderChain


def record(source: str) -> FundRecord:
    now = datetime.now(UTC)
    return FundRecord(
        external_id="OFFICIAL-1",
        name_fa="صندوق رسمی",
        symbol=None,
        fund_type="fixed_income",
        is_etf=False,
        inception_date=None,
        nav=1000,
        market_price=None,
        volume=None,
        trade_value=None,
        total_net_assets=None,
        manager=None,
        market_maker=None,
        is_active=True,
        asset_allocation={},
        metadata=ProviderMetadata(
            source_name=source,
            source_identifier="official:file",
            fetched_at=now,
            observed_at=now,
            unit="IRR",
            quality=DataQuality.VALID,
        ),
    )


class Broken:
    def fetch(self) -> list[FundRecord]:
        raise OSError("unavailable")


class OfficialFile:
    def fetch(self) -> list[FundRecord]:
        return [record("official-file")]


def test_chain_falls_back_without_losing_provenance() -> None:
    chain = FundDataProviderChain([("fipiran", Broken()), ("official-file", OfficialFile())])
    records = chain.fetch()
    assert records[0].metadata.source_name == "official-file"
    assert chain.last_result is not None
    assert chain.last_result.status == "official_file"
    assert chain.last_result.errors == ["fipiran: OSError"]
