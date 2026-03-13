"""Discord webhook notification backend.

Uses a synchronous httpx.post so it can be called from Celery tasks
without requiring an async event loop.
"""

from datetime import datetime, timezone

import httpx

from app.notifications.protocol import NotificationBackend


def _fmt(dt: datetime) -> str:
    """Format a datetime for display in Discord embeds."""
    return dt.astimezone(timezone.utc).strftime("%a, %b %-d %Y at %H:%M UTC")


def _hours_label(hours_until: int) -> str:
    if hours_until >= 7 * 24:
        return "1 week"
    if hours_until >= 24:
        return "24 hours"
    return "1 hour"


class DiscordNotificationBackend:
    """Sends rich embeds to a Discord channel via webhook."""

    # Discord blurple
    _COLOR_INFO = 0x5865F2
    _COLOR_REMINDER = 0xF0A500

    def send_confirmation(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        webhook_url: str,
    ) -> None:
        payload = {
            "embeds": [
                {
                    "title": f"✅ Session Confirmed — {session_title}",
                    "color": self._COLOR_INFO,
                    "fields": [
                        {"name": "Campaign", "value": campaign_name, "inline": True},
                        {
                            "name": "When",
                            "value": _fmt(confirmed_time),
                            "inline": True,
                        },
                    ],
                    "footer": {"text": "Quest Board"},
                }
            ]
        }
        self._post(webhook_url, payload)

    def send_reminder(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        hours_until: int,
        webhook_url: str,
    ) -> None:
        label = _hours_label(hours_until)
        payload = {
            "embeds": [
                {
                    "title": f"⏰ Reminder — {label} until {session_title}!",
                    "color": self._COLOR_REMINDER,
                    "fields": [
                        {"name": "Campaign", "value": campaign_name, "inline": True},
                        {
                            "name": "When",
                            "value": _fmt(confirmed_time),
                            "inline": True,
                        },
                    ],
                    "footer": {"text": "Quest Board"},
                }
            ]
        }
        self._post(webhook_url, payload)

    @staticmethod
    def _post(webhook_url: str, payload: dict) -> None:
        try:
            resp = httpx.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Log but don't crash the worker — notifications are best-effort.
            import logging
            logging.getLogger(__name__).warning(
                "Discord webhook failed: %s", exc
            )


# Module-level singleton used by Celery tasks and the service layer.
discord_backend: NotificationBackend = DiscordNotificationBackend()
