"""ORM model for player availability votes on session time slots.

Votes are used exclusively by vote-mode sessions.  Each user may cast at
most one vote per time slot (enforced by the uq_votes_slot_user
unique constraint).

Scoring used by the VotingGrid component and displayed to the GM:
  yes   = +2 points
  maybe = +1 point
  no    =  0 points
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Availability(str, enum.Enum):
    """A player's availability for a proposed time slot."""

    yes = "yes"     # Can definitely make it (+2 points)
    maybe = "maybe" # Might be able to make it (+1 point)
    no = "no"       # Cannot make it (0 points)


class Vote(Base):
    """One user's availability response for a specific time slot."""

    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("time_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    availability: Mapped[Availability] = mapped_column(
        SAEnum(Availability, name="availability"), nullable=False
    )
    # updated_at has a server default for INSERT; the service layer must set
    # this explicitly on UPDATE (e.g. vote.updated_at = datetime.now(UTC)).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("time_slot_id", "user_id", name="uq_votes_slot_user"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    time_slot: Mapped["TimeSlot"] = relationship(  # noqa: F821
        back_populates="votes"
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="votes"
    )
