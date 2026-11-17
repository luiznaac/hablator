"""Notification repository against real MySQL: create with pending deliveries, read, history."""

from __future__ import annotations

from datetime import datetime, timedelta

from hablator.application.container import Container
from hablator.usecase.channel.model import Channel, Content
from hablator.usecase.notification.model import (
    DeliveryStatus,
    HistoryQuery,
    NotificationStatus,
)
from tests.fixtures import NOW, attempt, create_notification


async def _create_at(
    container: Container,
    now: datetime,
    *,
    source: str | None = "valoab",
    channels: tuple[Channel, ...] = (Channel.EMAIL,),
) -> int:
    created = await create_notification(container, source=source, channels=channels, now=now)
    return created.id


async def _set_status(
    container: Container, notification_id: int, statuses: dict[Channel, DeliveryStatus], now: datetime
) -> None:
    notification = await container.notification_repository.get(notification_id)
    assert notification is not None
    for delivery in notification.deliveries:
        target = statuses[delivery.channel]
        if target is DeliveryStatus.PENDING:
            continue
        await container.delivery_repository.transition(delivery.id, DeliveryStatus.IN_PROGRESS, now=now)
        await container.delivery_repository.transition(delivery.id, target, now=now)


async def test_create_persists_the_notification_with_pending_deliveries(repositories: Container) -> None:
    created = await create_notification(repositories, channels=(Channel.EMAIL, Channel.PUSH))

    assert created.id > 0
    assert created.source == "valoab"
    assert created.content == Content(subject="Backup finished", body="plain text", body_html="<p>rich</p>")
    assert created.created_at == NOW
    assert created.status is NotificationStatus.PENDING
    assert [delivery.channel for delivery in created.deliveries] == [Channel.EMAIL, Channel.PUSH]
    assert all(delivery.status is DeliveryStatus.PENDING for delivery in created.deliveries)
    assert all(delivery.notification_id == created.id for delivery in created.deliveries)
    assert all(delivery.created_at == NOW and delivery.updated_at == NOW for delivery in created.deliveries)

    stored = await repositories.notification_repository.get(created.id)

    assert stored == created


async def test_get_returns_deliveries_with_their_attempts(repositories: Container) -> None:
    created = await create_notification(repositories)
    delivery = created.deliveries[0]
    recorded = attempt()
    await repositories.delivery_repository.append_attempt(delivery.id, recorded)

    stored = await repositories.notification_repository.get(created.id)

    assert stored is not None
    assert stored.deliveries[0].attempts == (recorded,)


async def test_get_returns_none_for_an_unknown_notification(repositories: Container) -> None:
    assert await repositories.notification_repository.get(999_999) is None


async def test_history_is_newest_first_with_offset_pagination_and_total(repositories: Container) -> None:
    first = await _create_at(repositories, NOW)
    second = await _create_at(repositories, NOW + timedelta(minutes=1))
    third = await _create_at(repositories, NOW + timedelta(minutes=2))

    page = await repositories.notification_repository.history(HistoryQuery(limit=2, offset=1))

    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 1
    assert [item.id for item in page.items] == [second, first]
    assert third not in [item.id for item in page.items]


async def test_history_orders_same_instant_rows_by_id_descending(repositories: Container) -> None:
    first = await _create_at(repositories, NOW)
    second = await _create_at(repositories, NOW)

    page = await repositories.notification_repository.history(HistoryQuery())

    assert [item.id for item in page.items] == [second, first]


async def test_history_filters_by_source(repositories: Container) -> None:
    valoab = await _create_at(repositories, NOW, source="valoab")
    await _create_at(repositories, NOW, source="chameidor")

    page = await repositories.notification_repository.history(HistoryQuery(source="valoab"))

    assert page.total == 1
    assert [item.id for item in page.items] == [valoab]


async def test_history_filters_by_channel_with_a_delivery_exists(repositories: Container) -> None:
    both = await _create_at(repositories, NOW, channels=(Channel.EMAIL, Channel.PUSH))
    await _create_at(repositories, NOW, channels=(Channel.EMAIL,))

    page = await repositories.notification_repository.history(HistoryQuery(channel=Channel.PUSH))

    assert page.total == 1
    assert [item.id for item in page.items] == [both]
    assert page.items[0].channels == (Channel.EMAIL, Channel.PUSH)


async def test_history_filters_by_derived_status(repositories: Container) -> None:
    succeeded = await _create_at(repositories, NOW, channels=(Channel.EMAIL, Channel.PUSH))
    await _set_status(
        repositories,
        succeeded,
        {Channel.EMAIL: DeliveryStatus.SUCCEEDED, Channel.PUSH: DeliveryStatus.SUCCEEDED},
        NOW,
    )
    failed = await _create_at(repositories, NOW, channels=(Channel.EMAIL, Channel.PUSH))
    await _set_status(
        repositories,
        failed,
        {Channel.EMAIL: DeliveryStatus.FAILED, Channel.PUSH: DeliveryStatus.SUCCEEDED},
        NOW,
    )
    pending = await _create_at(repositories, NOW, channels=(Channel.EMAIL, Channel.PUSH))
    await _set_status(
        repositories,
        pending,
        {Channel.EMAIL: DeliveryStatus.SUCCEEDED, Channel.PUSH: DeliveryStatus.PENDING},
        NOW,
    )

    succeeded_page = await repositories.notification_repository.history(
        HistoryQuery(status=NotificationStatus.SUCCEEDED)
    )
    failed_page = await repositories.notification_repository.history(HistoryQuery(status=NotificationStatus.FAILED))
    pending_page = await repositories.notification_repository.history(HistoryQuery(status=NotificationStatus.PENDING))

    assert [item.id for item in succeeded_page.items] == [succeeded]
    assert [item.id for item in failed_page.items] == [failed]
    assert [item.id for item in pending_page.items] == [pending]
    assert succeeded_page.total == 1
    assert failed_page.total == 1
    assert pending_page.total == 1


async def test_history_filters_by_derived_status_before_paginating(repositories: Container) -> None:
    for _ in range(3):
        await _create_at(repositories, NOW, channels=(Channel.EMAIL,))
    succeeded = await _create_at(repositories, NOW, channels=(Channel.EMAIL,))
    await _set_status(repositories, succeeded, {Channel.EMAIL: DeliveryStatus.SUCCEEDED}, NOW)

    page = await repositories.notification_repository.history(
        HistoryQuery(status=NotificationStatus.SUCCEEDED, limit=1, offset=0)
    )

    assert page.total == 1
    assert [item.id for item in page.items] == [succeeded]


async def test_history_date_filters_are_inclusive_after_and_exclusive_before(repositories: Container) -> None:
    earlier = await _create_at(repositories, NOW)
    pivot = await _create_at(repositories, NOW + timedelta(minutes=1))
    later = await _create_at(repositories, NOW + timedelta(minutes=2))

    after = await repositories.notification_repository.history(HistoryQuery(created_after=NOW + timedelta(minutes=1)))
    before = await repositories.notification_repository.history(HistoryQuery(created_before=NOW + timedelta(minutes=1)))

    assert [item.id for item in after.items] == [later, pivot]
    assert [item.id for item in before.items] == [earlier]


async def test_history_rows_carry_the_base_subject_and_derived_status(repositories: Container) -> None:
    created = await _create_at(repositories, NOW, channels=(Channel.PUSH,))
    await _set_status(repositories, created, {Channel.PUSH: DeliveryStatus.SUCCEEDED}, NOW)

    page = await repositories.notification_repository.history(HistoryQuery())

    assert page.items[0].subject == "Backup finished"
    assert page.items[0].status is NotificationStatus.SUCCEEDED
    assert page.items[0].channels == (Channel.PUSH,)
    assert page.items[0].created_at == NOW
