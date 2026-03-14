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
