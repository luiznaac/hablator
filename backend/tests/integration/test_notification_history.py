"""The history query against real MySQL: filters, derived status, ordering and pagination."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from hablator.application.container import Container
from hablator.persistence.notification.repository import NotificationRepository
from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.notification.model import (
    Delivery,
    DeliveryStatus,
    HistoryQuery,
    Notification,
    NotificationStatus,
)
from tests.fixtures import clear_hub_tables

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def _clean(container: Container) -> None:
    await clear_hub_tables(container.engine)


def _notification(source: str | None = "valoab") -> Notification:
    return Notification(
        id=None,
        source=source,
        content=Content(subject="Backup finished", body_text="done", body_html="<p>done</p>"),
        created_at=_NOW,
    )


def _delivery(channel: Channel = Channel.EMAIL) -> Delivery:
    return Delivery(
        id=None,
        notification_id=None,
        channel=channel,
        status=DeliveryStatus.PENDING,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject=f"{channel.value} subject", body_text="done"),
        options={},
        next_attempt_at=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def _create(
    container: Container,
    repository: NotificationRepository,
    *,
    now: datetime = _NOW,
    source: str | None = "valoab",
    channels: tuple[Channel, ...] = (Channel.EMAIL,),
) -> tuple[int, list[Delivery]]:
    notification = replace(_notification(source), created_at=now)
    deliveries = [replace(_delivery(channel), created_at=now, updated_at=now) for channel in channels]
    persisted, persisted_deliveries = await container.transaction_template.execute(
        lambda: repository.create(notification, deliveries)
    )
    assert persisted.id is not None
    return persisted.id, persisted_deliveries


async def _set_status(
    container: Container,
    repository: NotificationRepository,
    delivery: Delivery,
    status: DeliveryStatus,
) -> None:
    moved = replace(delivery, status=status)
    await container.transaction_template.execute(lambda: repository.update_delivery(moved))


async def _history(container: Container, repository: NotificationRepository, query: HistoryQuery):
    return await container.transaction_template.execute(lambda: repository.history(query))


async def test_history_is_newest_first_with_offset_pagination_and_total(container: Container) -> None:
    repository = NotificationRepository()
    first, _ = await _create(container, repository, now=_NOW)
    second, _ = await _create(container, repository, now=_NOW + timedelta(minutes=1))
    third, _ = await _create(container, repository, now=_NOW + timedelta(minutes=2))

    page = await _history(container, repository, HistoryQuery(limit=2, offset=1))

    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 1
    assert [item.id for item in page.items] == [second, first]
    assert third not in [item.id for item in page.items]


async def test_history_orders_same_instant_rows_by_id_descending(container: Container) -> None:
    repository = NotificationRepository()
    first, _ = await _create(container, repository)
    second, _ = await _create(container, repository)

    page = await _history(container, repository, HistoryQuery())

    assert [item.id for item in page.items] == [second, first]


async def test_history_filters_by_source(container: Container) -> None:
    repository = NotificationRepository()
    valoab, _ = await _create(container, repository, source="valoab")
    await _create(container, repository, source="chameidor")

    page = await _history(container, repository, HistoryQuery(source="valoab"))

    assert page.total == 1
    assert [item.id for item in page.items] == [valoab]


async def test_history_filters_by_channel_with_a_delivery_exists(container: Container) -> None:
    repository = NotificationRepository()
    both, _ = await _create(container, repository, channels=(Channel.EMAIL, Channel.PUSH))
    await _create(container, repository, channels=(Channel.EMAIL,))

    page = await _history(container, repository, HistoryQuery(channel=Channel.PUSH))

    assert page.total == 1
    assert [item.id for item in page.items] == [both]
    assert page.items[0].channels == (Channel.EMAIL, Channel.PUSH)


async def test_history_filters_by_derived_status(container: Container) -> None:
    repository = NotificationRepository()
    succeeded, succeeded_deliveries = await _create(container, repository, channels=(Channel.EMAIL, Channel.PUSH))
    for delivery in succeeded_deliveries:
        await _set_status(container, repository, delivery, DeliveryStatus.SUCCEEDED)

    failed, failed_deliveries = await _create(container, repository, channels=(Channel.EMAIL, Channel.PUSH))
    await _set_status(container, repository, failed_deliveries[0], DeliveryStatus.FAILED)
    await _set_status(container, repository, failed_deliveries[1], DeliveryStatus.SUCCEEDED)

    pending, pending_deliveries = await _create(container, repository, channels=(Channel.EMAIL, Channel.PUSH))
    await _set_status(container, repository, pending_deliveries[0], DeliveryStatus.SUCCEEDED)

    succeeded_page = await _history(container, repository, HistoryQuery(status=NotificationStatus.SUCCEEDED))
    failed_page = await _history(container, repository, HistoryQuery(status=NotificationStatus.FAILED))
    pending_page = await _history(container, repository, HistoryQuery(status=NotificationStatus.PENDING))

    assert [item.id for item in succeeded_page.items] == [succeeded]
    assert [item.id for item in failed_page.items] == [failed]
    assert [item.id for item in pending_page.items] == [pending]
    assert succeeded_page.total == 1
    assert failed_page.total == 1
    assert pending_page.total == 1


async def test_history_filters_by_derived_status_before_paginating(container: Container) -> None:
    repository = NotificationRepository()
    for _ in range(3):
        await _create(container, repository)
    succeeded, deliveries = await _create(container, repository)
    await _set_status(container, repository, deliveries[0], DeliveryStatus.SUCCEEDED)

    page = await _history(container, repository, HistoryQuery(status=NotificationStatus.SUCCEEDED, limit=1, offset=0))

    assert page.total == 1
    assert [item.id for item in page.items] == [succeeded]


async def test_history_date_filters_are_inclusive_after_and_exclusive_before(container: Container) -> None:
    repository = NotificationRepository()
    earlier, _ = await _create(container, repository, now=_NOW)
    pivot, _ = await _create(container, repository, now=_NOW + timedelta(minutes=1))
    later, _ = await _create(container, repository, now=_NOW + timedelta(minutes=2))

    after = await _history(container, repository, HistoryQuery(created_after=_NOW + timedelta(minutes=1)))
    before = await _history(container, repository, HistoryQuery(created_before=_NOW + timedelta(minutes=1)))

    assert [item.id for item in after.items] == [later, pivot]
    assert [item.id for item in before.items] == [earlier]


async def test_history_rows_carry_the_base_subject_and_derived_status(container: Container) -> None:
    repository = NotificationRepository()
    notification_id, deliveries = await _create(container, repository, channels=(Channel.PUSH,))
    await _set_status(container, repository, deliveries[0], DeliveryStatus.SUCCEEDED)

    page = await _history(container, repository, HistoryQuery())

    assert page.items[0].id == notification_id
    assert page.items[0].subject == "Backup finished"
    assert page.items[0].status is NotificationStatus.SUCCEEDED
    assert page.items[0].channels == (Channel.PUSH,)
    assert page.items[0].created_at == _NOW
