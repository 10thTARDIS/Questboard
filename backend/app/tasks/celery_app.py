"""Celery application instance for Quest Board.

Workers are launched by the `worker` Docker service:
    celery -A app.tasks.celery_app worker --loglevel=info

The beat scheduler (for ETA-based task dispatch) runs in the `beat` service:
    celery -A app.tasks.celery_app beat --loglevel=info

Redis is used as both the broker (database 1) and the result backend (database 2).
All serialization is JSON to avoid pickle-related security risks.
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "quest_board",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Modules containing task definitions — imported by workers on startup
    include=["app.tasks.reminder_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],  # Reject non-JSON content to prevent deserialization attacks
    timezone="UTC",
    enable_utc=True,
)
