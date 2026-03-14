"""Session API routes.

Campaign-scoped:  POST/GET /api/campaigns/{campaign_id}/sessions
Session-scoped:   GET/PATCH/DELETE/POST /api/sessions/{session_id}[/confirm]
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    get_session_for_gm,
    get_session_for_member,
    require_campaign_member,
    require_gm,
)
from app.database import get_db
from app.models.campaign import Campaign
from app.models.session import Session, SessionStatus
from app.models.user import User
from app.schemas.session import (
    AttendanceEntry,
    AttendanceUpsert,
    ConfirmRequest,
    SessionCreate,
    SessionListItem,
    SessionNoteResponse,
    SessionNoteUpsert,
    SessionResponse,
    SessionUpdate,
)
from app.services import attendance_service, session_note_service, session_service

router = APIRouter()


# ── Campaign-scoped: list + create ────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/sessions", response_model=list[SessionListItem])
async def list_sessions(
    campaign_id: uuid.UUID,
    _: User = Depends(require_campaign_member),
    db: AsyncSession = Depends(get_db),
) -> list[SessionListItem]:
    """List all sessions for a campaign (members only)."""
    return await session_service.list_campaign_sessions(db, campaign_id)


@router.post(
    "/campaigns/{campaign_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    campaign_id: uuid.UUID,
    data: SessionCreate,
    current_user: User = Depends(require_gm),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create a new session (GM only).

    Scheduling mode controls how many proposed_times are accepted:
    - vote:      2–5 proposed times; players vote before GM confirms.
    - direct:    exactly 1 time; session is confirmed immediately.
    - tentative: exactly 1 time; session stays proposed until GM confirms.
    """
    return await session_service.create_session(db, campaign_id, current_user, data)


# ── Session-scoped: detail, update, cancel, confirm ───────────────────────────

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    _: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    session = await session_service.get_session_with_slots(db, session_id)
    return session  # type: ignore[return-value]


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    try:
        return await session_service.update_session(db, session, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a session (GM only). Sets status to 'cancelled'."""
    try:
        await session_service.cancel_session(db, session)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/sessions/{session_id}/confirm", response_model=SessionResponse)
async def confirm_session(
    session_id: uuid.UUID,
    body: ConfirmRequest,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Confirm a proposed session (GM only).

    For vote mode: supply the winning time_slot_id.
    For tentative mode: omit time_slot_id (the single slot is used automatically).
    """
    try:
        return await session_service.confirm_session(db, session, body.time_slot_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ── Per-user session notes ─────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/my-note", response_model=SessionNoteResponse | None)
async def get_my_note(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> SessionNoteResponse | None:
    """Return the current user's private note for this session, or null."""
    return await session_note_service.get_note(db, session_id, current_user.id)


@router.put("/sessions/{session_id}/my-note", response_model=SessionNoteResponse)
async def upsert_my_note(
    session_id: uuid.UUID,
    data: SessionNoteUpsert,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> SessionNoteResponse:
    """Create or update the current user's note for this session.

    Players can only save private notes.  GMs may also set visibility=public
    to share notes with all campaign members in the aggregated journal view.
    """
    from app.models.campaign import CampaignMember, MemberRole
    from app.models.session_note import NoteVisibility
    from sqlalchemy import select

    # Only GMs are allowed to create public notes
    visibility = data.visibility
    if visibility == NoteVisibility.public:
        member = await db.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == session.campaign_id,
                CampaignMember.user_id == current_user.id,
                CampaignMember.role == MemberRole.gm,
            )
        )
        if not member:
            visibility = NoteVisibility.private

    return await session_note_service.upsert_note(
        db, session_id, current_user.id, data.content, visibility
    )


# ── Attendance ─────────────────────────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}/attendance",
    response_model=list[AttendanceEntry],
)
async def get_attendance(
    session_id: uuid.UUID,
    session: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceEntry]:
    """Return attendance status for all campaign members (any member can view)."""
    return await attendance_service.get_session_attendance(
        db, session_id, session.campaign_id
    )


@router.put(
    "/sessions/{session_id}/attendance/{user_id}",
    response_model=AttendanceEntry,
)
async def set_attendance(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AttendanceUpsert,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> AttendanceEntry:
    """Mark a member as attended or not attended (GM only).

    In v2.0 the Discord recording bot will call this same endpoint to
    auto-set attendance when it detects users joining a voice channel.
    """
    from app.models.campaign import CampaignMember
    from sqlalchemy import select

    # Verify the target user is a campaign member
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == session.campaign_id,
            CampaignMember.user_id == user_id,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this campaign",
        )

    record = await attendance_service.upsert_attendance(
        db, session_id, user_id, data.attended
    )

    # Fetch display name for response
    from app.models.user import User as UserModel
    from sqlalchemy import select as sel
    u = await db.scalar(sel(UserModel).where(UserModel.id == user_id))
    return AttendanceEntry(
        user_id=user_id,
        display_name=u.effective_display_name if u else str(user_id),
        attended=record.attended,
    )


# ── Calendar / ICS download ────────────────────────────────────────────────────

def _build_ics(session: Session, campaign_name: str) -> str:
    """Generate an iCalendar (.ics) file for a confirmed session."""
    def _fmt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    confirmed = session.confirmed_time.astimezone(timezone.utc)  # type: ignore[union-attr]
    dtend = confirmed + timedelta(hours=4)
    now = datetime.now(timezone.utc)
    title = (session.title or "Game Session").replace(",", "\\,").replace(";", "\\;")
    campaign = campaign_name.replace(",", "\\,").replace(";", "\\;")
    summary = f"{title} — {campaign}"
    desc = (session.description or "").replace("\n", "\\n").replace(",", "\\,")

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Quest Board//Quest Board//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{session.id}@questboard\r\n"
        f"DTSTAMP:{_fmt(now)}\r\n"
        f"DTSTART:{_fmt(confirmed)}\r\n"
        f"DTEND:{_fmt(dtend)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{desc}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@router.get("/sessions/{session_id}/calendar.ics")
async def download_ics(
    session_id: uuid.UUID,
    session: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a .ics calendar file for a confirmed session."""
    if session.status != SessionStatus.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calendar download is only available for confirmed sessions",
        )
    campaign = await db.get(Campaign, session.campaign_id)
    campaign_name = campaign.name if campaign else "Campaign"
    ics = _build_ics(session, campaign_name)
    safe_title = (session.title or "session").replace(" ", "_").replace("/", "-")[:40]
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.ics"'},
    )
