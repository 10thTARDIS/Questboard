"""ORM model for admin-configurable application settings.

A generic key/value store for site-wide configuration that admins can
change without redeployment.  Current keys:

  smtp_config              — JSONB: {host, port, username, password, from_address}
  default_discord_webhook  — str: global fallback Discord webhook URL
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    """A single admin-configurable key/value setting."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict | None] = mapped_column(
        JSONB(astext_type=Text()), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
