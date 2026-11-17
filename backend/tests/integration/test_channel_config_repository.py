"""Provider-config and retry-policy repositories against real MySQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hablator.application.container import Container
from hablator.persistence.channel.repository import ProviderConfigRepository, RetryPolicyRepository
from hablator.usecase.channel.model import Channel, ProviderConfig, RetryPolicy
from tests.fixtures import clear_hub_tables

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_LATER = _NOW + timedelta(minutes=5)


@pytest.fixture(autouse=True)
async def _clean(container: Container) -> None:
    await clear_hub_tables(container.engine)


def _config(provider: str = "mailgun", *, updated_at: datetime = _NOW) -> ProviderConfig:
    return ProviderConfig(
        channel=Channel.EMAIL,
        provider=provider,
        config={"from": "hablator@example.com", "bcc": "archive@example.com"},
        updated_at=updated_at,
    )


def _policy(max_attempts: int = 3, *, updated_at: datetime = _NOW) -> RetryPolicy:
    return RetryPolicy(
        channel=Channel.EMAIL,
        max_attempts=max_attempts,
        backoff_seconds=(30, 120, 600),
        updated_at=updated_at,
    )


async def _get_config(container: Container, channel: Channel) -> ProviderConfig | None:
    return await container.transaction_template.execute(lambda: ProviderConfigRepository().get(channel))


async def _get_policy(container: Container, channel: Channel) -> RetryPolicy | None:
    return await container.transaction_template.execute(lambda: RetryPolicyRepository().get(channel))


async def test_provider_config_get_returns_none_for_an_unconfigured_channel(container: Container) -> None:
    assert await _get_config(container, Channel.EMAIL) is None


async def test_provider_config_upsert_creates_then_reads_back(container: Container) -> None:
    saved = await container.transaction_template.execute(lambda: ProviderConfigRepository().upsert(_config()))

    assert saved == _config()
    assert await _get_config(container, Channel.EMAIL) == _config()


async def test_provider_config_upsert_replaces_the_whole_row(container: Container) -> None:
    await container.transaction_template.execute(lambda: ProviderConfigRepository().upsert(_config()))

    replaced = await container.transaction_template.execute(
        lambda: ProviderConfigRepository().upsert(
            ProviderConfig(
                channel=Channel.EMAIL,
                provider="mailgun",
                config={"from": "new@example.com"},
                updated_at=_LATER,
            )
        )
    )

    stored = await _get_config(container, Channel.EMAIL)
    assert stored == replaced
    assert stored is not None
    assert stored.config == {"from": "new@example.com"}
    assert stored.updated_at == _LATER


async def test_provider_config_delete_removes_the_row_and_is_idempotent(container: Container) -> None:
    await container.transaction_template.execute(lambda: ProviderConfigRepository().upsert(_config()))

    await container.transaction_template.execute(lambda: ProviderConfigRepository().delete(Channel.EMAIL))
    await container.transaction_template.execute(lambda: ProviderConfigRepository().delete(Channel.EMAIL))

    assert await _get_config(container, Channel.EMAIL) is None


async def test_provider_config_channels_are_configured_independently(container: Container) -> None:
    await container.transaction_template.execute(lambda: ProviderConfigRepository().upsert(_config()))
    push = ProviderConfig(
        channel=Channel.PUSH,
        provider="ntfy",
        config={"topic": "hablator"},
        updated_at=_NOW,
    )
    await container.transaction_template.execute(lambda: ProviderConfigRepository().upsert(push))

    assert await _get_config(container, Channel.EMAIL) == _config()
    assert await _get_config(container, Channel.PUSH) == push
    assert await _get_config(container, Channel.SMS) is None


async def test_retry_policy_get_returns_none_for_an_unconfigured_channel(container: Container) -> None:
    assert await _get_policy(container, Channel.EMAIL) is None


async def test_retry_policy_upsert_creates_then_reads_back(container: Container) -> None:
    saved = await container.transaction_template.execute(lambda: RetryPolicyRepository().upsert(_policy()))

    assert saved == _policy()
    assert await _get_policy(container, Channel.EMAIL) == _policy()


async def test_retry_policy_upsert_replaces_the_policy(container: Container) -> None:
    await container.transaction_template.execute(lambda: RetryPolicyRepository().upsert(_policy()))

    await container.transaction_template.execute(lambda: RetryPolicyRepository().upsert(_policy(5, updated_at=_LATER)))

    stored = await _get_policy(container, Channel.EMAIL)
    assert stored is not None
    assert stored.max_attempts == 5
    assert stored.backoff_seconds == (30, 120, 600)
    assert stored.updated_at == _LATER
