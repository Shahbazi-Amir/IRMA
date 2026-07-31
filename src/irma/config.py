"""Application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from IRMA-prefixed environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IRMA_",
        extra="ignore",
    )

    app_name: str = "IRMA API"
    app_env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite:///./irma.db"
    cors_origins: str = "http://localhost:8501"
    admin_key: str | None = None
    api_base_url: str = "http://localhost:8000"
    fund_csv_path: str = "data/imports/funds.csv"
    market_index_csv_path: str = "data/imports/market_indices.csv"
    instrument_market_csv_path: str = "data/imports/market_instruments.csv"
    inflation_csv_path: str = "data/imports/inflation.csv"
    bank_product_csv_path: str = "data/imports/bank_products.csv"
    fund_provider: str = Field(default="csv", pattern="^(csv|fipiran|chain)$")
    fipiran_base_url: str = "https://www.fipiran.com/services"
    fipiran_contract: str = Field(default="auto", pattern="^(auto|services-v1)$")
    fipiran_catalog_path: str = "fund/fundcompare/"
    fipiran_history_path: str = "chart/getfundchart"
    fipiran_user_agent: str = "IRMA/1.0 (+https://github.com/Shahbazi-Amir/IRMA)"
    fund_history_limit: int = Field(default=25, ge=0, le=500)
    fund_history_all: bool = False
    provider_min_interval_seconds: float = Field(default=0.25, ge=0, le=10)
    provider_circuit_failures: int = Field(default=3, ge=1, le=20)
    provider_circuit_cooldown_seconds: int = Field(default=300, ge=1, le=86400)
    official_fund_file_path: str = "data/imports/official_funds.csv"
    nav_conflict_warning_percent: float = Field(default=0.5, ge=0, le=100)
    nav_conflict_error_percent: float = Field(default=2.0, ge=0, le=100)
    refresh_enabled: bool = False
    refresh_interval_minutes: int = Field(default=1440, ge=15)
    provider_timeout_seconds: int = Field(default=15, ge=1, le=120)
    provider_max_retries: int = Field(default=2, ge=0, le=10)
    fixture_data_enabled: bool = False
    max_upload_bytes: int = Field(default=2_000_000, ge=1_024, le=20_000_000)
    heavy_rate_limit_per_minute: int = Field(default=30, ge=1, le=1_000)

    def fixtures_allowed(self) -> bool:
        """Fixtures are never a production data source."""
        return self.fixture_data_enabled and self.app_env in {"development", "test", "e2e"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
