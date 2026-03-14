"""Celery reminder tasks for Quest Board sessions."""

from datetime import datetime, timezone

from app.notifications.discord import discord_backend
from app.notifications.email import email_backend
from app.tasks.celery_app import celery_app

# All active notification backends — add new ones here as they are implemented.
_BACKENDS = [discord_backend, email_backend]


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.reminder_tasks.send_session_reminder",
)
def send_session_reminder(
    self,
    session_id: str,
    campaign_name: str,
    session_title: str,
    confirmed_time_iso: str,
    hours_until: int,
    webhook_url: str,
) -> None:
    """Send a reminder notification before a confirmed session.

    Scheduled with ETAs of 7 days / 24 hours / 1 hour before the session.
    All data is passed as arguments so no DB access is needed in the task.
    Notifications are sent via all active backends (Discord + email).
    """
    try:
        confirmed_time = datetime.fromisoformat(confirmed_time_iso).replace(
            tzinfo=timezone.utc
        )
        title = session_title or "Untitled Session"
        for backend in _BACKENDS:
            backend.send_reminder(
                campaign_name=campaign_name,
                session_title=title,
                confirmed_time=confirmed_time,
                hours_until=hours_until,
                webhook_url=webhook_url,
            )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.reminder_tasks.send_session_confirmed",
)
def send_session_confirmed(
    self,
    session_id: str,
    campaign_name: str,
    session_title: str,
    confirmed_time_iso: str,
    webhook_url: str,
) -> None:
    """Notify members immediately when a session is confirmed.

    Notifications are sent via all active backends (Discord + email).
    """
    try:
        confirmed_time = datetime.fromisoformat(confirmed_time_iso).replace(
            tzinfo=timezone.utc
        )
        title = session_title or "Untitled Session"
        for backend in _BACKENDS:
            backend.send_confirmation(
                campaign_name=campaign_name,
                session_title=title,
                confirmed_time=confirmed_time,
                webhook_url=webhook_url,
            )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=5,
    name="app.tasks.reminder_tasks.send_test_email",
)
def send_test_email(self, to_address: str) -> None:
    """Send a test email to verify SMTP configuration (triggered from admin UI)."""
    try:
        email_backend.send_test(to_address=to_address)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="app.tasks.reminder_tasks.send_vote_notification",
)
def send_vote_notification(
    self,
    campaign_name: str,
    session_title: str,
    webhook_url: str,
    mode: str,
    voter_name: str | None = None,
) -> None:
    """Post a vote notification to the campaign's webhook.

    mode="each_vote" — sent after every individual vote cast.
    mode="all_voted"  — sent once when all campaign members have voted.
    """
    import httpx

    title = session_title or "Untitled Session"
    if mode == "all_voted":
        message = f"🗳️ All players have voted on **{title}** in **{campaign_name}**!"
    else:
        voter = voter_name or "Someone"
        message = f"🗳️ **{voter}** voted on **{title}** in **{campaign_name}**."

    payload = {"content": message}
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.reminder_tasks.auto_close_voting",
)
def auto_close_voting(session_id: str) -> None:
    """Auto-close a vote-mode session by confirming the highest-scored time slot.

    Scheduled when a vote-mode session is created (if the campaign has
    vote_auto_close_hours set).  Fires silently if the session was already
    confirmed or cancelled by the GM.
    """
    import asyncio

    asyncio.run(_auto_close_voting_async(session_id))


async def _auto_close_voting_async(session_id: str) -> None:
    import uuid

    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.session import SchedulingMode, Session, SessionStatus
    from app.models.timeslot import TimeSlot
    from app.models.vote import Availability, Vote
    from app.services import session_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(Session.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()

        # Only act on vote-mode sessions still in proposed state
        if (
            session is None
            or session.status != SessionStatus.proposed
            or session.scheduling_mode != SchedulingMode.vote
        ):
            return

        # Find all time slots and pick the highest-scored one
        slots_result = await db.execute(
            select(TimeSlot).where(TimeSlot.session_id == session.id)
        )
        slots = slots_result.scalars().all()
        if not slots:
            return

        best_slot = slots[0]
        best_score = -1
        for slot in slots:
            votes_result = await db.execute(
                select(Vote).where(Vote.time_slot_id == slot.id)
            )
            votes = votes_result.scalars().all()
            score = sum(
                2 if v.availability == Availability.yes
                else 1 if v.availability == Availability.maybe
                else 0
                for v in votes
            )
            if score > best_score:
                best_score = score
                best_slot = slot

        try:
            await session_service.confirm_session(db, session, best_slot.id)
        except ValueError:
            pass  # Already handled or cancelled concurrently


@celery_app.task(
    name="app.tasks.reminder_tasks.auto_complete_sessions",
)
def auto_complete_sessions() -> None:
    """Transition confirmed sessions to 'completed' once their time has passed.

    Runs on a schedule (every 5 minutes via Celery Beat).  Finds all sessions
    with status=confirmed whose confirmed_time is in the past and marks them
    completed so the GM no longer needs to do it manually.
    """
    import asyncio

    asyncio.run(_auto_complete_sessions_async())


async def _auto_complete_sessions_async() -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.session import Session, SessionStatus

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(
                Session.status == SessionStatus.confirmed,
                Session.confirmed_time < now,
            )
        )
        sessions = result.scalars().all()
        for session in sessions:
            session.status = SessionStatus.completed
        if sessions:
            await db.commit()
