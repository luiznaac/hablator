"""The notification aggregate: the derived status rule and the delivery outcome view."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.commons.exceptions import (
    DeliveryNotRetriableError,
    InvalidArgumentError,
    InvalidTransitionError,
)
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryOutcome,
    DeliveryStatus,
    NotificationStatus,
    derive_status,
    derive_status_from_statuses,
    reopen_for_retry,
    transition,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _delivery(status: DeliveryStatus) -> Delivery:
    return Delivery(
        id=1,
        notification_id=1,
        channel=Channel.EMAIL,
        status=status,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="b"),
        options={},
        next_attempt_at=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_every_delivery_succeeded_derives_succeeded() -> None:
    assert derive_status([_delivery(DeliveryStatus.SUCCEEDED)]) is NotificationStatus.SUCCEEDED


def test_all_terminal_with_a_failure_derives_failed() -> None:
    deliveries = [_delivery(DeliveryStatus.SUCCEEDED), _delivery(DeliveryStatus.FAILED)]

    assert derive_status(deliveries) is NotificationStatus.FAILED


def test_any_non_terminal_delivery_derives_pending() -> None:
    assert derive_status([_delivery(DeliveryStatus.PENDING)]) is NotificationStatus.PENDING
    assert derive_status([_delivery(DeliveryStatus.IN_PROGRESS)]) is NotificationStatus.PENDING
    assert (
        derive_status([_delivery(DeliveryStatus.SUCCEEDED), _delivery(DeliveryStatus.IN_PROGRESS)])
        is NotificationStatus.PENDING
    )


def test_no_deliveries_is_pending() -> None:
    assert derive_status([]) is NotificationStatus.PENDING


def test_delivery_outcome_reports_success_from_its_delivery_status() -> None:
    attempt = Attempt(
        id=1,
        delivery_id=1,
        attempt_number=1,
        outcome=AttemptOutcome.SUCCEEDED,
        provider="mailgun",
        provider_status=200,
        error_kind=None,
        error_message=None,
        retriable=False,
        started_at=_NOW,
        finished_at=_NOW,
    )
    succeeded = DeliveryOutcome(
        delivery=_delivery(DeliveryStatus.SUCCEEDED),
        attempts=(attempt,),
        provider_body="queued",
    )
    failed = DeliveryOutcome(
        delivery=_delivery(DeliveryStatus.FAILED),
        attempts=(attempt,),
        provider_body="boom",
    )

    assert succeeded.succeeded is True
    assert failed.succeeded is False


def _later() -> datetime:

    return _NOW + timedelta(minutes=5)


def test_pending_transitions_to_in_progress() -> None:
    moved = transition(_delivery(DeliveryStatus.PENDING), DeliveryStatus.IN_PROGRESS, now=_later())

    assert moved.status is DeliveryStatus.IN_PROGRESS
    assert moved.updated_at == _later()
    assert moved.next_attempt_at is None


def test_in_progress_transitions_to_a_terminal_status() -> None:
    succeeded = transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.SUCCEEDED, now=_later())
    failed = transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.FAILED, now=_later())

    assert succeeded.status is DeliveryStatus.SUCCEEDED
    assert failed.status is DeliveryStatus.FAILED


def test_in_progress_returns_to_pending_with_the_next_attempt() -> None:
    moved = transition(
        _delivery(DeliveryStatus.IN_PROGRESS),
        DeliveryStatus.PENDING,
        now=_later(),
        next_attempt_at=_later(),
    )

    assert moved.status is DeliveryStatus.PENDING
    assert moved.next_attempt_at == _later()


def test_in_progress_returning_to_pending_requires_a_next_attempt() -> None:
    with pytest.raises(InvalidArgumentError):
        transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.PENDING, now=_later())


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DeliveryStatus.PENDING, DeliveryStatus.SUCCEEDED),
        (DeliveryStatus.PENDING, DeliveryStatus.FAILED),
        (DeliveryStatus.SUCCEEDED, DeliveryStatus.IN_PROGRESS),
        (DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED),
        (DeliveryStatus.FAILED, DeliveryStatus.IN_PROGRESS),
        (DeliveryStatus.FAILED, DeliveryStatus.PENDING),
    ],
)
def test_forbidden_lifecycle_transitions(current: DeliveryStatus, target: DeliveryStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(_delivery(current), target, now=_later(), next_attempt_at=_later())


def test_reopen_for_retry_moves_a_failed_delivery_back_to_pending() -> None:
    reopened = reopen_for_retry(_delivery(DeliveryStatus.FAILED), now=_later())

    assert reopened.status is DeliveryStatus.PENDING
    assert reopened.next_attempt_at is None
    assert reopened.updated_at == _later()


def test_reopen_for_retry_leaves_a_pending_delivery_pending() -> None:
    reopened = reopen_for_retry(_delivery(DeliveryStatus.PENDING), now=_later())

    assert reopened.status is DeliveryStatus.PENDING
    assert reopened.updated_at == _later()


@pytest.mark.parametrize("status", [DeliveryStatus.IN_PROGRESS, DeliveryStatus.SUCCEEDED])
def test_reopen_for_retry_rejects_a_delivery_that_is_not_retriable(status: DeliveryStatus) -> None:
    with pytest.raises(DeliveryNotRetriableError):
        reopen_for_retry(_delivery(status), now=_later())


def test_derive_status_from_statuses_matches_derive_status() -> None:
    statuses = [DeliveryStatus.SUCCEEDED, DeliveryStatus.FAILED]

    assert derive_status_from_statuses(statuses) is derive_status([_delivery(status) for status in statuses])
