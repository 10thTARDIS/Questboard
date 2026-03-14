"""Session API routes.

Campaign-scoped:  POST/GET /api/campaigns/{campaign_id}/sessions
Session-scoped:   GET/PATCH/DELETE/POST /api/sessions/{session_id}[/confirm]
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    get_session_for_gm,
    get_session_for_member,
    require_campaign_member,
    require_gm,
)
from app.database import get_db
from app.models.session import Session
from app.models.user import User
from app.schemas.session import (
    ConfirmRequest,
    SessionCreate,
    SessionListItem,
    SessionNoteResponse,
    SessionNoteUpsert,
    SessionResponse,
    SessionUpdate,
)
from app.services import session_note_service, session_service

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
    _: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> SessionNoteResponse:
    """Create or update the current user's private note for this session."""
    return await session_note_service.upsert_note(
        db, session_id, current_user.id, data.content
    )
