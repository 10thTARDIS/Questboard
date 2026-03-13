"""Time slot API routes, all scoped under /api/sessions/{session_id}/timeslots."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_session_for_gm, get_session_for_member
from app.database import get_db
from app.models.session import Session
from app.schemas.session import TimeSlotCreate, TimeSlotResponse
from app.services import session_service

router = APIRouter()


@router.get(
    "/sessions/{session_id}/timeslots",
    response_model=list[TimeSlotResponse],
)
async def list_timeslots(
    session_id: uuid.UUID,
    session: Session = Depends(get_session_for_member),
    db: AsyncSession = Depends(get_db),
) -> list[TimeSlotResponse]:
    """List time slots for a session (members only)."""
    full = await session_service.get_session_with_slots(db, session_id)
    return full.time_slots if full else []  # type: ignore[return-value]


@router.post(
    "/sessions/{session_id}/timeslots",
    response_model=TimeSlotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_timeslot(
    session_id: uuid.UUID,
    data: TimeSlotCreate,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> TimeSlotResponse:
    """Add a time slot to a vote-mode session (GM only, max 5 total)."""
    try:
        return await session_service.add_timeslot(db, session, data.proposed_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/sessions/{session_id}/timeslots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_timeslot(
    session_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: Session = Depends(get_session_for_gm),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a time slot (GM only; session must still be proposed)."""
    try:
        await session_service.remove_timeslot(db, session, slot_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
