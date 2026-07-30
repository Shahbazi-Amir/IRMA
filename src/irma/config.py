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
    fund_provider: str = Field(default="csv", pattern="^(csv|fipiran)$")
    fipiran_base_url: str = "https://www.fipiran.com/services"
    fund_history_limit: int = Field(default=25, ge=0, le=500)
    provider_min_interval_seconds: float = Field(default=0.25, ge=0, le=10)
    refresh_enabled: bool = False
    refresh_interval_minutes: int = Field(default=1440, ge=15)
    provider_timeout_seconds: int = Field(default=15, ge=1, le=120)
    provider_max_retries: int = Field(default=2, ge=0, le=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
