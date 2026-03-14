"""Session note business logic (per-user notes per session + campaign journal)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import CampaignMember, MemberRole
from app.models.session import Session, SessionStatus
from app.models.session_note import NoteVisibility, SessionNote
from app.schemas.session import CampaignNoteEntry


async def upsert_note(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    visibility: NoteVisibility = NoteVisibility.private,
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
            visibility=visibility,
        )
        db.add(note)
    else:
        note.content = content
        note.visibility = visibility
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


async def get_campaign_notes(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> list[CampaignNoteEntry]:
    """Return an aggregated journal for a user across all sessions in a campaign.

    Each entry contains:
      - The user's own note for that session (any visibility).
      - The GM's public note for that session (if one exists and user isn't the GM).

    Sessions are ordered by confirmed_time ascending (chronological journal).
    Sessions with no notes at all are omitted.
    """
    # Fetch all sessions in the campaign that are not cancelled
    sessions_result = await db.execute(
        select(Session)
        .where(
            Session.campaign_id == campaign_id,
            Session.status != SessionStatus.cancelled,
        )
        .order_by(Session.confirmed_time.asc().nullslast(), Session.created_at.asc())
    )
    sessions = list(sessions_result.scalars().all())
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    session_map = {s.id: s for s in sessions}

    # Find the GM of this campaign
    gm_result = await db.execute(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.role == MemberRole.gm,
        )
    )
    gm_id: uuid.UUID | None = gm_result.scalar_one_or_none()

    # Fetch the current user's notes for all sessions in this campaign
    my_notes_result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id.in_(session_ids),
            SessionNote.user_id == user_id,
        )
    )
    my_notes: dict[uuid.UUID, SessionNote] = {
        n.session_id: n for n in my_notes_result.scalars().all()
    }

    # Fetch the GM's public notes for all sessions (if user is not the GM)
    gm_public_notes: dict[uuid.UUID, SessionNote] = {}
    if gm_id and gm_id != user_id:
        gm_result = await db.execute(
            select(SessionNote).where(
                SessionNote.session_id.in_(session_ids),
                SessionNote.user_id == gm_id,
                SessionNote.visibility == NoteVisibility.public,
            )
        )
        gm_public_notes = {n.session_id: n for n in gm_result.scalars().all()}

    entries: list[CampaignNoteEntry] = []
    for session in sessions:
        my_note = my_notes.get(session.id)
        gm_note = gm_public_notes.get(session.id)
        # Only include sessions where there's at least one note to show
        if not my_note and not gm_note:
            continue
        entries.append(
            CampaignNoteEntry(
                session_id=session.id,
                session_title=session.title,
                confirmed_time=session.confirmed_time,
                my_note=my_note.content if my_note else None,
                gm_public_note=gm_note.content if gm_note else None,
            )
        )

    return entries
