"""
Application configuration using pydantic-settings.

Reads from environment variables and .env file.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Leads Enrichment Pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/leads_enrichment"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/leads_enrichment"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ──
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── OpenAI ──
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"

    # ── External Enrichment APIs ──
    GOOGLE_NEWS_API_KEY: str = ""
    GOOGLE_NEWS_API_URL: str = "https://newsapi.org/v2/everything"

    LUSHA_API_KEY: str = ""
    LUSHA_API_URL: str = "https://api.lusha.com/person"

    CLEARBIT_API_KEY: str = ""
    CLEARBIT_API_URL: str = "https://company.clearbit.com/v2/companies/find"

    HUNTER_API_KEY: str = ""
    HUNTER_API_URL: str = "https://api.hunter.io/v2/domain-search"

    # ── App ──
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"


# Singleton instance
settings = Settings()
