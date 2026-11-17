"""The notification aggregate: the derived status rule and the delivery outcome view."""

from __future__ import annotations

from datetime import UTC, datetime

from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryOutcome,
    DeliveryStatus,
    NotificationStatus,
    derive_status,
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
