"""Bot API routes — authenticated via X-Bot-Key header.

All endpoints in this router are intended for use by the Discord bot
(a separate repository).  They accept the shared API key in the
X-Bot-Key header instead of the user-session cookie.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_bot_auth
from app.database import get_db
from app.models.campaign import Campaign, CampaignMember
from app.models.platform_link import PlatformLink, PlatformType
from app.models.session import Session, SessionStatus
from app.models.session_attendance import SessionAttendance
from app.models.timeslot import TimeSlot
from app.models.user import User
from app.services import attendance_service, session_service

router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────

class UpcomingSessionItem(BaseModel):
    session_id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_name: str
    title: str | None
    confirmed_time: datetime
    webhook_url: str | None

    model_config = {"from_attributes": True}


class LinkedUserItem(BaseModel):
    user_id: uuid.UUID
    display_name: str
    discord_user_id: str

    model_config = {"from_attributes": True}


class BotVoteRequest(BaseModel):
    discord_user_id: str
    availability: str  # "yes" | "maybe" | "no"


class BotAttendanceRequest(BaseModel):
    attended: bool


class TranscriptRequest(BaseModel):
    recording_url: str | None = None
    transcript: str
    summary: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/bot/sessions/upcoming", response_model=list[UpcomingSessionItem])
async def bot_upcoming_sessions(
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> list[UpcomingSessionItem]:
    """Return confirmed sessions in the next 7 days.

    The bot uses this to schedule voice-channel joins and post vote messages.
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=7)

    rows = await db.execute(
        select(Session, Campaign)
        .join(Campaign, Campaign.id == Session.campaign_id)
        .where(
            Session.status == SessionStatus.confirmed,
            Session.confirmed_time >= now,
            Session.confirmed_time <= window_end,
        )
        .order_by(Session.confirmed_time)
    )

    result = []
    for session, campaign in rows:
        result.append(
            UpcomingSessionItem(
                session_id=session.id,
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                title=session.title,
                confirmed_time=session.confirmed_time,
                webhook_url=campaign.discord_webhook_url,
            )
        )
    return result


@router.get(
    "/bot/campaigns/{campaign_id}/linked-users",
    response_model=list[LinkedUserItem],
)
async def bot_linked_users(
    campaign_id: uuid.UUID,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> list[LinkedUserItem]:
    """Return all campaign members who have a Discord platform link."""
    rows = await db.execute(
        select(User, PlatformLink)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .join(
            PlatformLink,
            (PlatformLink.user_id == User.id)
            & (PlatformLink.platform == PlatformType.discord),
        )
        .where(CampaignMember.campaign_id == campaign_id)
    )
    return [
        LinkedUserItem(
            user_id=user.id,
            display_name=user.effective_display_name,
            discord_user_id=link.platform_user_id,
        )
        for user, link in rows
    ]


@router.put("/bot/sessions/{session_id}/timeslots/{slot_id}/vote")
async def bot_submit_vote(
    session_id: uuid.UUID,
    slot_id: uuid.UUID,
    data: BotVoteRequest,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit a vote on behalf of a Discord user.

    Looks up the Questboard user by their Discord ID, then calls the
    same vote service used by the web frontend.
    """
    from app.services import vote_service

    link = await db.scalar(
        select(PlatformLink).where(
            PlatformLink.platform == PlatformType.discord,
            PlatformLink.platform_user_id == data.discord_user_id,
        )
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Questboard user linked to that Discord ID",
        )

    # Validate availability value
    from app.models.vote import Availability
    try:
        availability = Availability(data.availability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid availability value: {data.availability}",
        )

    slot = await db.get(TimeSlot, slot_id)
    if slot is None or slot.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time slot not found")

    vote = await vote_service.upsert_vote(db, slot, link.user_id, availability)
    return {"detail": "Vote recorded", "vote_id": str(vote.id)}


@router.put("/bot/sessions/{session_id}/attendance/{discord_user_id}")
async def bot_set_attendance(
    session_id: uuid.UUID,
    discord_user_id: str,
    data: BotAttendanceRequest,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a Discord user as attended/not attended."""
    link = await db.scalar(
        select(PlatformLink).where(
            PlatformLink.platform == PlatformType.discord,
            PlatformLink.platform_user_id == discord_user_id,
        )
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Questboard user linked to that Discord ID",
        )

    await attendance_service.upsert_attendance(db, session_id, link.user_id, data.attended)
    return {"detail": "Attendance recorded"}


@router.post("/bot/sessions/{session_id}/transcript")
async def bot_post_transcript(
    session_id: uuid.UUID,
    data: TranscriptRequest,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a transcript and summary for a session."""
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if data.recording_url is not None:
        session.recording_url = data.recording_url
    session.transcript = data.transcript
    session.summary = data.summary
    session.transcript_updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"detail": "Transcript saved"}
