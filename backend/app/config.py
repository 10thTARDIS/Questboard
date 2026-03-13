"""Application configuration.

Settings are loaded from environment variables (or a .env file in the
working directory).  pydantic-settings performs type coercion and
validation automatically.  The module exposes a single cached singleton
`settings` that should be imported everywhere.
"""

from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings, sourced from environment variables.

    See .env.example for required and optional variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_url: str = "http://localhost:8000"
    secret_key: str
    invite_code: str = ""

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str  # postgresql+asyncpg://... (used by the app)
    database_migrate_url: str  # postgresql://...  (used by Alembic)

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── OIDC ───────────────────────────────────────────────────────────────────
    oidc_discovery_url: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str

    # ── Notifications ──────────────────────────────────────────────────────────
    default_discord_webhook_url: str = ""

    # ── Celery ─────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Session ────────────────────────────────────────────────────────────────
    session_ttl_seconds: int = 8 * 3600  # 8 hours


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    The @lru_cache ensures the .env file is only parsed once per process.
    Call get_settings.cache_clear() in tests to force re-reads.
    """
    return Settings()


# Module-level singleton — import this everywhere instead of calling get_settings().
settings = get_settings()
