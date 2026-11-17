"""SQLAlchemy 2.0 entities for the notification aggregate (notification, delivery, attempt).

The schema contract is `0002_notification_hub`; `tests/integration/test_migrations.py` keeps these
entities and that migration from drifting.
"""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from hablator.persistence.configuration.base import Base

_TIMESTAMP = mysql.DATETIME(fsp=6)
_BIGINT = sa.BigInteger


class NotificationEntity(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(_BIGINT, primary_key=True, autoincrement=True)
    source: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(sa.String(998), nullable=True)
    body_text: Mapped[str] = mapped_column(mysql.MEDIUMTEXT, nullable=False)
    body_html: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)

    __table_args__ = (
        sa.Index("ix_notification_created_at", "created_at"),
        sa.Index("ix_notification_source_created_at", "source", "created_at"),
    )


class DeliveryEntity(Base):
    __tablename__ = "delivery"

    id: Mapped[int] = mapped_column(_BIGINT, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        _BIGINT,
        sa.ForeignKey("notification.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(mysql.JSON, nullable=False)
    subject: Mapped[str | None] = mapped_column(sa.String(998), nullable=True)
    body_text: Mapped[str] = mapped_column(mysql.MEDIUMTEXT, nullable=False)
    body_html: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT, nullable=True)
    options: Mapped[dict[str, Any]] = mapped_column(
        mysql.JSON, nullable=False, server_default=sa.text("(JSON_OBJECT())")
    )
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(_TIMESTAMP, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)

    __table_args__ = (
        sa.Index("ix_delivery_notification_id", "notification_id"),
        sa.Index("ix_delivery_status_next_attempt_at", "status", "next_attempt_at"),
        sa.Index("ix_delivery_channel_status_created_at", "channel", "status", "created_at"),
        sa.CheckConstraint("channel IN ('email', 'push', 'sms', 'voice')", name="ck_delivery_channel"),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'succeeded', 'failed')", name="ck_delivery_status"),
    )


class AttemptEntity(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(_BIGINT, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(
        _BIGINT,
        sa.ForeignKey("delivery.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    provider_status: Mapped[int | None] = mapped_column(mysql.SMALLINT, nullable=True)
    error_kind: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(mysql.TEXT, nullable=True)
    retriable: Mapped[bool] = mapped_column(mysql.TINYINT(display_width=1), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(_TIMESTAMP, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("delivery_id", "attempt_number", name="uq_attempt_delivery_number"),
        sa.CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_attempt_outcome"),
    )
