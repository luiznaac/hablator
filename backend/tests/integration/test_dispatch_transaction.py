"""The provider call runs with no database session bound.

This is the real guarantee the unit test only approximates: the dispatcher commits the
`in_progress` transition, then calls the provider while `current_session()` is unbound.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hablator.application.container import Container
from hablator.persistence.channel.repository import ProviderConfigRepository
from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.repository import NotificationRepository
from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    Content,
    ProviderResult,
    Recipient,
)
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.delivery.dispatcher import DeliveryDispatcher
from hablator.usecase.notification.model import Delivery, DeliveryStatus, Notification
from tests.fixtures import clear_hub_tables

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _SessionCheckingProvider:
    channel = Channel.EMAIL
    name = "mailgun"

    def __init__(self) -> None:
        self.called = False

    async def send(self, message: ChannelMessage) -> ProviderResult:
        with pytest.raises(RuntimeError):
            current_session()
        self.called = True
        return ProviderResult(
            provider="mailgun",
            provider_status=200,
            error_kind=None,
            error_message=None,
            provider_body="queued",
        )


@pytest.fixture(autouse=True)
async def _clean(container: Container) -> None:
    await clear_hub_tables(container.engine)


async def test_the_provider_runs_without_a_bound_session(container: Container) -> None:
    repository = NotificationRepository()
    _, deliveries = await container.transaction_template.execute(
        lambda: repository.create(
            Notification(
                id=None,
                source=None,
                content=Content(subject="s", body_text="b"),
                created_at=_NOW,
            ),
            [
                Delivery(
                    id=None,
                    notification_id=None,
                    channel=Channel.EMAIL,
                    status=DeliveryStatus.PENDING,
                    recipients=(Recipient("ops@example.com"),),
                    content=Content(subject="s", body_text="b"),
                    options={},
                    next_attempt_at=None,
                    created_at=_NOW,
                    updated_at=_NOW,
                )
            ],
        )
    )
    provider = _SessionCheckingProvider()
    registry = ChannelRegistry()
    registry.register(provider)
    dispatcher = DeliveryDispatcher(
        clock=container.clock,
        transaction=container.transaction_template,
        repository=repository,
        provider_configs=ProviderConfigRepository(),
        registry=registry,
    )

    outcome = await dispatcher.dispatch(deliveries[0])

    assert provider.called is True
    assert outcome.succeeded is True
