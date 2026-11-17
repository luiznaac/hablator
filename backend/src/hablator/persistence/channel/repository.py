"""Per-channel configuration repositories: provider config and retry policy, one row per channel."""

from __future__ import annotations

from hablator.persistence.channel.entity import ProviderConfigEntity, RetryPolicyEntity
from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.usecase.channel.model import Channel, ProviderConfig, RetryPolicy


class ProviderConfigRepository:
    async def get(self, channel: Channel) -> ProviderConfig | None:
        session = current_session()
        entity = await session.get(ProviderConfigEntity, str(channel))
        if entity is None:
            return None
        return ProviderConfig(
            channel=Channel(entity.channel),
            provider=entity.provider,
            config=dict(entity.config),
            updated_at=from_db_utc(entity.updated_at),
        )

    async def upsert(self, config: ProviderConfig) -> ProviderConfig:
        session = current_session()
        entity = await session.get(ProviderConfigEntity, str(config.channel))
        if entity is None:
            entity = ProviderConfigEntity(channel=str(config.channel))
            session.add(entity)
        entity.provider = config.provider
        entity.config = dict(config.config)
        entity.updated_at = to_db_utc(config.updated_at)
        await session.flush()
        return config

    async def delete(self, channel: Channel) -> None:
        session = current_session()
        entity = await session.get(ProviderConfigEntity, str(channel))
        if entity is not None:
            await session.delete(entity)
            await session.flush()


class RetryPolicyRepository:
    async def get(self, channel: Channel) -> RetryPolicy | None:
        session = current_session()
        entity = await session.get(RetryPolicyEntity, str(channel))
        if entity is None:
            return None
        return RetryPolicy(
            channel=Channel(entity.channel),
            max_attempts=entity.max_attempts,
            backoff_seconds=tuple(entity.backoff_seconds),
            updated_at=from_db_utc(entity.updated_at),
        )

    async def upsert(self, policy: RetryPolicy) -> RetryPolicy:
        session = current_session()
        entity = await session.get(RetryPolicyEntity, str(policy.channel))
        if entity is None:
            entity = RetryPolicyEntity(channel=str(policy.channel))
            session.add(entity)
        entity.max_attempts = policy.max_attempts
        entity.backoff_seconds = list(policy.backoff_seconds)
        entity.updated_at = to_db_utc(policy.updated_at)
        await session.flush()
        return policy
