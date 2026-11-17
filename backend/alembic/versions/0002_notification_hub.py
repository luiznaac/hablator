"""notification hub schema

Revision ID: 0002_notification_hub
Revises: 0001_baseline
Create Date: 2026-11-16 22:30:00.000000

The five decided tables: notification, delivery, attempt, provider_config and retry_policy.
`retry_policy` is intentionally present although retry execution belongs to chameidor.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0002_notification_hub"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}
_TIMESTAMP = mysql.DATETIME(fsp=6)
_CHANNEL_CHECK = "channel IN ('email', 'push', 'sms', 'voice')"
_JSON_EMPTY = sa.text("(JSON_OBJECT())")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column("body_text", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("body_html", mysql.MEDIUMTEXT(), nullable=True),
        sa.Column("created_at", _TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_OPTIONS,
    )
    op.create_index("ix_notification_created_at", "notification", ["created_at"])
    op.create_index("ix_notification_source_created_at", "notification", ["source", "created_at"])

    op.create_table(
        "delivery",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("recipients", mysql.JSON(), nullable=False),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column("body_text", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("body_html", mysql.MEDIUMTEXT(), nullable=True),
        sa.Column("options", mysql.JSON(), nullable=False, server_default=_JSON_EMPTY),
        sa.Column("next_attempt_at", _TIMESTAMP, nullable=True),
        sa.Column("created_at", _TIMESTAMP, nullable=False),
        sa.Column("updated_at", _TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notification.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("channel IN ('email', 'push', 'sms', 'voice')", name="ck_delivery_channel"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'succeeded', 'failed')",
            name="ck_delivery_status",
        ),
        **_TABLE_OPTIONS,
    )
    op.create_index("ix_delivery_notification_id", "delivery", ["notification_id"])
    op.create_index("ix_delivery_status_next_attempt_at", "delivery", ["status", "next_attempt_at"])
    op.create_index("ix_delivery_channel_status_created_at", "delivery", ["channel", "status", "created_at"])

    op.create_table(
        "attempt",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("delivery_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_number", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_status", mysql.SMALLINT(), nullable=True),
        sa.Column("error_kind", sa.String(32), nullable=True),
        sa.Column("error_message", mysql.TEXT(), nullable=True),
        sa.Column("retriable", mysql.TINYINT(display_width=1), nullable=False),
        sa.Column("started_at", _TIMESTAMP, nullable=False),
        sa.Column("finished_at", _TIMESTAMP, nullable=True),
        sa.ForeignKeyConstraint(["delivery_id"], ["delivery.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", "attempt_number", name="uq_attempt_delivery_number"),
        sa.CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_attempt_outcome"),
        **_TABLE_OPTIONS,
    )

    op.create_table(
        "provider_config",
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("config", mysql.JSON(), nullable=False, server_default=_JSON_EMPTY),
        sa.Column("updated_at", _TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("channel"),
        sa.CheckConstraint(_CHANNEL_CHECK, name="ck_provider_config_channel"),
        **_TABLE_OPTIONS,
    )

    op.create_table(
        "retry_policy",
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("max_attempts", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("backoff_seconds", mysql.JSON(), nullable=False),
        sa.Column("updated_at", _TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("channel"),
        sa.CheckConstraint(_CHANNEL_CHECK, name="ck_retry_policy_channel"),
        **_TABLE_OPTIONS,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("retry_policy")
    op.drop_table("provider_config")
    op.drop_table("attempt")
    op.drop_index("ix_delivery_channel_status_created_at", table_name="delivery")
    op.drop_index("ix_delivery_status_next_attempt_at", table_name="delivery")
    op.drop_index("ix_delivery_notification_id", table_name="delivery")
    op.drop_table("delivery")
    op.drop_index("ix_notification_source_created_at", table_name="notification")
    op.drop_index("ix_notification_created_at", table_name="notification")
    op.drop_table("notification")
