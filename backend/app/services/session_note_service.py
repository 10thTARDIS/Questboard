"""Session note business logic (private per-user notes per session)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session_note import SessionNote


async def upsert_note(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> SessionNote:
    """Create or update the note for this (session, user) pair."""
    result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id == session_id,
            SessionNote.user_id == user_id,
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        note = SessionNote(
            session_id=session_id,
            user_id=user_id,
            content=content,
        )
        db.add(note)
    else:
        note.content = content
        note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


async def get_note(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SessionNote | None:
    """Return the note for this (session, user) pair, or None."""
    result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id == session_id,
            SessionNote.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
