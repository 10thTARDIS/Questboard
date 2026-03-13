"""Vote endpoints — submit, update, delete, and list votes for a session."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_session_for_member
from app.database import get_db
from app.models.session import Session, SchedulingMode, SessionStatus
from app.models.timeslot import TimeSlot
from app.models.user import User
from app.schemas.vote import VoteResponse, VoteSubmit
from app.services import vote_service

router = APIRouter()


# ── List all votes for a session ───────────────────────────────────────────────

@router.get("/sessions/{session_id}/votes", response_model=list[VoteResponse])
async def list_votes(
    session: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
):
    """Return every vote cast across all time slots of the session."""
    return await vote_service.get_session_votes(db, session.id)


# ── Submit / update a vote ─────────────────────────────────────────────────────

@router.put(
    "/sessions/{session_id}/timeslots/{slot_id}/vote",
    response_model=VoteResponse,
)
async def submit_vote(
    slot_id: uuid.UUID,
    body: VoteSubmit,
    session: Session = Depends(get_session_for_member),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the current user's vote for a specific time slot."""
    if session.scheduling_mode != SchedulingMode.vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting is only available for vote-mode sessions",
        )
    if session.status != SessionStatus.proposed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot vote on a session that is not proposed",
        )
    slot = await db.scalar(
        select(TimeSlot).where(
            TimeSlot.id == slot_id,
            TimeSlot.session_id == session.id,
        )
    )
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time slot not found",
        )
    return await vote_service.upsert_vote(db, slot, current_user.id, body.availability)


# ── Remove a vote ──────────────────────────────────────────────────────────────

@router.delete(
    "/sessions/{session_id}/timeslots/{slot_id}/vote",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_vote(
    slot_id: uuid.UUID,
    session: Session = Depends(get_session_for_member),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the current user's vote for a specific time slot."""
    slot = await db.scalar(
        select(TimeSlot).where(
            TimeSlot.id == slot_id,
            TimeSlot.session_id == session.id,
        )
    )
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time slot not found",
        )
    await vote_service.delete_vote(db, slot, current_user.id)
