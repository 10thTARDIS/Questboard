"""Initial schema

Revision ID: e3a8f2c1d9b4
Revises:
Create Date: 2026-03-12 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3a8f2c1d9b4"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── PostgreSQL ENUM types ──────────────────────────────────────────────────
    # Created before the tables that reference them.
    op.execute("CREATE TYPE memberrole AS ENUM ('gm', 'player')")
    op.execute("CREATE TYPE schedulingmode AS ENUM ('vote', 'direct', 'tentative')")
    op.execute(
        "CREATE TYPE sessionstatus AS ENUM "
        "('proposed', 'confirmed', 'completed', 'cancelled')"
    )
    op.execute("CREATE TYPE availability AS ENUM ('yes', 'maybe', 'no')")

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("oidc_sub", sa.Text(), nullable=False),
        sa.Column("oidc_issuer", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oidc_sub", "oidc_issuer", name="uq_users_oidc_sub_issuer"),
    )

    # ── campaigns ─────────────────────────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("game_system", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discord_webhook_url", sa.Text(), nullable=True),
        sa.Column("invite_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code", name="uq_campaigns_invite_code"),
    )

    # ── campaign_members ───────────────────────────────────────────────────────
    op.create_table(
        "campaign_members",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.Enum("gm", "player", name="memberrole", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("campaign_id", "user_id"),
    )

    # ── sessions ───────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "scheduling_mode",
            sa.Enum("vote", "direct", "tentative", name="schedulingmode", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "proposed", "confirmed", "completed", "cancelled",
                name="sessionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'proposed'"),
        ),
        sa.Column("confirmed_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("celery_task_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_campaign_id", "sessions", ["campaign_id"])

    # ── time_slots ─────────────────────────────────────────────────────────────
    op.create_table(
        "time_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_slots_session_id", "time_slots", ["session_id"])

    # ── votes ──────────────────────────────────────────────────────────────────
    op.create_table(
        "votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("time_slot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "availability",
            sa.Enum("yes", "maybe", "no", name="availability", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["time_slot_id"], ["time_slots.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("time_slot_id", "user_id", name="uq_votes_slot_user"),
    )
    op.create_index("ix_votes_time_slot_id", "votes", ["time_slot_id"])
    op.create_index("ix_votes_user_id", "votes", ["user_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_votes_user_id", table_name="votes")
    op.drop_index("ix_votes_time_slot_id", table_name="votes")
    op.drop_table("votes")

    op.drop_index("ix_time_slots_session_id", table_name="time_slots")
    op.drop_table("time_slots")

    op.drop_index("ix_sessions_campaign_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_table("campaign_members")
    op.drop_table("campaigns")
    op.drop_table("users")

    # Drop ENUM types after all tables that reference them are gone
    op.execute("DROP TYPE availability")
    op.execute("DROP TYPE sessionstatus")
    op.execute("DROP TYPE schedulingmode")
    op.execute("DROP TYPE memberrole")
