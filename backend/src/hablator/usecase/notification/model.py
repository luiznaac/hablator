"""The notification aggregate: Notification -> Delivery -> Attempt, and the derived status.

Notification status is never persisted; it is computed from its deliveries so there is one source
of truth and no drift.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient
from hablator.usecase.commons.exceptions import (
    DeliveryNotRetriableError,
    InvalidArgumentError,
    InvalidTransitionError,
)


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


def derive_status_from_statuses(statuses: Iterable[DeliveryStatus]) -> NotificationStatus:
    """`succeeded` when every delivery succeeded; `failed` when all are terminal and one failed."""
    status_set = set(statuses)
    if not status_set:
        return NotificationStatus.PENDING
    if status_set == {DeliveryStatus.SUCCEEDED}:
        return NotificationStatus.SUCCEEDED
    terminal = {DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED}
    if status_set <= terminal and DeliveryStatus.FAILED in status_set:
        return NotificationStatus.FAILED
    return NotificationStatus.PENDING


def derive_status(deliveries: Sequence[Delivery]) -> NotificationStatus:
    """`succeeded` when every delivery succeeded; `failed` when all are terminal and one failed."""
    return derive_status_from_statuses(delivery.status for delivery in deliveries)


_ALLOWED_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.PENDING: frozenset({DeliveryStatus.IN_PROGRESS}),
    DeliveryStatus.IN_PROGRESS: frozenset({DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED, DeliveryStatus.PENDING}),
    DeliveryStatus.SUCCEEDED: frozenset(),
    DeliveryStatus.FAILED: frozenset(),
}


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


_MANUALLY_RETRIABLE: frozenset[DeliveryStatus] = frozenset({DeliveryStatus.PENDING, DeliveryStatus.FAILED})


def reopen_for_retry(delivery: Delivery, *, now: datetime) -> Delivery:
    """Prepare a delivery for a manual retry: a failed one reopens as pending, a pending one stays.

    This is the manual-retry counterpart of `transition`: the retry is synchronous, so no
    `next_attempt_at` is scheduled, and `transition`'s scheduling invariant does not apply.

    Raises:
        DeliveryNotRetriableError: when the delivery is in progress or already succeeded.
    """
    if delivery.status not in _MANUALLY_RETRIABLE:
        raise DeliveryNotRetriableError(delivery.status.value)
    return replace(delivery, status=DeliveryStatus.PENDING, next_attempt_at=None, updated_at=now)


@dataclass(frozen=True, slots=True)
class DeliveryDetail:
    """A delivery plus its append-only attempts, as read for a notification detail."""

    delivery: Delivery
    attempts: tuple[Attempt, ...]


@dataclass(frozen=True, slots=True)
class NotificationDetail:
    """A notification read back with its deliveries and their attempts."""

    notification: Notification
    deliveries: tuple[DeliveryDetail, ...]

    @property
    def status(self) -> NotificationStatus:
        return derive_status([detail.delivery for detail in self.deliveries])


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


MIN_PAGE_LIMIT = 1
MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """History filters; `created_after` is inclusive and `created_before` exclusive."""

    source: str | None = None
    channel: Channel | None = None
    status: NotificationStatus | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0
