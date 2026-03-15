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

    # Fire recap email task for opted-in attendees (no-op if SMTP or opt-ins not configured)
    from app.tasks.reminder_tasks import send_recap_email
    send_recap_email.delay(str(session_id))

    return {"detail": "Transcript saved"}


# ── New endpoints for bot ↔ Questboard integration ────────────────────────────

class VoteCounts(BaseModel):
    yes: int = 0
    maybe: int = 0
    no: int = 0


class TimeSlotDetail(BaseModel):
    slot_id: uuid.UUID
    proposed_time: datetime
    vote_counts: VoteCounts


class SessionTimeslotsResponse(BaseModel):
    session_id: uuid.UUID
    campaign_name: str
    game_system: str | None
    reminder_offsets_minutes: list[int] | None
    slots: list[TimeSlotDetail]


@router.get("/bot/sessions/{session_id}/timeslots", response_model=SessionTimeslotsResponse)
async def bot_session_timeslots(
    session_id: uuid.UUID,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> SessionTimeslotsResponse:
    """Return time slots with per-slot vote counts and campaign metadata."""
    from app.models.vote import Availability, Vote

    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    campaign = await db.get(Campaign, session.campaign_id)

    slots_result = await db.execute(
        select(TimeSlot).where(TimeSlot.session_id == session_id).order_by(TimeSlot.created_at)
    )
    slots = slots_result.scalars().all()

    slot_details = []
    for slot in slots:
        votes_result = await db.execute(
            select(Vote).where(Vote.time_slot_id == slot.id)
        )
        votes = votes_result.scalars().all()
        counts = VoteCounts(
            yes=sum(1 for v in votes if v.availability == Availability.yes),
            maybe=sum(1 for v in votes if v.availability == Availability.maybe),
            no=sum(1 for v in votes if v.availability == Availability.no),
        )
        slot_details.append(
            TimeSlotDetail(slot_id=slot.id, proposed_time=slot.proposed_time, vote_counts=counts)
        )

    return SessionTimeslotsResponse(
        session_id=session.id,
        campaign_name=campaign.name if campaign else "",
        game_system=campaign.game_system if campaign else None,
        reminder_offsets_minutes=campaign.reminder_offsets_minutes if campaign else None,
        slots=slot_details,
    )


class PlatformLinkDetail(BaseModel):
    user_id: uuid.UUID
    display_name: str


@router.get(
    "/bot/platform-links/{platform}/{platform_user_id}",
    response_model=PlatformLinkDetail,
)
async def bot_platform_link(
    platform: str,
    platform_user_id: str,
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> PlatformLinkDetail:
    """Look up a Questboard user by their platform account ID."""
    try:
        platform_type = PlatformType(platform)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown platform: {platform}",
        )

    row = await db.execute(
        select(PlatformLink, User)
        .join(User, User.id == PlatformLink.user_id)
        .where(
            PlatformLink.platform == platform_type,
            PlatformLink.platform_user_id == platform_user_id,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No linked user found"
        )

    link, user = result
    return PlatformLinkDetail(user_id=user.id, display_name=user.effective_display_name)


class LinkStatusResponse(BaseModel):
    linked: bool
    user_id: uuid.UUID | None = None


@router.get("/bot/link-status/{token}", response_model=LinkStatusResponse)
async def bot_link_status(
    token: str,
    _: None = Depends(require_bot_auth),
) -> LinkStatusResponse:
    """Poll whether a Discord account linking flow has completed."""
    from app.auth.session import consume_discord_link_done

    user_id_str = await consume_discord_link_done(token)
    if user_id_str:
        return LinkStatusResponse(linked=True, user_id=uuid.UUID(user_id_str))
    return LinkStatusResponse(linked=False)


class BotConfigResponse(BaseModel):
    whisper_endpoint_url: str | None = None
    whisper_api_key: str | None = None
    llm_endpoint_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None


@router.get("/bot/settings", response_model=BotConfigResponse)
async def bot_get_settings(
    _: None = Depends(require_bot_auth),
    db: AsyncSession = Depends(get_db),
) -> BotConfigResponse:
    """Return Whisper and LLM configuration for the bot."""
    from app.services.settings_service import get_llm_config, get_whisper_config

    whisper = await get_whisper_config(db)
    llm = await get_llm_config(db)
    return BotConfigResponse(
        whisper_endpoint_url=whisper.endpoint_url if whisper else None,
        whisper_api_key=whisper.api_key if whisper else None,
        llm_endpoint_url=llm.endpoint_url if llm else None,
        llm_api_key=llm.api_key if llm else None,
        llm_model=llm.model if llm else None,
    )


class LinkingTokenRequest(BaseModel):
    token: str
    discord_user_id: str


@router.post("/bot/linking-tokens", status_code=status.HTTP_201_CREATED)
async def bot_store_linking_token(
    data: LinkingTokenRequest,
    _: None = Depends(require_bot_auth),
) -> dict:
    """Store a one-time Discord account linking token generated by the bot."""
    from app.auth.session import store_discord_link_token

    await store_discord_link_token(data.token, data.discord_user_id)
    return {"detail": "ok"}
