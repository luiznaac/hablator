"""SQLAlchemy entities for the notification aggregate: notification, delivery, attempt."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hablator.persistence.configuration.base import Base
from hablator.persistence.configuration.checks import CHANNEL_CHECK


class NotificationEntity(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str | None] = mapped_column(String(64))
    subject: Mapped[str | None] = mapped_column(String(998))
    body_text: Mapped[str] = mapped_column(mysql.MEDIUMTEXT)
    body_html: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT)
    created_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))

    deliveries: Mapped[list[DeliveryEntity]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="DeliveryEntity.id",
        lazy="raise",
    )

    __table_args__ = (
        Index("ix_notification_created_at", "created_at"),
        Index("ix_notification_source_created_at", "source", "created_at"),
    )


class DeliveryEntity(Base):
    __tablename__ = "delivery"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(BigInteger)
    channel: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    recipients: Mapped[list[str]] = mapped_column(mysql.JSON)
    subject: Mapped[str | None] = mapped_column(String(998))
    body_text: Mapped[str] = mapped_column(mysql.MEDIUMTEXT)
    body_html: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT)
    options: Mapped[dict[str, object]] = mapped_column(mysql.JSON, server_default=text("(JSON_OBJECT())"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))

    notification: Mapped[NotificationEntity] = relationship(back_populates="deliveries")
    attempts: Mapped[list[AttemptEntity]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        order_by="AttemptEntity.attempt_number",
        lazy="raise",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["notification_id"],
            ["notification.id"],
            name="fk_delivery_notification",
            ondelete="CASCADE",
        ),
        Index("ix_delivery_notification_id", "notification_id"),
        Index("ix_delivery_status_next_attempt_at", "status", "next_attempt_at"),
        Index("ix_delivery_channel_status_created_at", "channel", "status", "created_at"),
        CheckConstraint(CHANNEL_CHECK, name="ck_delivery_channel"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'succeeded', 'failed')",
            name="ck_delivery_status",
        ),
    )


class AttemptEntity(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(BigInteger)
    attempt_number: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True))
    outcome: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    provider_status: Mapped[int | None] = mapped_column(SmallInteger)
    error_kind: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(mysql.TEXT)
    retriable: Mapped[bool] = mapped_column(mysql.TINYINT(display_width=1))
    started_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))
    finished_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6))

    delivery: Mapped[DeliveryEntity] = relationship(back_populates="attempts")

    __table_args__ = (
        ForeignKeyConstraint(
            ["delivery_id"],
            ["delivery.id"],
            name="fk_attempt_delivery",
            ondelete="CASCADE",
        ),
        UniqueConstraint("delivery_id", "attempt_number", name="uq_attempt_delivery_number"),
        CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_attempt_outcome"),
    )
