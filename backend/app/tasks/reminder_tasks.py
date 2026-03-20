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
    *,
    guild_id: str = "",
    notification_channel_id: str = "",
    campaign_id: str = "",
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Send a reminder notification before a confirmed session.

    Scheduled with ETAs of 7 days / 24 hours / 1 hour before the session.
    All data is passed as arguments so no DB access is needed in the task.
    If the campaign has a guild_id and bot_url is set, the notification is
    routed to the bot instead of the webhook.
    """
    try:
        confirmed_time = datetime.fromisoformat(confirmed_time_iso).replace(
            tzinfo=timezone.utc
        )
        title = session_title or "Untitled Session"

        if guild_id and bot_url:
            import httpx as _httpx
            try:
                _httpx.post(
                    f"{bot_url}/notify",
                    json={
                        "event_type": "session_reminder",
                        "session_id": session_id,
                        "campaign_id": campaign_id,
                        "guild_id": guild_id,
                        "channel_id": notification_channel_id,
                        "extra": {
                            "confirmed_time": confirmed_time_iso,
                            "hours_until": hours_until,
                            "title": title,
                            "campaign_name": campaign_name,
                        },
                    },
                    headers={"X-Bot-Key": bot_key},
                    timeout=10,
                )
                return  # bot reachable — skip webhook to avoid double-posting
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Bot notify (session_reminder) failed, falling back to webhook: %s", exc
                )

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
    *,
    guild_id: str = "",
    notification_channel_id: str = "",
    campaign_id: str = "",
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Notify members immediately when a session is confirmed.

    If the campaign has a guild_id and bot_url is set, the notification is
    routed to the bot instead of the webhook.
    """
    try:
        confirmed_time = datetime.fromisoformat(confirmed_time_iso).replace(
            tzinfo=timezone.utc
        )
        title = session_title or "Untitled Session"

        if guild_id and bot_url:
            import httpx as _httpx
            try:
                _httpx.post(
                    f"{bot_url}/notify",
                    json={
                        "event_type": "session_confirmed",
                        "session_id": session_id,
                        "campaign_id": campaign_id,
                        "guild_id": guild_id,
                        "channel_id": notification_channel_id,
                        "extra": {
                            "confirmed_time": confirmed_time_iso,
                            "title": title,
                            "campaign_name": campaign_name,
                        },
                    },
                    headers={"X-Bot-Key": bot_key},
                    timeout=10,
                )
                return  # bot reachable — skip webhook to avoid double-posting
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Bot notify (session_confirmed) failed, falling back to webhook: %s", exc
                )

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
    name="app.tasks.reminder_tasks.send_recap_email",
)
def send_recap_email(self, session_id: str) -> None:
    """Send a post-session recap email to opted-in attendees.

    Fired after the bot uploads a transcript via POST /api/bot/sessions/{id}/transcript.
    Only sends if:
      - The campaign has recap_email_enabled = True
      - The recipient user has recap_email_opt_in = True and has an email address
      - SMTP is configured
    """
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    try:
        from app.database import AsyncSessionLocal
        from app.models.campaign import Campaign
        from app.models.session import Session
        from app.models.session_attendance import SessionAttendance
        from app.models.user import User
        from app.services.settings_service import get_smtp_config
        from sqlalchemy import select

        loop = asyncio.new_event_loop()
        try:
            async def _fetch():
                async with AsyncSessionLocal() as db:
                    session = await db.get(Session, session_id)
                    if session is None:
                        return None
                    campaign = await db.get(Campaign, session.campaign_id)
                    if campaign is None or not campaign.recap_email_enabled:
                        return None
                    smtp_cfg = await get_smtp_config(db)
                    if smtp_cfg is None:
                        return None
                    # Attendees who opted in and have an email address
                    att_result = await db.execute(
                        select(SessionAttendance, User)
                        .join(User, User.id == SessionAttendance.user_id)
                        .where(
                            SessionAttendance.session_id == session.id,
                            SessionAttendance.attended == True,  # noqa: E712
                            User.recap_email_opt_in == True,  # noqa: E712
                            User.email.isnot(None),
                        )
                    )
                    recipients = [(row.User.email, row.User.effective_display_name) for row in att_result]
                    return {
                        "session_title": session.title or "Untitled Session",
                        "campaign_name": campaign.name,
                        "summary": session.summary or "",
                        "smtp_cfg": smtp_cfg,
                        "recipients": recipients,
                    }

            data = loop.run_until_complete(_fetch())
        finally:
            loop.close()

        if not data or not data["recipients"]:
            return

        from app.notifications.email import email_backend as _email
        import smtplib, ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        cfg = data["smtp_cfg"]
        subject = f"[Quest Board] Session Recap — {data['session_title']}"

        for to_email, display_name in data["recipients"]:
            html_body = (
                f"<h2>Session Recap: {data['session_title']}</h2>"
                f"<p><strong>Campaign:</strong> {data['campaign_name']}</p>"
                f"<hr>"
                f"<h3>Summary</h3>"
                f"<p>{data['summary'].replace(chr(10), '<br>')}</p>"
                f"<hr><p style='color:#888;font-size:12px;'>Sent by Quest Board · "
                f"To unsubscribe, uncheck <em>Recap emails</em> in your Profile settings.</p>"
            )
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = cfg.from_address
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html"))
            try:
                if cfg.use_tls:
                    context = ssl.create_default_context()
                    with smtplib.SMTP(cfg.host, cfg.port, timeout=15) as server:
                        server.ehlo()
                        server.starttls(context=context)
                        if cfg.username:
                            server.login(cfg.username, cfg.password)
                        server.sendmail(cfg.from_address, to_email, msg.as_string())
                else:
                    with smtplib.SMTP(cfg.host, cfg.port, timeout=15) as server:
                        if cfg.username:
                            server.login(cfg.username, cfg.password)
                        server.sendmail(cfg.from_address, to_email, msg.as_string())
            except Exception as exc:
                logger.warning("Recap email to %s failed: %s", to_email, exc)

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
    *,
    session_id: str = "",
    campaign_id: str = "",
    guild_id: str = "",
    notification_channel_id: str = "",
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Post a vote notification to the campaign's webhook or bot.

    mode="each_vote" — sent after every individual vote cast.
    mode="all_voted"  — sent once when all campaign members have voted.
    If guild_id and bot_url are set, routes to the bot for a rich embed.
    """
    import httpx

    title = session_title or "Untitled Session"

    if guild_id and bot_url:
        try:
            httpx.post(
                f"{bot_url}/notify",
                json={
                    "event_type": "vote_update",
                    "session_id": session_id,
                    "campaign_id": campaign_id,
                    "guild_id": guild_id,
                    "channel_id": notification_channel_id,
                    "extra": {
                        "mode": mode,
                        "voter_name": voter_name,
                        "title": title,
                        "campaign_name": campaign_name,
                    },
                },
                headers={"X-Bot-Key": bot_key},
                timeout=10,
            )
            return  # bot reachable — skip webhook
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Bot notify (vote_update) failed, falling back to webhook: %s", exc
            )

    if mode == "all_voted":
        message = f"🗳️ All players have voted on **{title}** in **{campaign_name}**!"
    else:
        voter = voter_name or "Someone"
        message = f"🗳️ **{voter}** voted on **{title}** in **{campaign_name}**."

    try:
        resp = httpx.post(webhook_url, json={"content": message}, timeout=10)
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
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.reminder_tasks.send_session_completed",
)
def send_session_completed(
    self,
    session_id: str,
    campaign_id: str,
    campaign_name: str,
    session_title: str,
    guild_id: str,
    notification_channel_id: str,
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Notify the bot when a session auto-completes (transitions confirmed → completed).

    The bot uses this to prompt the GM to start a recording or post a
    "session complete" embed, and to check whether a transcript is still needed.
    """
    if not guild_id or not bot_url:
        return
    import httpx as _httpx
    try:
        resp = _httpx.post(
            f"{bot_url}/notify",
            json={
                "event_type": "session_completed",
                "session_id": session_id,
                "campaign_id": campaign_id,
                "guild_id": guild_id,
                "channel_id": notification_channel_id,
                "extra": {"title": session_title, "campaign_name": campaign_name},
            },
            headers={"X-Bot-Key": bot_key},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise self.retry(exc=exc)


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
    from app.models.campaign import Campaign
    from app.models.session import Session, SessionStatus
    from app.services.settings_service import get_bot_api_key, get_bot_url

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session).where(
                Session.status == SessionStatus.confirmed,
                Session.confirmed_time < now,
            )
        )
        sessions = result.scalars().all()
        if not sessions:
            return

        bot_url = await get_bot_url(db)
        bot_key = await get_bot_api_key(db) or ""

        for session in sessions:
            session.status = SessionStatus.completed

        await db.commit()

        # Notify the bot for each completed session (if bot-connected)
        for session in sessions:
            campaign = await db.get(Campaign, session.campaign_id)
            if campaign and campaign.guild_id and bot_url:
                send_session_completed.delay(
                    session_id=str(session.id),
                    campaign_id=str(campaign.id),
                    campaign_name=campaign.name,
                    session_title=session.title or "",
                    guild_id=campaign.guild_id,
                    notification_channel_id=campaign.notification_channel_id or "",
                    bot_url=bot_url,
                    bot_key=bot_key,
                )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.reminder_tasks.send_session_proposed",
)
def send_session_proposed(
    self,
    session_id: str,
    campaign_id: str,
    campaign_name: str,
    session_title: str,
    guild_id: str,
    notification_channel_id: str,
    slot_ids: list[str],
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Notify the bot when a vote-mode session is proposed."""
    if not guild_id or not bot_url:
        return
    import httpx as _httpx
    try:
        resp = _httpx.post(
            f"{bot_url}/notify",
            json={
                "event_type": "session_proposed",
                "session_id": session_id,
                "campaign_id": campaign_id,
                "guild_id": guild_id,
                "channel_id": notification_channel_id,
                "extra": {
                    "slot_ids": slot_ids,
                    "title": session_title,
                    "campaign_name": campaign_name,
                },
            },
            headers={"X-Bot-Key": bot_key},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.reminder_tasks.send_session_cancelled",
)
def send_session_cancelled(
    self,
    session_id: str,
    campaign_id: str,
    campaign_name: str,
    session_title: str,
    guild_id: str,
    notification_channel_id: str,
    bot_url: str = "",
    bot_key: str = "",
) -> None:
    """Notify the bot when a session is cancelled."""
    if not guild_id or not bot_url:
        return
    import httpx as _httpx
    try:
        resp = _httpx.post(
            f"{bot_url}/notify",
            json={
                "event_type": "session_cancelled",
                "session_id": session_id,
                "campaign_id": campaign_id,
                "guild_id": guild_id,
                "channel_id": notification_channel_id,
                "extra": {"title": session_title, "campaign_name": campaign_name},
            },
            headers={"X-Bot-Key": bot_key},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise self.retry(exc=exc)
