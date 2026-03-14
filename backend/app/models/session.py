"""ORM models for game sessions and their scheduling lifecycle.

The Session model captures a single planned game event.  Its lifecycle is
driven by SchedulingMode and SessionStatus:

  vote      → proposed → (players vote) → confirmed
  direct    → confirmed  (immediately, no voting needed)
  tentative → proposed  → confirmed
  any       → cancelled  (at any proposed/confirmed stage)
  any       → completed  (manually set after the session occurs)

Celery task IDs for pending reminder notifications are stored in JSONB
so they can be revoked if the session is rescheduled or cancelled.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SchedulingMode(str, enum.Enum):
    """How a session is scheduled and confirmed."""

    vote = "vote"           # Multiple candidate slots; players vote; GM confirms winner
    direct = "direct"       # Single slot; session is confirmed on creation
    tentative = "tentative" # Single slot; stays proposed until GM manually confirms


class SessionStatus(str, enum.Enum):
    """Current lifecycle state of a session."""

    proposed = "proposed"     # Created but not yet confirmed
    confirmed = "confirmed"   # Time is locked in; reminders are scheduled
    completed = "completed"   # Session has taken place
    cancelled = "cancelled"   # Session will not happen


class Session(Base):
    """A single planned game session within a campaign."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduling_mode: Mapped[SchedulingMode] = mapped_column(
        SAEnum(SchedulingMode, name="schedulingmode"), nullable=False
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="sessionstatus"),
        nullable=False,
        server_default=text("'proposed'"),
    )
    confirmed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Celery task IDs for scheduled reminders; stored so they can be revoked on
    # reschedule or cancellation.  Schema: ["task_id_7d", "task_id_24h", "task_id_1h"]
    celery_task_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="sessions"
    )
    creator: Mapped["User"] = relationship(  # noqa: F821
        back_populates="created_sessions", foreign_keys=[created_by]
    )
    time_slots: Mapped[list["TimeSlot"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
    notes: Mapped[list["SessionNote"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
