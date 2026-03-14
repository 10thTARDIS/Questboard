"""Email notification backend.

Sends session confirmation and reminder emails via SMTP.
Uses synchronous smtplib so it works inside Celery tasks without an event loop.

SMTP credentials are read from the database at send time via settings_service.
If no SMTP config is stored, all methods no-op silently.
"""

import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.notifications.protocol import NotificationBackend

logger = logging.getLogger(__name__)


def _fmt(dt: datetime) -> str:
    """Format a datetime for display in emails."""
    return dt.astimezone(timezone.utc).strftime("%A, %B %-d %Y at %H:%M UTC")


def _hours_label(hours_until: int) -> str:
    if hours_until >= 7 * 24:
        return "1 week"
    if hours_until >= 24:
        return "24 hours"
    return "1 hour"


class EmailNotificationBackend:
    """Sends HTML notification emails via SMTP.

    Credentials are loaded from the database each time a notification is sent
    so admin changes take effect immediately without restarting workers.
    """

    def send_confirmation(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        webhook_url: str,  # unused for email; accepted to satisfy protocol
    ) -> None:
        cfg = self._load_config()
        if cfg is None:
            return
        subject = f"[Quest Board] Session Confirmed — {session_title}"
        body = (
            f"<h2>✅ Session Confirmed</h2>"
            f"<p><strong>Campaign:</strong> {campaign_name}</p>"
            f"<p><strong>Session:</strong> {session_title}</p>"
            f"<p><strong>When:</strong> {_fmt(confirmed_time)}</p>"
            f"<hr><p style='color:#888;font-size:12px;'>Sent by Quest Board</p>"
        )
        self._send(cfg, subject, body)

    def send_reminder(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        hours_until: int,
        webhook_url: str,  # unused for email; accepted to satisfy protocol
    ) -> None:
        cfg = self._load_config()
        if cfg is None:
            return
        label = _hours_label(hours_until)
        subject = f"[Quest Board] Reminder — {label} until {session_title}!"
        body = (
            f"<h2>⏰ Session Reminder</h2>"
            f"<p><strong>{label}</strong> until your next session!</p>"
            f"<p><strong>Campaign:</strong> {campaign_name}</p>"
            f"<p><strong>Session:</strong> {session_title}</p>"
            f"<p><strong>When:</strong> {_fmt(confirmed_time)}</p>"
            f"<hr><p style='color:#888;font-size:12px;'>Sent by Quest Board</p>"
        )
        self._send(cfg, subject, body)

    def send_test(self, *, to_address: str) -> None:
        """Send a test email to verify SMTP config (called from admin panel)."""
        cfg = self._load_config()
        if cfg is None:
            raise ValueError("SMTP not configured")
        subject = "[Quest Board] Test Email"
        body = (
            "<h2>✅ Quest Board Email Test</h2>"
            "<p>SMTP is configured correctly.  Notifications will be delivered to this address.</p>"
            "<hr><p style='color:#888;font-size:12px;'>Sent by Quest Board</p>"
        )
        self._send(cfg, subject, body, to_override=to_address)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _load_config(self) -> "SmtpConfig | None":  # noqa: F821
        """Load SMTP config synchronously from the database.

        Celery tasks run in a separate process without an async event loop,
        so we use a dedicated sync DB session here.
        """
        try:
            import asyncio
            from app.database import AsyncSessionLocal
            from app.services.settings_service import get_smtp_config

            # Celery tasks have no running event loop; spin up a temporary one.
            loop = asyncio.new_event_loop()
            try:
                async def _fetch():
                    async with AsyncSessionLocal() as db:
                        return await get_smtp_config(db)
                return loop.run_until_complete(_fetch())
            finally:
                loop.close()
        except Exception as exc:
            logger.warning("Failed to load SMTP config: %s", exc)
            return None

    def _send(
        self,
        cfg: "SmtpConfig",  # noqa: F821
        subject: str,
        html_body: str,
        to_override: str | None = None,
    ) -> None:
        to_addr = to_override or cfg.from_address
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.from_address
        msg["To"] = to_addr
        msg.attach(MIMEText(html_body, "html"))
        try:
            if cfg.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(cfg.host, cfg.port, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    if cfg.username:
                        server.login(cfg.username, cfg.password)
                    server.sendmail(cfg.from_address, to_addr, msg.as_string())
            else:
                with smtplib.SMTP(cfg.host, cfg.port, timeout=15) as server:
                    if cfg.username:
                        server.login(cfg.username, cfg.password)
                    server.sendmail(cfg.from_address, to_addr, msg.as_string())
        except Exception as exc:
            logger.warning("Email send failed: %s", exc)


# Module-level singleton
email_backend: NotificationBackend = EmailNotificationBackend()
