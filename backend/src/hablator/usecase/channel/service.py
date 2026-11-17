"""`ChannelConfigService` — the admin surface for a channel's non-secret provider config.

Secrets live in the environment; this service only ever writes the non-secret `config` mapping. It
owns the channel-level rules (a registered provider, a secret-shaped key) and delegates the
per-adapter config shape to the provider itself.
"""

from __future__ import annotations

import re
from datetime import datetime

from hablator.usecase.channel.model import (
    Channel,
    ChannelConfigUpsert,
    ChannelConfigView,
    ProviderConfig,
    ProviderConfigMapping,
)
from hablator.usecase.channel.ports import IProviderConfigRepository
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.exceptions import DomainError
from hablator.usecase.commons.logging import get_logger
from hablator.usecase.commons.time import IClock
from hablator.usecase.configuration.transaction import ITransactionTemplate

_log = get_logger(__name__)

_SECRET_SHAPED_KEY = re.compile(r"api_key|token|secret|password|auth", re.IGNORECASE)
_SECRET_ENV_VARS: dict[Channel, str] = {
    Channel.EMAIL: "MAILGUN__API_KEY",
    Channel.PUSH: "NTFY__TOKEN",
}


class ChannelConfigService:
    def __init__(
        self,
        *,
        clock: IClock,
        transaction: ITransactionTemplate,
        repository: IProviderConfigRepository,
        registry: ChannelRegistry,
    ) -> None:
        self._clock = clock
        self._transaction = transaction
        self._repository = repository
        self._registry = registry

    async def list(self) -> tuple[ChannelConfigView, ...]:
        """Every channel of the vocabulary, configured or not, in vocabulary order."""
        return tuple([await self._view(channel) for channel in Channel])

    async def upsert(
        self,
        channel: Channel,
        provider: str,
        config: ProviderConfigMapping,
    ) -> ChannelConfigUpsert:
        """Full-replace a channel's provider config, validating it before any write.

        Raises:
            DomainError: when the provider is not registered for the channel, a key is
                secret-shaped, or the adapter rejects the config shape.
        """
        validated = self._validate(channel, provider, config)
        now = self._clock.now()
        saved, created = await self._transaction.execute(lambda: self._save(channel, provider, validated, now))
        _log.info("config.channel.updated", channel=str(channel), provider=provider)
        return ChannelConfigUpsert(view=_view_of(channel, saved), created=created)

    async def delete(self, channel: Channel) -> None:
        """Remove a channel's config row; deleting an unconfigured channel is a no-op."""
        removed = await self._transaction.execute(lambda: self._delete_if_present(channel))
        if removed:
            _log.info("config.channel.deleted", channel=str(channel))

    async def _delete_if_present(self, channel: Channel) -> bool:
        if await self._repository.get(channel) is None:
            return False
        await self._repository.delete(channel)
        return True

    async def _view(self, channel: Channel) -> ChannelConfigView:
        config = await self._transaction.execute(lambda: self._repository.get(channel))
        return _view_of(channel, config)

    async def _save(
        self,
        channel: Channel,
        provider: str,
        config: ProviderConfigMapping,
        now: datetime,
    ) -> tuple[ProviderConfig, bool]:
        existing = await self._repository.get(channel)
        saved = await self._repository.upsert(
            ProviderConfig(channel=channel, provider=provider, config=dict(config), updated_at=now)
        )
        return saved, existing is None

    def _validate(self, channel: Channel, provider: str, config: ProviderConfigMapping) -> dict[str, object]:
        implementation = self._registry.get(channel, provider)
        if implementation is None:
            raise DomainError(f"Provider '{provider}' is not registered for channel '{channel}'")
        for key in config:
            if _SECRET_SHAPED_KEY.search(key):
                raise DomainError(_secret_message(channel, key))
        return dict(implementation.validate_config(config))


def _view_of(channel: Channel, config: ProviderConfig | None) -> ChannelConfigView:
    if config is None:
        return ChannelConfigView(channel=channel, provider=None, config=None, updated_at=None)
    return ChannelConfigView(
        channel=channel,
        provider=config.provider,
        config=dict(config.config),
        updated_at=config.updated_at,
    )


def _secret_message(channel: Channel, key: str) -> str:
    env_var = _SECRET_ENV_VARS.get(channel)
    if env_var is None:
        return f"config key '{key}' is secret-shaped; secrets stay in the environment"
    return f"config key '{key}' is secret-shaped; set {env_var} in the environment instead"
