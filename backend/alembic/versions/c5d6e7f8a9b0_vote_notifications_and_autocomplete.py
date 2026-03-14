"""Vote notification settings and auto-complete groundwork

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-03-14 00:00:00.000000

Adds:
  campaigns — vote_notification_mode (Text nullable): "each_vote" | "all_voted" | null
  campaigns — vote_auto_close_hours (Integer nullable): auto-close voting after N hours
  sessions  — vote_close_task_id (Text nullable): Celery task ID for auto-close revocation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── campaigns: vote notification settings ──────────────────────────────────
    op.add_column(
        "campaigns",
        sa.Column("vote_notification_mode", sa.Text(), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("vote_auto_close_hours", sa.Integer(), nullable=True),
    )

    # ── sessions: vote auto-close Celery task ID ───────────────────────────────
    op.add_column(
        "sessions",
        sa.Column("vote_close_task_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "vote_close_task_id")
    op.drop_column("campaigns", "vote_auto_close_hours")
    op.drop_column("campaigns", "vote_notification_mode")
