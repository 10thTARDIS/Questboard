"""Vote submission, update, and retrieval."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timeslot import TimeSlot
from app.models.vote import Availability, Vote


async def get_session_votes(db: AsyncSession, session_id: uuid.UUID) -> list[Vote]:
    """Return all votes across every time slot of a session."""
    result = await db.execute(
        select(Vote)
        .join(TimeSlot, Vote.time_slot_id == TimeSlot.id)
        .where(TimeSlot.session_id == session_id)
    )
    return list(result.scalars())


async def upsert_vote(
    db: AsyncSession,
    slot: TimeSlot,
    user_id: uuid.UUID,
    availability: Availability,
) -> Vote:
    """Create or update a user's vote for a time slot."""
    result = await db.execute(
        select(Vote).where(
            Vote.time_slot_id == slot.id,
            Vote.user_id == user_id,
        )
    )
    vote = result.scalar_one_or_none()
    if vote:
        vote.availability = availability
        vote.updated_at = datetime.now(timezone.utc)
    else:
        vote = Vote(
            time_slot_id=slot.id,
            user_id=user_id,
            availability=availability,
        )
        db.add(vote)
    await db.flush()
    await db.refresh(vote)
    return vote


async def delete_vote(
    db: AsyncSession,
    slot: TimeSlot,
    user_id: uuid.UUID,
) -> None:
    """Remove a user's vote for a time slot if it exists."""
    result = await db.execute(
        select(Vote).where(
            Vote.time_slot_id == slot.id,
            Vote.user_id == user_id,
        )
    )
    vote = result.scalar_one_or_none()
    if vote:
        await db.delete(vote)
        await db.flush()
