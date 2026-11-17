"""SQLAlchemy entities for the channel slice: provider_config and retry_policy, one row per channel."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from hablator.persistence.configuration.base import Base
from hablator.persistence.configuration.checks import CHANNEL_CHECK


class ProviderConfigEntity(Base):
    __tablename__ = "provider_config"

    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict[str, object]] = mapped_column(mysql.JSON, server_default=text("(JSON_OBJECT())"))
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))

    __table_args__ = (CheckConstraint(CHANNEL_CHECK, name="ck_provider_config_channel"),)


class RetryPolicyEntity(Base):
    __tablename__ = "retry_policy"

    channel: Mapped[str] = mapped_column(String(16), primary_key=True)
    max_attempts: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True))
    backoff_seconds: Mapped[list[int]] = mapped_column(mysql.JSON)
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6))

    __table_args__ = (CheckConstraint(CHANNEL_CHECK, name="ck_retry_policy_channel"),)
