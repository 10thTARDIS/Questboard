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
            Milestone.milestone_date.nulls_last(),
            Milestone.created_at,
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
    title: str | None,
    description: str | None,
    session_id: uuid.UUID | None,
    milestone_date: datetime | None,
) -> Milestone:
    """Update milestone fields.

    `title` is only changed when not None (it is required and cannot be cleared).
    Nullable fields (description, session_id, milestone_date) are always written
    so that passing None explicitly sets them to NULL.
    """
    if title is not None:
        milestone.title = title
    milestone.description = description
    milestone.session_id = session_id
    milestone.milestone_date = milestone_date
    await db.commit()
    await db.refresh(milestone)
    return milestone


async def delete_milestone(db: AsyncSession, milestone: Milestone) -> None:
    await db.delete(milestone)
    await db.commit()
