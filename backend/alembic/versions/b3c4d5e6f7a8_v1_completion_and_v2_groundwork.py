"""v1 completion features + v2 groundwork schema

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-14 00:00:00.000000

Adds:
  session_attendance — tracks who attended a completed session (GM-set)
  session_notes      — adds visibility column (private/public) for GM public notes
  platform_links     — (v2 groundwork) links users to Discord/Matrix accounts
  sessions           — adds transcript/summary/recording_url for v2 transcription
  app_settings       — generic key/value store for admin-configurable settings

Data migration:
  If no admin users exist, promotes the first registered user (by created_at)
  to admin.  Fixes the case where the admin feature was added after accounts
  were already created.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── session_attendance ─────────────────────────────────────────────────────
    op.create_table(
        "session_attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "attended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "noted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "user_id", name="uq_session_attendance_session_user"
        ),
    )
    op.create_index(
        "ix_session_attendance_session_id", "session_attendance", ["session_id"]
    )
    op.create_index(
        "ix_session_attendance_user_id", "session_attendance", ["user_id"]
    )

    # ── session_notes: add visibility column ───────────────────────────────────
    note_visibility_enum = sa.Enum("private", "public", name="notevisibility")
    note_visibility_enum.create(op.get_bind())
    op.add_column(
        "session_notes",
        sa.Column(
            "visibility",
            sa.Enum("private", "public", name="notevisibility"),
            nullable=False,
            server_default=sa.text("'private'"),
        ),
    )

    # ── platform_links (v2 groundwork) ────────────────────────────────────────
    platform_enum = sa.Enum("discord", "matrix", name="platformtype")
    platform_enum.create(op.get_bind())
    op.create_table(
        "platform_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("discord", "matrix", name="platformtype"),
            nullable=False,
        ),
        sa.Column("platform_user_id", sa.Text(), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "platform", name="uq_platform_links_user_platform"),
    )
    op.create_index("ix_platform_links_user_id", "platform_links", ["user_id"])

    # ── sessions: v2 transcription fields ─────────────────────────────────────
    op.add_column("sessions", sa.Column("recording_url", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("transcript", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("transcript_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── app_settings ───────────────────────────────────────────────────────────
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # ── Admin bootstrap data migration ─────────────────────────────────────────
    # If no admin user exists yet (i.e. the admin feature was added after
    # existing users were created), promote the earliest registered user.
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE users
            SET is_admin = true
            WHERE id = (
                SELECT id FROM users ORDER BY created_at ASC LIMIT 1
            )
            AND NOT EXISTS (
                SELECT 1 FROM users WHERE is_admin = true
            )
        """)
    )


def downgrade() -> None:
    op.drop_table("app_settings")

    op.drop_column("sessions", "transcript_updated_at")
    op.drop_column("sessions", "summary")
    op.drop_column("sessions", "transcript")
    op.drop_column("sessions", "recording_url")

    op.drop_index("ix_platform_links_user_id", table_name="platform_links")
    op.drop_table("platform_links")
    sa.Enum(name="platformtype").drop(op.get_bind())

    op.drop_column("session_notes", "visibility")
    sa.Enum(name="notevisibility").drop(op.get_bind())

    op.drop_index(
        "ix_session_attendance_user_id", table_name="session_attendance"
    )
    op.drop_index(
        "ix_session_attendance_session_id", table_name="session_attendance"
    )
    op.drop_table("session_attendance")
