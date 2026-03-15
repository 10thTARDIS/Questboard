"""Allow one note per (session, user, visibility) instead of per (session, user)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-14 00:00:00.000000

The old constraint allowed only one note per (session_id, user_id).
This prevented GMs from having both a private note and a public note on
the same session.  The new constraint is (session_id, user_id, visibility),
allowing at most one note of each visibility type per user per session.

Existing notes are unaffected — they all have visibility='private' and
satisfy the new constraint.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_session_notes_session_user",
        "session_notes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_session_notes_session_user_visibility",
        "session_notes",
        ["session_id", "user_id", "visibility"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_session_notes_session_user_visibility",
        "session_notes",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_session_notes_session_user",
        "session_notes",
        ["session_id", "user_id"],
    )
