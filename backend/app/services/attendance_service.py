"""Attendance tracking business logic.

GMs record who attended a completed session.  In v2.0 the Discord recording
bot will call the same PUT endpoint (with a bot token or GM credentials) to
set attendance automatically.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import CampaignMember
from app.models.session_attendance import SessionAttendance
from app.schemas.session import AttendanceEntry


async def get_session_attendance(
    db: AsyncSession, session_id: uuid.UUID, campaign_id: uuid.UUID
) -> list[AttendanceEntry]:
    """Return attendance status for every campaign member.

    Members not yet recorded default to attended=False.
    """
    # Fetch all members of the campaign with their user info
    result = await db.execute(
        select(CampaignMember)
        .where(CampaignMember.campaign_id == campaign_id)
        .options(selectinload(CampaignMember.user))
    )
    members = list(result.scalars().all())

    # Fetch existing attendance records for this session
    att_result = await db.execute(
        select(SessionAttendance).where(
            SessionAttendance.session_id == session_id
        )
    )
    attendance_map: dict[uuid.UUID, bool] = {
        a.user_id: a.attended for a in att_result.scalars().all()
    }

    return [
        AttendanceEntry(
            user_id=m.user_id,
            display_name=m.user.effective_display_name,
            attended=attendance_map.get(m.user_id, False),
        )
        for m in members
    ]


async def upsert_attendance(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    attended: bool,
) -> SessionAttendance:
    """Create or update an attendance record for a (session, user) pair."""
    result = await db.execute(
        select(SessionAttendance).where(
            SessionAttendance.session_id == session_id,
            SessionAttendance.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = SessionAttendance(
            session_id=session_id,
            user_id=user_id,
            attended=attended,
        )
        db.add(record)
    else:
        record.attended = attended
    await db.commit()
    await db.refresh(record)
    return record
