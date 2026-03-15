"""Session note business logic (per-user notes per session + campaign journal)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Create or update the note for this (session, user, visibility) triplet.

    Each user may have at most one private note and one public note per
    session.  Upserting with visibility='private' never touches their public
    note, and vice-versa.
    """
    result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id == session_id,
            SessionNote.user_id == user_id,
            SessionNote.visibility == visibility,
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
        note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


async def get_notes(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SessionNote]:
    """Return all notes (private and/or public) for this (session, user) pair."""
    result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id == session_id,
            SessionNote.user_id == user_id,
        )
    )
    return list(result.scalars().all())


async def get_campaign_notes(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> list[CampaignNoteEntry]:
    """Return an aggregated journal for a user across all sessions in a campaign.

    Each entry contains:
      - All of the user's own notes for that session (private + public).
      - The GM's public note for that session (if the user is not the GM).

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

    # Fetch ALL of the current user's notes for sessions in this campaign
    my_notes_result = await db.execute(
        select(SessionNote).where(
            SessionNote.session_id.in_(session_ids),
            SessionNote.user_id == user_id,
        )
    )
    # Group by session_id — a user can now have up to 2 notes per session
    my_notes_by_session: dict[uuid.UUID, list[SessionNote]] = {}
    for n in my_notes_result.scalars().all():
        my_notes_by_session.setdefault(n.session_id, []).append(n)

    # Fetch the GM's public notes for all sessions (if user is not the GM)
    gm_public_notes: dict[uuid.UUID, SessionNote] = {}
    if gm_id and gm_id != user_id:
        gm_result2 = await db.execute(
            select(SessionNote).where(
                SessionNote.session_id.in_(session_ids),
                SessionNote.user_id == gm_id,
                SessionNote.visibility == NoteVisibility.public,
            )
        )
        gm_public_notes = {n.session_id: n for n in gm_result2.scalars().all()}

    entries: list[CampaignNoteEntry] = []
    for session in sessions:
        my_notes = my_notes_by_session.get(session.id, [])
        gm_note = gm_public_notes.get(session.id)
        if not my_notes and not gm_note:
            continue
        entries.append(
            CampaignNoteEntry(
                session_id=session.id,
                session_title=session.title,
                confirmed_time=session.confirmed_time,
                my_notes=[n.content for n in sorted(my_notes, key=lambda n: n.created_at)],
                gm_public_note=gm_note.content if gm_note else None,
            )
        )

    return entries
