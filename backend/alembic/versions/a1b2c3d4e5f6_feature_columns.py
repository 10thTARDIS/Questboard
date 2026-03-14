"""Feature columns: user profile, campaign settings, session notes

Revision ID: a1b2c3d4e5f6
Revises: e3a8f2c1d9b4
Create Date: 2026-03-14 00:00:00.000000

Adds:
  users         — display_name_override, timezone, is_admin, last_login_at
  campaigns     — timezone, reminder_offsets_minutes
  campaign_members — character_name
  session_notes — new table (one note per user per session)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e3a8f2c1d9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.add_column("users", sa.Column("display_name_override", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── campaigns ─────────────────────────────────────────────────────────────
    op.add_column("campaigns", sa.Column("timezone", sa.Text(), nullable=True))
    op.add_column(
        "campaigns",
        sa.Column(
            "reminder_offsets_minutes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # ── campaign_members ───────────────────────────────────────────────────────
    op.add_column(
        "campaign_members",
        sa.Column("character_name", sa.Text(), nullable=True),
    )

    # ── session_notes ──────────────────────────────────────────────────────────
    op.create_table(
        "session_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_notes_session_user"),
    )
    op.create_index("ix_session_notes_session_id", "session_notes", ["session_id"])
    op.create_index("ix_session_notes_user_id", "session_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_session_notes_user_id", table_name="session_notes")
    op.drop_index("ix_session_notes_session_id", table_name="session_notes")
    op.drop_table("session_notes")

    op.drop_column("campaign_members", "character_name")
    op.drop_column("campaigns", "reminder_offsets_minutes")
    op.drop_column("campaigns", "timezone")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "timezone")
    op.drop_column("users", "display_name_override")
