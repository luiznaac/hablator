"""ChannelConfigService: the vocabulary listing, the full-replace upsert and the idempotent delete.

The service owns the channel-level rules (a registered provider, a secret-shaped key) and delegates
the per-adapter config shape to the provider itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from hablator.application.telemetry import Telemetry
from hablator.usecase.channel.model import Channel, ProviderConfig
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.channel.service import ChannelConfigService
from hablator.usecase.commons.exceptions import DomainError
from hablator.usecase.commons.time import FixedClock
from tests.fixtures import FakeChannelProvider, InlineTransaction, InMemoryProviderConfigRepository, log_records

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _RejectingProvider(FakeChannelProvider):
    def validate_config(self, config: Mapping[str, object]) -> Mapping[str, object]:
        raise DomainError("adapter says no")


def _service(
    *providers: object,
    configs: Mapping[Channel, ProviderConfig] | None = None,
) -> tuple[ChannelConfigService, InMemoryProviderConfigRepository]:
    registry = ChannelRegistry()
    for provider in providers:
        registry.register(provider)  # type: ignore[arg-type]
    repository = InMemoryProviderConfigRepository(configs)
    service = ChannelConfigService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=repository,
        registry=registry,
    )
    return service, repository


def _email() -> FakeChannelProvider:
    return FakeChannelProvider(channel=Channel.EMAIL, name="mailgun")


def _push() -> FakeChannelProvider:
    return FakeChannelProvider(channel=Channel.PUSH, name="ntfy")


async def test_list_returns_every_channel_of_the_vocabulary_in_order() -> None:
    service, _ = _service(_email(), _push())

    views = await service.list()

    assert [view.channel for view in views] == [Channel.EMAIL, Channel.PUSH, Channel.SMS, Channel.VOICE]
    assert all(view.configured is False for view in views)
    assert all(view.provider is None and view.config is None and view.updated_at is None for view in views)


async def test_list_reports_a_configured_channel_and_leaves_the_others_unconfigured() -> None:
    config = ProviderConfig(
        channel=Channel.PUSH,
        provider="ntfy",
        config={"topic": "hablator"},
        updated_at=_NOW,
    )
    service, _ = _service(_email(), _push(), configs={Channel.PUSH: config})

    views = {view.channel: view for view in await service.list()}

    assert views[Channel.PUSH].configured is True
    assert views[Channel.PUSH].provider == "ntfy"
    assert views[Channel.PUSH].config == {"topic": "hablator"}
    assert views[Channel.PUSH].updated_at == _NOW
    assert views[Channel.EMAIL].configured is False


async def test_upsert_creates_a_new_row_with_the_clock_time() -> None:
    service, repository = _service(_push())

    result = await service.upsert(Channel.PUSH, "ntfy", {"topic": "hablator"})

    assert result.created is True
    assert result.view.configured is True
    assert result.view.provider == "ntfy"
    assert result.view.config == {"topic": "hablator"}
    assert result.view.updated_at == _NOW
    assert await repository.get(Channel.PUSH) == ProviderConfig(
        channel=Channel.PUSH,
        provider="ntfy",
        config={"topic": "hablator"},
        updated_at=_NOW,
    )


async def test_upsert_replaces_an_existing_row_and_reports_not_created() -> None:
    existing = ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={"topic": "old"}, updated_at=_NOW)
    service, repository = _service(_push(), configs={Channel.PUSH: existing})

    result = await service.upsert(Channel.PUSH, "ntfy", {"topic": "new"})

    assert result.created is False
    assert result.view.config == {"topic": "new"}
    stored = await repository.get(Channel.PUSH)
    assert stored is not None
    assert stored.config == {"topic": "new"}


async def test_upsert_rejects_a_provider_not_registered_for_the_channel() -> None:
    service, repository = _service(_email())

    with pytest.raises(DomainError):
        await service.upsert(Channel.EMAIL, "ntfy", {"topic": "hablator"})

    assert await repository.get(Channel.EMAIL) is None


@pytest.mark.parametrize("channel", [Channel.SMS, Channel.VOICE])
async def test_upsert_rejects_a_channel_without_a_registered_provider(channel: Channel) -> None:
    service, repository = _service(_email(), _push())

    with pytest.raises(DomainError):
        await service.upsert(channel, "ntfy", {})

    assert await repository.get(channel) is None


@pytest.mark.parametrize("key", ["api_key", "token", "secret", "password", "auth"])
async def test_upsert_rejects_a_secret_shaped_key_and_names_the_env_var(key: str) -> None:
    service, repository = _service(_push())

    with pytest.raises(DomainError) as raised:
        await service.upsert(Channel.PUSH, "ntfy", {"topic": "hablator", key: "leak"})

    assert "NTFY__TOKEN" in str(raised.value)
    assert "leak" not in str(raised.value)
    assert await repository.get(Channel.PUSH) is None


async def test_upsert_names_the_email_secret_env_var_for_email_config() -> None:
    service, _ = _service(_email())

    with pytest.raises(DomainError) as raised:
        await service.upsert(Channel.EMAIL, "mailgun", {"from": "a@example.com", "api_key": "leak"})

    assert "MAILGUN__API_KEY" in str(raised.value)


async def test_upsert_delegates_the_config_shape_to_the_adapter() -> None:
    service, repository = _service(_RejectingProvider(channel=Channel.EMAIL, name="mailgun"))

    with pytest.raises(DomainError):
        await service.upsert(Channel.EMAIL, "mailgun", {"from": "a@example.com"})

    assert await repository.get(Channel.EMAIL) is None


async def test_upsert_stores_the_adapter_normalized_config() -> None:
    class _NormalizingProvider(FakeChannelProvider):
        def validate_config(self, config: Mapping[str, object]) -> Mapping[str, object]:
            return {"topic": str(config["topic"]).strip()}

    service, _ = _service(_NormalizingProvider(channel=Channel.PUSH, name="ntfy"))

    result = await service.upsert(Channel.PUSH, "ntfy", {"topic": "  hablator  "})

    assert result.view.config == {"topic": "hablator"}


async def test_delete_removes_the_row_and_is_idempotent() -> None:
    config = ProviderConfig(channel=Channel.PUSH, provider="ntfy", config={"topic": "hablator"}, updated_at=_NOW)
    service, repository = _service(_push(), configs={Channel.PUSH: config})

    await service.delete(Channel.PUSH)
    await service.delete(Channel.PUSH)

    assert await repository.get(Channel.PUSH) is None


async def test_a_config_change_logs_channel_and_provider_never_values(telemetry: Telemetry) -> None:
    registry = ChannelRegistry()
    registry.register(_push())
    service = ChannelConfigService(
        clock=FixedClock(_NOW),
        transaction=InlineTransaction(),
        repository=InMemoryProviderConfigRepository(),
        registry=registry,
    )

    await service.upsert(Channel.PUSH, "ntfy", {"topic": "secret-topic-value"})

    records = [item.log_record for item in log_records(telemetry) if item.log_record.body == "config.channel.updated"]
    assert len(records) == 1
    record = records[0]
    assert record.severity_text == "INFO"
    assert record.attributes["channel"] == "push"
    assert record.attributes["provider"] == "ntfy"
    assert "secret-topic-value" not in record.attributes.values()
