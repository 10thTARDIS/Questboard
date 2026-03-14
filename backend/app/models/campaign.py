"""ORM models for campaigns and campaign membership.

A Campaign is the top-level grouping for TTRPG play.  Each campaign has
one or more CampaignMembers — one GM who administers it and any number of
players.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MemberRole(str, enum.Enum):
    """Role a user holds within a campaign."""

    gm = "gm"          # Game Master — full administrative access
    player = "player"  # Regular player — read/vote access only


class Campaign(Base):
    """A TTRPG campaign with its members, sessions, and optional Discord integration."""

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    game_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discord_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_code: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_offsets_minutes: Mapped[list[int] | None] = mapped_column(
        JSONB(astext_type=Text()), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    members: Mapped[list["CampaignMember"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignMember(Base):
    """Join table linking a User to a Campaign with a role.

    The primary key is (campaign_id, user_id) — a user can only hold one
    role per campaign.
    """

    __tablename__ = "campaign_members"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[MemberRole] = mapped_column(
        SAEnum(MemberRole, name="memberrole"), nullable=False
    )
    character_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="campaign_memberships"
    )
