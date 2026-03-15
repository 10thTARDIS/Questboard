"""Campaign milestone business logic."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.milestone import Milestone


async def list_milestones(db: AsyncSession, campaign_id: uuid.UUID) -> list[Milestone]:
    """Return all milestones for a campaign, ordered by milestone_date then created_at."""
    result = await db.execute(
        select(Milestone)
        .where(Milestone.campaign_id == campaign_id)
        .order_by(
            Milestone.milestone_date.desc().nulls_first(),
            Milestone.created_at.desc(),
        )
    )
    return list(result.scalars().all())


async def create_milestone(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    creator_id: uuid.UUID,
    title: str,
    description: str | None,
    session_id: uuid.UUID | None,
    milestone_date: datetime | None,
) -> Milestone:
    milestone = Milestone(
        campaign_id=campaign_id,
        created_by=creator_id,
        title=title,
        description=description,
        session_id=session_id,
        milestone_date=milestone_date,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return milestone


async def update_milestone(
    db: AsyncSession,
    milestone: Milestone,
    updates: dict,
) -> Milestone:
    """Apply a partial update to a milestone.

    Only keys present in `updates` are written — callers should build this
    dict with `model_dump(exclude_unset=True)` so unmentioned fields are
    never touched.  Passing a key with value `None` explicitly sets that
    column to NULL (e.g. to unlink a session).
    """
    for key, value in updates.items():
        setattr(milestone, key, value)
    await db.commit()
    await db.refresh(milestone)
    return milestone


async def delete_milestone(db: AsyncSession, milestone: Milestone) -> None:
    await db.delete(milestone)
    await db.commit()
