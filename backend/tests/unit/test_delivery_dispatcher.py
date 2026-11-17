"""Dispatch: status transitions, attempt recording, retriability and the transaction boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from hablator.application.telemetry import Telemetry
from hablator.usecase.channel.model import Channel, Content, ErrorKind, ProviderConfig, Recipient
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.exceptions import DomainError
from hablator.usecase.commons.time import FixedClock
from hablator.usecase.delivery.dispatcher import DeliveryDispatcher
from hablator.usecase.notification.model import AttemptOutcome, Delivery, DeliveryStatus
from tests.fixtures import (
    FakeChannelProvider,
    InlineTransaction,
    InMemoryNotificationRepository,
    InMemoryProviderConfigRepository,
    failing_result,
    log_records,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _delivery() -> Delivery:
    return Delivery(
        id=1,
        notification_id=1,
        channel=Channel.EMAIL,
        status=DeliveryStatus.PENDING,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="b", body_html="<p>b</p>"),
        options={},
        next_attempt_at=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _dispatcher(
    provider: FakeChannelProvider,
    *,
    transaction: InlineTransaction | None = None,
    configs: dict[Channel, ProviderConfig] | None = None,
) -> tuple[DeliveryDispatcher, InMemoryNotificationRepository]:
    repository = InMemoryNotificationRepository()
    registry = ChannelRegistry()
    registry.register(provider)
    dispatcher = DeliveryDispatcher(
        clock=FixedClock(_NOW),
        transaction=transaction or InlineTransaction(),
        repository=repository,
        provider_configs=InMemoryProviderConfigRepository(configs),
        registry=registry,
    )
    return dispatcher, repository


async def test_a_successful_attempt_marks_the_delivery_succeeded() -> None:
    dispatcher, repository = _dispatcher(FakeChannelProvider())

    outcome = await dispatcher.dispatch(_delivery())

    assert outcome.delivery.status is DeliveryStatus.SUCCEEDED
    assert outcome.succeeded is True
    assert outcome.provider_body == "queued"
    assert outcome.attempts[0].outcome is AttemptOutcome.SUCCEEDED
    assert outcome.attempts[0].retriable is False
    assert len(repository.attempts) == 1


async def test_a_second_attempt_on_the_same_delivery_is_numbered_two() -> None:
    dispatcher, repository = _dispatcher(FakeChannelProvider(result=failing_result(500)))

    first = await dispatcher.dispatch(_delivery())
    second = await dispatcher.dispatch(replace(first.delivery, status=DeliveryStatus.PENDING))

    assert first.attempts[0].attempt_number == 1
    assert second.attempts[0].attempt_number == 2
    assert [attempt.attempt_number for attempt in repository.attempts] == [1, 2]


async def test_a_retriable_failure_marks_the_delivery_failed_and_the_attempt_retriable() -> None:
    provider = FakeChannelProvider(result=failing_result(503))
    dispatcher, _ = _dispatcher(provider)

    outcome = await dispatcher.dispatch(_delivery())

    assert outcome.delivery.status is DeliveryStatus.FAILED
    assert outcome.attempts[0].outcome is AttemptOutcome.FAILED
    assert outcome.attempts[0].retriable is True
    assert outcome.provider_body == "provider failed"


async def test_a_raising_provider_becomes_a_non_retriable_unexpected_attempt() -> None:
    provider = FakeChannelProvider(exception=RuntimeError("kaboom"))
    dispatcher, _ = _dispatcher(provider)

    outcome = await dispatcher.dispatch(_delivery())

    attempt = outcome.attempts[0]
    assert outcome.delivery.status is DeliveryStatus.FAILED
    assert attempt.outcome is AttemptOutcome.FAILED
    assert attempt.error_kind is ErrorKind.UNEXPECTED
    assert attempt.retriable is False
    assert outcome.provider_body == ""


async def test_the_provider_is_called_outside_any_transaction() -> None:
    transaction = InlineTransaction()
    provider = FakeChannelProvider(hook=lambda: _assert_idle(transaction))
    dispatcher, _ = _dispatcher(provider, transaction=transaction)

    await dispatcher.dispatch(_delivery())

    assert provider.sent  # the hook ran


def _assert_idle(transaction: InlineTransaction) -> None:
    assert transaction.active is False


async def test_an_unregistered_provider_is_a_domain_error() -> None:
    registry = ChannelRegistry()
    dispatcher = DeliveryDispatcher(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=InMemoryNotificationRepository(),
        provider_configs=InMemoryProviderConfigRepository(),
        registry=registry,
    )

    with pytest.raises(DomainError):
        await dispatcher.dispatch(_delivery())


async def test_provider_config_is_passed_to_the_provider() -> None:
    provider = FakeChannelProvider()
    config = ProviderConfig(
        channel=Channel.EMAIL,
        provider="mailgun",
        config={"from": "x@example.com"},
        updated_at=_NOW,
    )
    dispatcher, _ = _dispatcher(provider, configs={Channel.EMAIL: config})

    await dispatcher.dispatch(_delivery())

    assert provider.sent[0].config == {"from": "x@example.com"}


async def test_email_falls_back_to_the_default_provider_without_a_config_row() -> None:
    provider = FakeChannelProvider()
    dispatcher, _ = _dispatcher(provider)

    await dispatcher.dispatch(_delivery())

    assert provider.sent[0].config == {}


async def test_a_raising_provider_logs_a_stack_trace_at_error(telemetry: Telemetry) -> None:
    provider = FakeChannelProvider(exception=RuntimeError("kaboom"))
    dispatcher, _ = _dispatcher(provider)

    await dispatcher.dispatch(_delivery())

    unexpected = [
        item.log_record for item in log_records(telemetry) if item.log_record.body == "channel.attempt.unexpected"
    ]
    assert len(unexpected) == 1
    assert unexpected[0].severity_text == "ERROR"
    assert "RuntimeError" in str(unexpected[0].attributes.get("exception.stacktrace", ""))
