"""Application settings loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://wizard:wizard@localhost:5432/stockwizard"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://wizard:wizard@localhost:5432/stockwizard"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Auth
    internal_api_token: str = Field(default="dev-token-change-me")

    # Vendor key encryption
    master_key: str = Field(default="")
    master_key_previous: str = Field(default="")

    # Market data
    risk_free_rate: float = Field(default=0.0525)
    default_exchange_tz: str = Field(default="America/New_York")


@lru_cache
def get_settings() -> Settings:
    return Settings()
