"""v0.3.1 — character sheet fields and recap email opt-ins

Revision ID: 98520cae8a4b
Revises: f8a9b0c1d2e3
Create Date: 2026-03-15

Changes:
  campaign_members — character_sheet_url (Text, nullable)
                   — character_sheet_notes (Text, nullable)
  campaigns        — recap_email_enabled (Boolean, default false)
  users            — recap_email_opt_in (Boolean, default false)
"""

from alembic import op
import sqlalchemy as sa

revision = "98520cae8a4b"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaign_members", sa.Column("character_sheet_url", sa.Text(), nullable=True))
    op.add_column("campaign_members", sa.Column("character_sheet_notes", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("recap_email_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("recap_email_opt_in", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("users", "recap_email_opt_in")
    op.drop_column("campaigns", "recap_email_enabled")
    op.drop_column("campaign_members", "character_sheet_notes")
    op.drop_column("campaign_members", "character_sheet_url")
