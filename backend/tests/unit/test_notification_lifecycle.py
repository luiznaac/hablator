"""The lifecycle is `pending -> in_progress -> succeeded | failed`; status is derived, never stored."""

from __future__ import annotations

from dataclasses import replace

import pytest

from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.commons.exceptions import InvalidArgumentError, InvalidTransitionError
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryStatus,
    Notification,
    NotificationStatus,
    derive_notification_status,
    transition,
)
from tests.fixtures import LATER, NOW


def _delivery(status: DeliveryStatus = DeliveryStatus.PENDING) -> Delivery:
    return Delivery(
        id=77,
        notification_id=42,
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="Backup finished", body="done"),
        options={},
        status=status,
        next_attempt_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], NotificationStatus.PENDING),
        ([DeliveryStatus.SUCCEEDED], NotificationStatus.SUCCEEDED),
        ([DeliveryStatus.SUCCEEDED, DeliveryStatus.SUCCEEDED], NotificationStatus.SUCCEEDED),
        ([DeliveryStatus.FAILED], NotificationStatus.FAILED),
        ([DeliveryStatus.FAILED, DeliveryStatus.SUCCEEDED], NotificationStatus.FAILED),
        ([DeliveryStatus.FAILED, DeliveryStatus.PENDING], NotificationStatus.PENDING),
        ([DeliveryStatus.SUCCEEDED, DeliveryStatus.IN_PROGRESS], NotificationStatus.PENDING),
        ([DeliveryStatus.PENDING], NotificationStatus.PENDING),
    ],
)
def test_derived_notification_status(statuses: list[DeliveryStatus], expected: NotificationStatus) -> None:
    assert derive_notification_status(statuses) is expected


def test_notification_status_derives_from_its_deliveries() -> None:
    notification = Notification(
        id=42,
        source="valoab",
        content=Content(subject="Backup finished", body="done"),
        created_at=NOW,
        deliveries=(
            _delivery(DeliveryStatus.SUCCEEDED),
            replace(_delivery(DeliveryStatus.SUCCEEDED), id=78, channel=Channel.PUSH),
        ),
    )

    assert notification.status is NotificationStatus.SUCCEEDED


def test_pending_transitions_to_in_progress() -> None:
    moved = transition(_delivery(), DeliveryStatus.IN_PROGRESS, now=LATER)

    assert moved.status is DeliveryStatus.IN_PROGRESS
    assert moved.updated_at == LATER
    assert moved.next_attempt_at is None


def test_in_progress_transitions_to_succeeded() -> None:
    moved = transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.SUCCEEDED, now=LATER)

    assert moved.status is DeliveryStatus.SUCCEEDED
    assert moved.next_attempt_at is None


def test_in_progress_transitions_to_failed() -> None:
    moved = transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.FAILED, now=LATER)

    assert moved.status is DeliveryStatus.FAILED


def test_in_progress_returns_to_pending_with_the_next_attempt() -> None:
    moved = transition(
        _delivery(DeliveryStatus.IN_PROGRESS),
        DeliveryStatus.PENDING,
        now=LATER,
        next_attempt_at=LATER,
    )

    assert moved.status is DeliveryStatus.PENDING
    assert moved.next_attempt_at == LATER


def test_in_progress_returning_to_pending_requires_a_next_attempt() -> None:
    with pytest.raises(InvalidArgumentError):
        transition(_delivery(DeliveryStatus.IN_PROGRESS), DeliveryStatus.PENDING, now=LATER)


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
def test_forbidden_transitions(current: DeliveryStatus, target: DeliveryStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(_delivery(current), target, now=LATER, next_attempt_at=LATER)


def test_a_retriable_failure_records_a_retriable_attempt() -> None:
    attempt = Attempt(
        attempt_number=1,
        outcome=AttemptOutcome.FAILED,
        provider="mailgun",
        provider_status=503,
        error_kind=None,
        error_message="service unavailable",
        retriable=True,
        started_at=NOW,
        finished_at=LATER,
    )

    assert attempt.retriable is True
    assert attempt.outcome is AttemptOutcome.FAILED
