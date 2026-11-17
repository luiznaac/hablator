"""SQLAlchemy 2.0 entities for per-channel configuration (provider_config, retry_policy).

`retry_policy` is part of the decided schema although retry execution belongs to chameidor; it is
declared so the schema and its migration stay in lockstep.
"""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from hablator.persistence.configuration.base import Base

_TIMESTAMP = mysql.DATETIME(fsp=6)
_CHANNEL_CHECK = "channel IN ('email', 'push', 'sms', 'voice')"


class ProviderConfigEntity(Base):
    __tablename__ = "provider_config"

    channel: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        mysql.JSON, nullable=False, server_default=sa.text("(JSON_OBJECT())")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)

    __table_args__ = (sa.CheckConstraint(_CHANNEL_CHECK, name="ck_provider_config_channel"),)


class RetryPolicyEntity(Base):
    __tablename__ = "retry_policy"

    channel: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    max_attempts: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True), nullable=False)
    backoff_seconds: Mapped[list[int]] = mapped_column(mysql.JSON, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(_TIMESTAMP, nullable=False)

    __table_args__ = (sa.CheckConstraint(_CHANNEL_CHECK, name="ck_retry_policy_channel"),)
