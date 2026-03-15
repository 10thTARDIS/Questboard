"""v0.3.2 — lore_entries table

Revision ID: 930af97f5798
Revises: 98520cae8a4b
Create Date: 2026-03-15

Changes:
  lore_entries — new table for campaign wiki entries
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "930af97f5798"
down_revision = "98520cae8a4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lore_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum("location", "faction", "npc", "item", "event", "other", name="loretype"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("linked_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lore_entries_campaign_id", "lore_entries", ["campaign_id"])
    op.create_index("ix_lore_entries_linked_session_id", "lore_entries", ["linked_session_id"])


def downgrade() -> None:
    op.drop_index("ix_lore_entries_linked_session_id", table_name="lore_entries")
    op.drop_index("ix_lore_entries_campaign_id", table_name="lore_entries")
    op.drop_table("lore_entries")
    op.execute("DROP TYPE IF EXISTS loretype")
