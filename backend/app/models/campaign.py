"""ORM models for campaigns and campaign membership.

A Campaign is the top-level grouping for TTRPG play.  Each campaign has
one or more CampaignMembers — one GM who administers it and any number of
players.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Text, func
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
    guild_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_channel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_code: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_offsets_minutes: Mapped[list[int] | None] = mapped_column(
        JSONB(astext_type=Text()), nullable=True
    )
    # Vote notification mode: "each_vote" | "all_voted" | None (disabled)
    vote_notification_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Auto-close voting after this many hours (None = never auto-close)
    vote_auto_close_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recap_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
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
    milestones: Mapped[list["Milestone"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    lore_entries: Mapped[list["LoreEntry"]] = relationship(  # noqa: F821
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
    character_sheet_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_sheet_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="campaign_memberships"
    )
