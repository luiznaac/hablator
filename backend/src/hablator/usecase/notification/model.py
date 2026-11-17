"""Notification, Delivery and Attempt — the hub's three nouns.

`Notification.status` is derived from its deliveries and never persisted. The lifecycle
is `pending -> in_progress -> succeeded | failed`; a retriable failure with attempts left
returns to `pending` with `next_attempt_at`, so there is no `retrying` state.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime

from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient
from hablator.usecase.commons.exceptions import InvalidArgumentError, InvalidTransitionError


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AttemptOutcome(enum.StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_TERMINAL_DELIVERY_STATUSES = frozenset({DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED})
_ALLOWED_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.PENDING: frozenset({DeliveryStatus.IN_PROGRESS}),
    DeliveryStatus.IN_PROGRESS: frozenset({DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED, DeliveryStatus.PENDING}),
    DeliveryStatus.SUCCEEDED: frozenset(),
    DeliveryStatus.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Attempt:
    """One execution of a Delivery against a provider — append-only, never updated."""

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
class Delivery:
    """The intent to deliver one Notification through one channel."""

    id: int
    notification_id: int
    channel: Channel
    recipients: tuple[Recipient, ...]
    content: Content
    options: Mapping[str, object]
    status: DeliveryStatus
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: tuple[Attempt, ...] = ()


@dataclass(frozen=True, slots=True)
class Notification:
    """The request. Its status is derived from its deliveries, never stored."""

    id: int
    source: str | None
    content: Content
    created_at: datetime
    deliveries: tuple[Delivery, ...] = ()

    @property
    def status(self) -> NotificationStatus:
        return derive_notification_status(delivery.status for delivery in self.deliveries)


@dataclass(frozen=True, slots=True)
class NewDelivery:
    """The creation shape of a Delivery: no id, no status, no timestamps."""

    channel: Channel
    recipients: tuple[Recipient, ...]
    content: Content
    options: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NewNotification:
    """The creation shape of a Notification with its pending deliveries."""

    source: str | None
    content: Content
    deliveries: tuple[NewDelivery, ...]


@dataclass(frozen=True, slots=True)
class NotificationSummary:
    """One history row: the notification's identity, derived status and channels."""

    id: int
    source: str | None
    subject: str | None
    status: NotificationStatus
    created_at: datetime
    channels: tuple[Channel, ...]


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: tuple[T, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """History filters; `created_after` is inclusive and `created_before` exclusive."""

    source: str | None = None
    channel: Channel | None = None
    status: NotificationStatus | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = 20
    offset: int = 0


def derive_notification_status(statuses: Iterable[DeliveryStatus]) -> NotificationStatus:
    """`succeeded` when every delivery succeeded, `failed` when all are terminal with a failure."""
    delivery_statuses = tuple(statuses)
    if not delivery_statuses:
        return NotificationStatus.PENDING
    if all(status is DeliveryStatus.SUCCEEDED for status in delivery_statuses):
        return NotificationStatus.SUCCEEDED
    if any(status is DeliveryStatus.FAILED for status in delivery_statuses) and all(
        status in _TERMINAL_DELIVERY_STATUSES for status in delivery_statuses
    ):
        return NotificationStatus.FAILED
    return NotificationStatus.PENDING


def transition(
    delivery: Delivery,
    target: DeliveryStatus,
    *,
    now: datetime,
    next_attempt_at: datetime | None = None,
) -> Delivery:
    """Move a delivery along the lifecycle, enforcing the retry scheduling invariant.

    A move back to `pending` must carry `next_attempt_at`; every other move clears it.

    Raises:
        InvalidTransitionError: when the lifecycle does not allow the move.
        InvalidArgumentError: when `next_attempt_at` contradicts the target status.
    """
    if target not in _ALLOWED_TRANSITIONS[delivery.status]:
        raise InvalidTransitionError(delivery.status.value, target.value)
    if target is DeliveryStatus.PENDING and next_attempt_at is None:
        raise InvalidArgumentError("A delivery returning to pending requires next_attempt_at")
    if target is not DeliveryStatus.PENDING and next_attempt_at is not None:
        raise InvalidArgumentError(f"A delivery moving to {target.value} cannot carry next_attempt_at")
    return replace(delivery, status=target, next_attempt_at=next_attempt_at, updated_at=now)
