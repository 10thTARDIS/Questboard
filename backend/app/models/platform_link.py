"""ORM model for user platform account links.

Stores Discord/Matrix account IDs linked to a Questboard user.
Used in v2.0 by the Discord bot for reaction-based voting and
attendance detection.  The table exists in v1.0 but has no UI or
endpoints yet — v2.0 bot integration will populate it.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlatformType(str, enum.Enum):
    discord = "discord"
    matrix = "matrix"


class PlatformLink(Base):
    """A linked external-platform account for a user."""

    __tablename__ = "platform_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[PlatformType] = mapped_column(
        SAEnum(PlatformType, name="platformtype"), nullable=False
    )
    platform_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_platform_links_user_platform"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="platform_links"
    )
