"""Campaign lore entry business logic."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lore_entry import LoreEntry, LoreType


async def list_lore_entries(db: AsyncSession, campaign_id: uuid.UUID) -> list[LoreEntry]:
    """Return all lore entries for a campaign, ordered by type then title."""
    result = await db.execute(
        select(LoreEntry)
        .where(LoreEntry.campaign_id == campaign_id)
        .order_by(LoreEntry.entry_type, LoreEntry.title)
    )
    return list(result.scalars().all())


async def create_lore_entry(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    creator_id: uuid.UUID,
    entry_type: LoreType,
    title: str,
    body: str,
    linked_session_id: uuid.UUID | None,
) -> LoreEntry:
    entry = LoreEntry(
        campaign_id=campaign_id,
        created_by=creator_id,
        entry_type=entry_type,
        title=title,
        body=body,
        linked_session_id=linked_session_id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_lore_entry(
    db: AsyncSession,
    entry: LoreEntry,
    updates: dict,
) -> LoreEntry:
    """Apply a partial update.  Only keys in `updates` are written."""
    for key, value in updates.items():
        setattr(entry, key, value)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_lore_entry(db: AsyncSession, entry: LoreEntry) -> None:
    await db.delete(entry)
    await db.commit()
