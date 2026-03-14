"""ORM model for session attendance records.

GMs mark which campaign members actually attended a completed session.
In v2.0 the Discord recording bot will also be able to set attendance
automatically via the same PUT endpoint it would call with GM credentials.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionAttendance(Base):
    """A record of whether a user attended a particular session."""

    __tablename__ = "session_attendance"

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
    attended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    noted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id", "user_id", name="uq_session_attendance_session_user"
        ),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    session: Mapped["Session"] = relationship(  # noqa: F821
        back_populates="attendance"
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="attendance_records"
    )
