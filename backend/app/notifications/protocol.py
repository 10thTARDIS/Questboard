"""Pluggable notification backend protocol.

Any notification backend must implement these two methods.  New backends
(email, Slack, etc.) can be added without touching the service layer.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationBackend(Protocol):
    def send_confirmation(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        webhook_url: str,
    ) -> None:
        """Notify members that a session has been confirmed."""
        ...

    def send_reminder(
        self,
        *,
        campaign_name: str,
        session_title: str,
        confirmed_time: datetime,
        hours_until: int,
        webhook_url: str,
    ) -> None:
        """Send a reminder ahead of a confirmed session."""
        ...
