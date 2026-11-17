"""Provider-config repository against real MySQL: read, full-replace upsert, idempotent delete."""

from __future__ import annotations

from datetime import datetime

from hablator.application.container import Container
from hablator.usecase.channel.model import Channel, ProviderConfig
from tests.fixtures import LATER, NOW


def _config(provider: str = "mailgun", *, updated_at: datetime = NOW) -> ProviderConfig:
    return ProviderConfig(
        channel=Channel.EMAIL,
        provider=provider,
        config={"from": "hablator@example.com", "bcc": "archive@example.com"},
        updated_at=updated_at,
    )


async def test_get_returns_none_for_an_unconfigured_channel(repositories: Container) -> None:
    assert await repositories.provider_config_repository.get(Channel.EMAIL) is None


async def test_upsert_creates_then_reads_back(repositories: Container) -> None:
    saved = await repositories.provider_config_repository.upsert(_config())

    assert saved == _config()
    assert await repositories.provider_config_repository.get(Channel.EMAIL) == _config()


async def test_upsert_replaces_the_whole_row(repositories: Container) -> None:
    await repositories.provider_config_repository.upsert(_config())

    replaced = await repositories.provider_config_repository.upsert(
        ProviderConfig(
            channel=Channel.EMAIL,
            provider="mailgun",
            config={"from": "new@example.com"},
            updated_at=LATER,
        )
    )

    stored = await repositories.provider_config_repository.get(Channel.EMAIL)
    assert stored == replaced
    assert stored is not None
    assert stored.config == {"from": "new@example.com"}
    assert stored.updated_at == LATER


async def test_delete_removes_the_row_and_is_idempotent(repositories: Container) -> None:
    await repositories.provider_config_repository.upsert(_config())

    await repositories.provider_config_repository.delete(Channel.EMAIL)
    await repositories.provider_config_repository.delete(Channel.EMAIL)

    assert await repositories.provider_config_repository.get(Channel.EMAIL) is None


async def test_channels_are_configured_independently(repositories: Container) -> None:
    await repositories.provider_config_repository.upsert(_config())
    push = ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={"topic": "hablator"}, updated_at=NOW)
    await repositories.provider_config_repository.upsert(push)

    assert await repositories.provider_config_repository.get(Channel.EMAIL) == _config()
    assert await repositories.provider_config_repository.get(Channel.PUSH) == push
    assert await repositories.provider_config_repository.get(Channel.SMS) is None
