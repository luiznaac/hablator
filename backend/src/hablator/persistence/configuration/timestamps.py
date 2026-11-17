"""Naive-UTC at the database boundary, aware UTC in the domain.

MySQL `DATETIME(6)` has no timezone, so the app writes naive UTC (from the injected clock)
and reads it back tagged as UTC. Domain timestamps are always timezone-aware.
"""

from __future__ import annotations

from datetime import UTC, datetime


def to_db_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def from_db_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC)
    return value.replace(tzinfo=UTC)
