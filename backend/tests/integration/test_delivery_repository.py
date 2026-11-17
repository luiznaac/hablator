"""Delivery repository against real MySQL: append-only attempts and status transitions."""

from __future__ import annotations

import pytest

from hablator.application.container import Container
from hablator.usecase.channel.model import ErrorKind
from hablator.usecase.commons.exceptions import InvalidTransitionError, ResourceNotFoundError
from hablator.usecase.notification.model import AttemptOutcome, DeliveryStatus
from tests.fixtures import LATER, NOW, attempt, create_notification


async def _delivery_id(container: Container) -> int:
    created = await create_notification(container)
    return created.deliveries[0].id


async def test_append_attempt_is_readable_with_the_delivery(repositories: Container) -> None:
    delivery_id = await _delivery_id(repositories)

    await repositories.delivery_repository.append_attempt(delivery_id, attempt(1))
    await repositories.delivery_repository.append_attempt(delivery_id, attempt(2, outcome=AttemptOutcome.FAILED))

    delivery = await repositories.delivery_repository.get(delivery_id)

    assert delivery is not None
    assert [recorded.attempt_number for recorded in delivery.attempts] == [1, 2]
    assert delivery.attempts[0].provider == "mailgun"
    assert delivery.attempts[0].started_at == NOW
    assert delivery.attempts[1].error_kind is ErrorKind.HTTP_STATUS
    assert delivery.attempts[1].retriable is True


async def test_get_returns_none_for_an_unknown_delivery(repositories: Container) -> None:
    assert await repositories.delivery_repository.get(999_999) is None


async def test_transition_updates_status_and_timestamps(repositories: Container) -> None:
    delivery_id = await _delivery_id(repositories)

    moved = await repositories.delivery_repository.transition(delivery_id, DeliveryStatus.IN_PROGRESS, now=LATER)

    assert moved.status is DeliveryStatus.IN_PROGRESS
    assert moved.updated_at == LATER
    assert moved.created_at == NOW
    assert moved.next_attempt_at is None

    stored = await repositories.delivery_repository.get(delivery_id)
    assert stored is not None
    assert stored.status is DeliveryStatus.IN_PROGRESS
    assert stored.updated_at == LATER


async def test_transition_can_schedule_the_next_attempt(repositories: Container) -> None:
    delivery_id = await _delivery_id(repositories)
    await repositories.delivery_repository.transition(delivery_id, DeliveryStatus.IN_PROGRESS, now=NOW)

    moved = await repositories.delivery_repository.transition(
        delivery_id,
        DeliveryStatus.PENDING,
        next_attempt_at=LATER,
        now=LATER,
    )

    assert moved.status is DeliveryStatus.PENDING
    assert moved.next_attempt_at == LATER


async def test_transition_enforces_the_lifecycle(repositories: Container) -> None:
    delivery_id = await _delivery_id(repositories)
    await repositories.delivery_repository.transition(delivery_id, DeliveryStatus.IN_PROGRESS, now=NOW)
    await repositories.delivery_repository.transition(delivery_id, DeliveryStatus.SUCCEEDED, now=NOW)

    with pytest.raises(InvalidTransitionError):
        await repositories.delivery_repository.transition(delivery_id, DeliveryStatus.IN_PROGRESS, now=LATER)


async def test_transition_rejects_an_unknown_delivery(repositories: Container) -> None:
    with pytest.raises(ResourceNotFoundError):
        await repositories.delivery_repository.transition(999_999, DeliveryStatus.IN_PROGRESS, now=NOW)
