"""NotificationService: create-then-fan-out, content resolution and the aggregated outcome."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from hablator.usecase.channel.model import Channel, ChannelMessage, Content, ProviderConfig, Recipient
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.exceptions import DomainError, InvalidArgumentError, ResourceNotFoundError
from hablator.usecase.commons.time import FixedClock
from hablator.usecase.delivery.dispatcher import DeliveryDispatcher
from hablator.usecase.notification.model import (
    ChannelRequest,
    Delivery,
    DeliveryOutcome,
    DeliveryStatus,
    NotificationRequest,
    NotificationStatus,
)
from hablator.usecase.notification.service import NotificationService
from tests.fixtures import (
    FakeChannelProvider,
    InlineTransaction,
    InMemoryNotificationRepository,
    InMemoryProviderConfigRepository,
    failing_result,
)

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
    registry = ChannelRegistry()
    registry.register(FakeChannelProvider())
    service = NotificationService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        dispatcher=dispatcher,
        registry=registry,
        provider_configs=InMemoryProviderConfigRepository(),
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
    repository = InMemoryNotificationRepository()
    registry = _registry(FakeChannelProvider(), FakeChannelProvider(channel=Channel.PUSH, name="ntfy"))
    push_config = ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={}, updated_at=_NOW)
    service = NotificationService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        dispatcher=dispatcher,
        registry=registry,
        provider_configs=InMemoryProviderConfigRepository({Channel.PUSH: push_config}),
    )
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),
            ChannelRequest(channel=Channel.PUSH),
        ),
    )

    outcome = await service.send(request)

    assert len(repository.deliveries) == 2
    assert len(dispatcher.dispatched) == 2
    assert len(outcome.deliveries) == 2


def _registry(*providers: object) -> ChannelRegistry:
    registry = ChannelRegistry()
    for provider in providers:
        registry.register(provider)  # type: ignore[arg-type]
    return registry


def _service_with_real_dispatcher(
    *providers: object,
    configs: dict[Channel, ProviderConfig] | None = None,
) -> tuple[NotificationService, InMemoryNotificationRepository]:
    repository = InMemoryNotificationRepository()
    registry = _registry(*providers)
    dispatcher = DeliveryDispatcher(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        provider_configs=InMemoryProviderConfigRepository(configs),
        registry=registry,
    )
    service = NotificationService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        dispatcher=dispatcher,
        registry=registry,
        provider_configs=InMemoryProviderConfigRepository(configs),
    )
    return service, repository


async def test_one_failing_channel_does_not_fail_the_request_or_the_other_channel() -> None:
    email = FakeChannelProvider(channel=Channel.EMAIL, name="mailgun", result=failing_result(500))
    push = FakeChannelProvider(channel=Channel.PUSH, name="ntfy")
    push_config = ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={}, updated_at=_NOW)
    service, repository = _service_with_real_dispatcher(email, push, configs={Channel.PUSH: push_config})
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),
            ChannelRequest(channel=Channel.PUSH),
        ),
    )

    outcome = await service.send(request)

    statuses = {delivery.delivery.channel: delivery.delivery.status for delivery in outcome.deliveries}
    assert statuses == {Channel.EMAIL: DeliveryStatus.FAILED, Channel.PUSH: DeliveryStatus.SUCCEEDED}
    assert outcome.status is NotificationStatus.FAILED
    assert len(repository.deliveries) == 2


async def test_every_delivery_records_exactly_one_attempt_numbered_one() -> None:
    service, repository = _service_with_real_dispatcher(
        FakeChannelProvider(),
        FakeChannelProvider(channel=Channel.PUSH, name="ntfy"),
        configs={Channel.PUSH: ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={}, updated_at=_NOW)},
    )
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),
            ChannelRequest(channel=Channel.PUSH),
        ),
    )

    await service.send(request)

    assert [attempt.attempt_number for attempt in repository.attempts] == [1, 1]


async def test_a_duplicate_channel_is_an_invalid_argument() -> None:
    service, repository = _service_with_real_dispatcher(FakeChannelProvider())
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("a@example.com"),)),
            ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("b@example.com"),)),
        ),
    )

    with pytest.raises(InvalidArgumentError):
        await service.send(request)

    assert repository.notifications == {}


async def test_a_channel_without_a_registered_provider_is_a_domain_error() -> None:
    service, repository = _service_with_real_dispatcher(FakeChannelProvider())
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(ChannelRequest(channel=Channel.PUSH),),
    )

    with pytest.raises(DomainError):
        await service.send(request)

    assert repository.notifications == {}


async def test_an_adapter_rule_violation_is_a_domain_error_before_any_write() -> None:
    class _RejectingProvider(FakeChannelProvider):
        def prepare(self, message: ChannelMessage) -> ChannelMessage:
            raise DomainError("email takes no delivery options")

    service, repository = _service_with_real_dispatcher(_RejectingProvider())
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(
            ChannelRequest(
                channel=Channel.EMAIL,
                recipients=(Recipient("ops@example.com"),),
                options={"priority": 1},
            ),
        ),
    )

    with pytest.raises(DomainError):
        await service.send(request)

    assert repository.notifications == {}


async def test_read_returns_the_notification_with_its_deliveries_and_attempts() -> None:
    service, _ = _service_with_real_dispatcher(FakeChannelProvider())
    request = NotificationRequest(
        content=Content(subject="s", body_text="b"),
        channels=(ChannelRequest(channel=Channel.EMAIL, recipients=(Recipient("ops@example.com"),)),),
    )
    outcome = await service.send(request)
    assert outcome.notification.id is not None

    detail = await service.read(outcome.notification.id)

    assert detail.notification.id == outcome.notification.id
    assert len(detail.deliveries) == 1
    assert detail.status is NotificationStatus.SUCCEEDED


async def test_read_an_unknown_id_is_not_found() -> None:
    service, _ = _service_with_real_dispatcher(FakeChannelProvider())

    with pytest.raises(ResourceNotFoundError):
        await service.read(999)
