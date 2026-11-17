"""The notification aggregate: Notification -> Delivery -> Attempt, and the derived status.

Notification status is never persisted; it is computed from its deliveries so there is one source
of truth and no drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Notification:
    id: int | None
    source: str | None
    content: Content
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Delivery:
    id: int | None
    notification_id: int | None
    channel: Channel
    status: DeliveryStatus
    recipients: tuple[Recipient, ...]
    content: Content
    options: Mapping[str, object]
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Attempt:
    """One execution of a Delivery against a provider. Append-only."""

    id: int | None
    delivery_id: int | None
    attempt_number: int
    outcome: AttemptOutcome
    provider: str
    provider_status: int | None
    error_kind: ErrorKind | None
    error_message: str | None
    retriable: bool
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ChannelRequest:
    """One channel entry of a send request: recipients plus an optional content override."""

    channel: Channel
    recipients: tuple[Recipient, ...] = ()
    content: Content | None = None
    options: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    content: Content
    channels: tuple[ChannelRequest, ...]
    source: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    """A delivery after its synchronous attempt, plus the raw provider body for the legacy contract."""

    delivery: Delivery
    attempts: tuple[Attempt, ...]
    provider_body: str

    @property
    def succeeded(self) -> bool:
        return self.delivery.status is DeliveryStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class NotificationOutcome:
    notification: Notification
    deliveries: tuple[DeliveryOutcome, ...]

    @property
    def status(self) -> NotificationStatus:
        return derive_status([outcome.delivery for outcome in self.deliveries])


def derive_status(deliveries: Sequence[Delivery]) -> NotificationStatus:
    """`succeeded` when every delivery succeeded; `failed` when all are terminal and one failed."""
    if not deliveries:
        return NotificationStatus.PENDING
    statuses = {delivery.status for delivery in deliveries}
    if statuses == {DeliveryStatus.SUCCEEDED}:
        return NotificationStatus.SUCCEEDED
    terminal = {DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED}
    if statuses <= terminal and DeliveryStatus.FAILED in statuses:
        return NotificationStatus.FAILED
    return NotificationStatus.PENDING
