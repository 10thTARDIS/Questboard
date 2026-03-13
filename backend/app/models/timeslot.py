"""ORM model for proposed time slots within a session.

Each Session can have 1–5 TimeSlots.  For vote-mode sessions, players
cast Votes against each slot to indicate their availability.  The GM
then picks the winning slot when confirming the session.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimeSlot(Base):
    """A single candidate date/time for a session."""

    __tablename__ = "time_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposed_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    session: Mapped["Session"] = relationship(  # noqa: F821
        back_populates="time_slots"
    )
    votes: Mapped[list["Vote"]] = relationship(  # noqa: F821
        back_populates="time_slot", cascade="all, delete-orphan"
    )
