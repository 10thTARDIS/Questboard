"""Application settings business logic.

Provides a generic key/value store (backed by the app_settings table) and
typed helpers for specific settings like SMTP config and the global Discord
webhook fallback URL.
"""

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

# ── Setting keys ───────────────────────────────────────────────────────────────

KEY_SMTP = "smtp_config"
KEY_DISCORD_WEBHOOK = "default_discord_webhook"


# ── Generic get/set ────────────────────────────────────────────────────────────

async def get_setting(db: AsyncSession, key: str) -> dict | None:
    """Return the raw JSON value for a key, or None if not set."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_setting(db: AsyncSession, key: str, value: dict | None) -> AppSetting:
    """Upsert a key/value setting."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = AppSetting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(setting)
    return setting


# ── Typed helpers ──────────────────────────────────────────────────────────────

@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_address: str
    use_tls: bool = True


async def get_smtp_config(db: AsyncSession) -> SmtpConfig | None:
    """Return SMTP config from the database, or None if not configured."""
    value = await get_setting(db, KEY_SMTP)
    if not value or not value.get("host"):
        return None
    return SmtpConfig(
        host=value["host"],
        port=int(value.get("port", 587)),
        username=value.get("username", ""),
        password=value.get("password", ""),
        from_address=value.get("from_address", ""),
        use_tls=bool(value.get("use_tls", True)),
    )


async def get_discord_webhook_fallback(db: AsyncSession) -> str | None:
    """Return the global Discord webhook URL.

    Checks the database first; falls back to the DEFAULT_DISCORD_WEBHOOK_URL
    environment variable so existing deployments keep working.
    """
    value = await get_setting(db, KEY_DISCORD_WEBHOOK)
    if value and value.get("url"):
        return value["url"]
    return os.environ.get("DEFAULT_DISCORD_WEBHOOK_URL")
