"""Session and time-slot business logic."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.campaign import Campaign
from app.models.session import SchedulingMode, Session, SessionStatus
from app.models.timeslot import TimeSlot
from app.models.user import User
from app.schemas.session import SessionCreate, SessionUpdate


# ── Helpers ────────────────────────────────────────────────────────────────────

def _effective_webhook(campaign: Campaign) -> str | None:
    """Return the webhook URL to use: campaign-level, then global fallback."""
    return campaign.discord_webhook_url or settings.default_discord_webhook_url or None


def _schedule_reminders(
    session: Session,
    campaign: Campaign,
    confirmed_time: datetime,
) -> list[str]:
    """Schedule Celery tasks and return the list of task IDs.

    Sends an immediate confirmation notice and schedules three timed reminders
    (7 days, 24 hours, 1 hour before the session) — skipping any whose ETA is
    already in the past.
    """
    # Import here to avoid circular imports at module load time
    from app.tasks.reminder_tasks import send_session_confirmed, send_session_reminder

    use_bot = bool(campaign.guild_id and settings.questboard_bot_url)
    webhook_url = _effective_webhook(campaign)
    if not use_bot and not webhook_url:
        return []

    task_ids: list[str] = []
    session_id = str(session.id)
    campaign_name = campaign.name
    session_title = session.title or "Untitled Session"
    confirmed_iso = confirmed_time.astimezone(timezone.utc).isoformat()

    # Immediate confirmation notification
    send_session_confirmed.delay(
        session_id,
        campaign_name,
        session_title,
        confirmed_iso,
        webhook_url or "",
        guild_id=campaign.guild_id or "",
        notification_channel_id=campaign.notification_channel_id or "",
        campaign_id=str(campaign.id),
    )

    # Timed reminders — use campaign-level offsets if set, otherwise default (7d/24h/1h)
    default_offsets_hours = [7 * 24, 24, 1]
    if campaign.reminder_offsets_minutes:
        reminder_hours_list = [m / 60 for m in campaign.reminder_offsets_minutes]
    else:
        reminder_hours_list = default_offsets_hours

    now = datetime.now(timezone.utc)
    for hours in reminder_hours_list:
        eta = confirmed_time.astimezone(timezone.utc) - timedelta(hours=hours)
        if eta <= now:
            continue  # already past — skip
        task = send_session_reminder.apply_async(
            args=[
                session_id,
                campaign_name,
                session_title,
                confirmed_iso,
                hours,
                webhook_url or "",
            ],
            kwargs={
                "guild_id": campaign.guild_id or "",
                "notification_channel_id": campaign.notification_channel_id or "",
                "campaign_id": str(campaign.id),
            },
            eta=eta,
        )
        task_ids.append(task.id)

    return task_ids


def _revoke_reminders(session: Session) -> None:
    """Cancel any pending Celery reminder tasks for the session."""
    if not session.celery_task_ids:
        return
    from app.tasks.celery_app import celery_app as _celery

    for task_id in session.celery_task_ids:
        _celery.control.revoke(task_id, terminate=True)
    session.celery_task_ids = None


def _schedule_vote_close(session: Session, campaign: Campaign) -> str | None:
    """Schedule the auto-close task for a vote-mode session.

    Returns the Celery task ID, or None if auto-close is not configured.
    """
    if not campaign.vote_auto_close_hours:
        return None

    from app.tasks.reminder_tasks import auto_close_voting

    now = datetime.now(timezone.utc)
    eta = now + timedelta(hours=campaign.vote_auto_close_hours)
    task = auto_close_voting.apply_async(args=[str(session.id)], eta=eta)
    return task.id


def _revoke_vote_close(session: Session) -> None:
    """Cancel the pending vote auto-close task if one was scheduled."""
    if not session.vote_close_task_id:
        return
    from app.tasks.celery_app import celery_app as _celery

    _celery.control.revoke(session.vote_close_task_id, terminate=True)
    session.vote_close_task_id = None


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    creator: User,
    data: SessionCreate,
) -> Session:
    """Create a session and its initial time slots.

    direct mode  → status=confirmed, confirmed_time set immediately, reminders scheduled.
    tentative    → status=proposed, one slot.
    vote         → status=proposed, 2–5 slots.
    """
    is_direct = data.scheduling_mode == SchedulingMode.direct

    session = Session(
        campaign_id=campaign_id,
        title=data.title,
        description=data.description,
        scheduling_mode=data.scheduling_mode,
        status=SessionStatus.confirmed if is_direct else SessionStatus.proposed,
        confirmed_time=data.proposed_times[0] if is_direct else None,
        created_by=creator.id,
    )
    db.add(session)
    await db.flush()  # populate session.id

    for t in data.proposed_times:
        db.add(TimeSlot(session_id=session.id, proposed_time=t))

    campaign = await db.get(Campaign, campaign_id)
    if campaign:
        if is_direct:
            # Direct mode: confirm and schedule reminders immediately
            task_ids = _schedule_reminders(session, campaign, data.proposed_times[0])
            if task_ids:
                session.celery_task_ids = task_ids
        elif data.scheduling_mode == SchedulingMode.vote:
            # Vote mode: schedule auto-close if configured
            task_id = _schedule_vote_close(session, campaign)
            if task_id:
                session.vote_close_task_id = task_id
            # Notify bot of proposed session if bot routing is configured
            if campaign.guild_id and settings.questboard_bot_url:
                await db.flush()  # ensure time slots have IDs
                slots_result = await db.execute(
                    select(TimeSlot)
                    .where(TimeSlot.session_id == session.id)
                    .order_by(TimeSlot.created_at)
                )
                slot_ids = [str(s.id) for s in slots_result.scalars().all()]
                from app.tasks.reminder_tasks import send_session_proposed
                send_session_proposed.delay(
                    str(session.id),
                    str(campaign_id),
                    campaign.name,
                    session.title or "Untitled Session",
                    campaign.guild_id,
                    campaign.notification_channel_id or "",
                    slot_ids,
                )

    await db.commit()
    return await get_session_with_slots(db, session.id)  # type: ignore[return-value]


async def get_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Session | None:
    """Return a Session by primary key without eagerly loading its time slots."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def get_session_with_slots(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Session | None:
    """Return a Session with its time_slots eagerly loaded (avoids lazy-load errors)."""
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.time_slots))
        .where(Session.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_campaign_sessions(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> list[Session]:
    """Return all sessions for a campaign, newest first.  Time slots are not loaded."""
    result = await db.execute(
        select(Session)
        .where(Session.campaign_id == campaign_id)
        .order_by(Session.created_at.desc())
    )
    return list(result.scalars().all())


async def update_session(
    db: AsyncSession,
    session: Session,
    data: SessionUpdate,
) -> Session:
    """Apply only the provided fields to the session (partial update).

    Special handling:
    - proposed_times: replaces all time slots on a non-confirmed session
    - reschedule_time: reschedules a confirmed session to a new time
    """
    updates = data.model_dump(exclude_unset=True)

    # Handle proposed_times — replace all existing slots
    if "proposed_times" in updates:
        if session.status == SessionStatus.confirmed:
            raise ValueError("Use reschedule_time to change a confirmed session's time")
        proposed_times = updates.pop("proposed_times")
        # Delete existing slots
        existing = await db.execute(
            select(TimeSlot).where(TimeSlot.session_id == session.id)
        )
        for slot in existing.scalars().all():
            await db.delete(slot)
        # Insert new slots
        for t in proposed_times:
            db.add(TimeSlot(session_id=session.id, proposed_time=t))

    # Handle reschedule_time — move a confirmed session
    if "reschedule_time" in updates:
        new_time = updates.pop("reschedule_time")
        if session.status != SessionStatus.confirmed:
            raise ValueError("Session is not confirmed; use proposed_times to edit slots")
        _revoke_reminders(session)
        session.confirmed_time = new_time
        # Update or replace the time slot that matches the old confirmed time
        existing = await db.execute(
            select(TimeSlot).where(TimeSlot.session_id == session.id)
        )
        for slot in existing.scalars().all():
            await db.delete(slot)
        db.add(TimeSlot(session_id=session.id, proposed_time=new_time))
        await db.flush()
        campaign = await db.get(Campaign, session.campaign_id)
        if campaign:
            task_ids = _schedule_reminders(session, campaign, new_time)
            if task_ids:
                session.celery_task_ids = task_ids

    for field, value in updates.items():
        setattr(session, field, value)
    await db.commit()
    return await get_session_with_slots(db, session.id)  # type: ignore[return-value]


async def cancel_session(db: AsyncSession, session: Session) -> Session:
    """Mark the session as cancelled and revoke any pending reminders."""
    if session.status == SessionStatus.cancelled:
        raise ValueError("Session is already cancelled")
    _revoke_reminders(session)
    _revoke_vote_close(session)
    session.status = SessionStatus.cancelled
    campaign = await db.get(Campaign, session.campaign_id)
    if campaign and campaign.guild_id and settings.questboard_bot_url:
        from app.tasks.reminder_tasks import send_session_cancelled
        send_session_cancelled.delay(
            str(session.id),
            str(session.campaign_id),
            campaign.name,
            session.title or "Untitled Session",
            campaign.guild_id,
            campaign.notification_channel_id or "",
        )
    await db.commit()
    return await get_session_with_slots(db, session.id)  # type: ignore[return-value]


async def confirm_session(
    db: AsyncSession,
    session: Session,
    time_slot_id: uuid.UUID | None,
) -> Session:
    """Confirm a proposed session, setting confirmed_time from the chosen slot."""
    if session.status != SessionStatus.proposed:
        raise ValueError(f"Cannot confirm a session with status '{session.status.value}'")

    if time_slot_id is not None:
        result = await db.execute(
            select(TimeSlot).where(
                TimeSlot.id == time_slot_id,
                TimeSlot.session_id == session.id,
            )
        )
        slot = result.scalar_one_or_none()
        if slot is None:
            raise ValueError("Time slot not found for this session")
        confirmed_time = slot.proposed_time
    else:
        # vote mode must specify a slot; tentative auto-uses the single slot
        if session.scheduling_mode == SchedulingMode.vote:
            raise ValueError("Vote-mode sessions require a time_slot_id to confirm")
        result = await db.execute(
            select(TimeSlot).where(TimeSlot.session_id == session.id)
        )
        slots = result.scalars().all()
        if not slots:
            raise ValueError("No time slots found for this session")
        confirmed_time = slots[0].proposed_time

    # Revoke any existing reminder/auto-close tasks before confirming
    _revoke_reminders(session)
    _revoke_vote_close(session)

    session.status = SessionStatus.confirmed
    session.confirmed_time = confirmed_time
    await db.flush()

    # Schedule new reminders
    campaign = await db.get(Campaign, session.campaign_id)
    if campaign:
        task_ids = _schedule_reminders(session, campaign, confirmed_time)
        if task_ids:
            session.celery_task_ids = task_ids

    await db.commit()
    return await get_session_with_slots(db, session.id)  # type: ignore[return-value]


# ── Time slots ────────────────────────────────────────────────────────────────

async def get_next_confirmed_session(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> Session | None:
    """Return the next upcoming confirmed session for a campaign, or None."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Session)
        .where(
            Session.campaign_id == campaign_id,
            Session.status == SessionStatus.confirmed,
            Session.confirmed_time > now,
        )
        .order_by(Session.confirmed_time)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add_timeslot(
    db: AsyncSession,
    session: Session,
    proposed_time: datetime,
) -> TimeSlot:
    if session.status != SessionStatus.proposed:
        raise ValueError("Cannot add time slots to a non-proposed session")
    if session.scheduling_mode != SchedulingMode.vote:
        raise ValueError("Time slots can only be added to vote-mode sessions")

    current_count = await db.scalar(
        select(func.count()).where(TimeSlot.session_id == session.id)
    )
    if (current_count or 0) >= 5:
        raise ValueError("Vote-mode sessions support at most 5 time slots")

    slot = TimeSlot(session_id=session.id, proposed_time=proposed_time)
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return slot


async def remove_timeslot(
    db: AsyncSession,
    session: Session,
    slot_id: uuid.UUID,
) -> None:
    if session.status != SessionStatus.proposed:
        raise ValueError("Cannot remove time slots from a non-proposed session")

    result = await db.execute(
        select(TimeSlot).where(
            TimeSlot.id == slot_id,
            TimeSlot.session_id == session.id,
        )
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise ValueError("Time slot not found")

    await db.delete(slot)
    await db.commit()
