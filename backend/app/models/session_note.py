"""ORM model for per-user session notes.

Each user can write one private note per session.  Notes are upserted
(created on first write, updated on subsequent writes).  They are private
by default — only the author can read or update their own note.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionNote(Base):
    """A private note written by one user about one session."""

    __tablename__ = "session_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_session_notes_session_user"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    session: Mapped["Session"] = relationship(  # noqa: F821
        back_populates="notes"
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="session_notes"
    )
