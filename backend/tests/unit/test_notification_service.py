"""NotificationService: create-then-fan-out, content resolution and the aggregated outcome."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.commons.time import FixedClock
from hablator.usecase.notification.model import (
    ChannelRequest,
    Delivery,
    DeliveryOutcome,
    DeliveryStatus,
    NotificationRequest,
    NotificationStatus,
)
from hablator.usecase.notification.service import NotificationService
from tests.fixtures import InlineTransaction, InMemoryNotificationRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeDispatcher:
    def __init__(self, status: DeliveryStatus = DeliveryStatus.SUCCEEDED) -> None:
        self._status = status
        self.dispatched: list[Delivery] = []

    async def dispatch(self, delivery: Delivery) -> DeliveryOutcome:
        self.dispatched.append(delivery)
        final = replace(delivery, status=self._status, updated_at=_NOW)
        return DeliveryOutcome(delivery=final, attempts=(), provider_body="ok")


def _service(dispatcher: _FakeDispatcher) -> tuple[NotificationService, InMemoryNotificationRepository]:
    repository = InMemoryNotificationRepository()
    service = NotificationService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        dispatcher=dispatcher,
    )
    return service, repository


async def test_send_persists_a_notification_and_one_delivery_per_channel_then_dispatches() -> None:
    dispatcher = _FakeDispatcher()
    service, repository = _service(dispatcher)
    request = NotificationRequest(
        content=Content(subject="Backup finished", body_text="done"),
        channels=(ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),),
    )

    outcome = await service.send(request)

    assert len(repository.notifications) == 1
    assert len(repository.deliveries) == 1
    assert dispatcher.dispatched[0].id is not None
    assert outcome.notification.id is not None
    assert outcome.status is NotificationStatus.SUCCEEDED


async def test_a_channel_content_override_replaces_the_base_content() -> None:
    dispatcher = _FakeDispatcher()
    service, repository = _service(dispatcher)
    request = NotificationRequest(
        content=Content(subject="base", body_text="base body"),
        channels=(
            ChannelRequest(
                channel=Channel.EMAIL,
                recipients=(Recipient("ops@example.com"),),
                content=Content(subject="override", body_text="override body"),
            ),
        ),
    )

    await service.send(request)

    delivery = next(iter(repository.deliveries.values()))
    assert delivery.content.subject == "override"
    assert delivery.content.body_text == "override body"


async def test_send_fans_out_one_delivery_per_channel_entry() -> None:
    dispatcher = _FakeDispatcher()
    service, repository = _service(dispatcher)
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),
            ChannelRequest(channel=Channel.PUSH, recipients=(Recipient("topic"),)),
        ),
    )

    outcome = await service.send(request)

    assert len(repository.deliveries) == 2
    assert len(dispatcher.dispatched) == 2
    assert len(outcome.deliveries) == 2
