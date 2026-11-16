"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-16 21:00:00.000000

The empty starting point of the schema history. The hub's five tables land in
`0002_notification_hub`; this baseline exists so every later revision has a parent and so a
database created before migrations existed can be stamped instead of re-run.
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
