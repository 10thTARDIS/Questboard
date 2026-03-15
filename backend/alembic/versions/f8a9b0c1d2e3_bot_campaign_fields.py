"""Add guild_id and notification_channel_id to campaigns.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-03-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("guild_id", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("notification_channel_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "notification_channel_id")
    op.drop_column("campaigns", "guild_id")
