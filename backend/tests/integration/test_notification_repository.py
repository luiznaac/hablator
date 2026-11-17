"""The notification repository and provider-config reader against real MySQL."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from hablator.application.container import Container
from hablator.persistence.channel.entity import ProviderConfigEntity
from hablator.persistence.channel.repository import ProviderConfigRepository
from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.repository import NotificationRepository
from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryStatus,
    Notification,
    NotificationStatus,
)
from tests.fixtures import clear_hub_tables

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def _clean(container: Container) -> None:
    await clear_hub_tables(container.engine)


def _notification() -> Notification:
    return Notification(
        id=None,
        source="valoab",
        content=Content(subject="Backup finished", body_text="done", body_html="<p>done</p>"),
        created_at=_NOW,
    )


def _delivery() -> Delivery:
    return Delivery(
        id=None,
        notification_id=None,
        channel=Channel.EMAIL,
        status=DeliveryStatus.PENDING,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="Backup finished", body_text="done", body_html="<p>done</p>"),
        options={"tracking": "no"},
        next_attempt_at=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def test_create_assigns_ids_and_persists_the_aggregate(container: Container) -> None:
    repository = NotificationRepository()

    notification, deliveries = await container.transaction_template.execute(
        lambda: repository.create(_notification(), [_delivery()])
    )

    assert notification.id is not None
    assert deliveries[0].id is not None
    assert deliveries[0].notification_id == notification.id


async def test_update_delivery_and_add_attempt_round_trip(container: Container) -> None:
    repository = NotificationRepository()
    _, deliveries = await container.transaction_template.execute(
        lambda: repository.create(_notification(), [_delivery()])
    )
    delivery = deliveries[0]
    assert delivery.id is not None

    succeeded = replace(delivery, status=DeliveryStatus.SUCCEEDED, updated_at=_NOW)
    await container.transaction_template.execute(lambda: repository.update_delivery(succeeded))

    attempt = Attempt(
        id=None,
        delivery_id=delivery.id,
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
    persisted_attempt = await container.transaction_template.execute(lambda: repository.add_attempt(attempt))

    assert persisted_attempt.id is not None
    async with container.engine.connect() as connection:
        status = (await connection.execute(text("SELECT status FROM delivery"))).scalar()
        outcome = (await connection.execute(text("SELECT outcome FROM attempt"))).scalar()
    assert status == "succeeded"
    assert outcome == "succeeded"


async def test_provider_config_repository_reads_a_row(container: Container) -> None:
    async def _insert() -> None:
        current_session().add(
            ProviderConfigEntity(
                channel="email",
                provider="mailgun",
                config={"from": "override@example.com"},
                updated_at=_NOW,
            )
        )

    await container.transaction_template.execute(_insert)

    config = await container.transaction_template.execute(lambda: ProviderConfigRepository().get(Channel.EMAIL))

    assert config is not None
    assert config.provider == "mailgun"
    assert config.config == {"from": "override@example.com"}


async def test_provider_config_repository_returns_none_for_an_unconfigured_channel(
    container: Container,
) -> None:
    config = await container.transaction_template.execute(lambda: ProviderConfigRepository().get(Channel.PUSH))

    assert config is None


async def test_get_reads_the_notification_with_its_deliveries_and_attempts(container: Container) -> None:
    repository = NotificationRepository()
    notification, deliveries = await container.transaction_template.execute(
        lambda: repository.create(_notification(), [_delivery()])
    )
    assert notification.id is not None
    attempt = Attempt(
        id=None,
        delivery_id=deliveries[0].id,
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
    persisted_attempt = await container.transaction_template.execute(lambda: repository.add_attempt(attempt))

    detail = await container.transaction_template.execute(lambda: repository.get(notification.id))

    assert detail is not None
    assert detail.notification == notification
    assert detail.deliveries[0].delivery == deliveries[0]
    assert detail.deliveries[0].attempts == (persisted_attempt,)
    assert detail.status is NotificationStatus.PENDING


async def test_get_returns_none_for_an_unknown_notification(container: Container) -> None:
    repository = NotificationRepository()

    assert await container.transaction_template.execute(lambda: repository.get(999_999)) is None
