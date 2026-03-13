"""ORM model for authenticated users.

Users are identified by their OIDC subject claim (sub) together with the
issuer URL.  This allows the same application to accept tokens from
multiple providers while guaranteeing globally unique user records.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """An authenticated user, keyed on (oidc_issuer, oidc_sub)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Keyed on (oidc_issuer, oidc_sub) together — multiple providers can share
    # the same sub value, so uniqueness is per-issuer.
    oidc_sub: Mapped[str] = mapped_column(Text, nullable=False)
    oidc_issuer: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("oidc_sub", "oidc_issuer", name="uq_users_oidc_sub_issuer"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    campaign_memberships: Mapped[list["CampaignMember"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    created_sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="creator", foreign_keys="Session.created_by"
    )
    votes: Mapped[list["Vote"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
