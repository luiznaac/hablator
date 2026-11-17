"""`IProviderConfigRepository` against MySQL — one row per channel, full-replace upsert."""

from __future__ import annotations

from hablator.persistence.channel.entity import ProviderConfigEntity
from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.usecase.channel.model import Channel, ProviderConfig
from hablator.usecase.configuration.transaction import ITransactionTemplate


def _from_entity(entity: ProviderConfigEntity) -> ProviderConfig:
    return ProviderConfig(
        channel=Channel(entity.channel),
        provider=entity.provider,
        config=dict(entity.config),
        updated_at=from_db_utc(entity.updated_at),
    )


class SqlAlchemyProviderConfigRepository:
    def __init__(self, transactions: ITransactionTemplate) -> None:
        self._transactions = transactions

    async def get(self, channel: Channel) -> ProviderConfig | None:
        async def _get() -> ProviderConfig | None:
            session = current_session()
            entity = await session.get(ProviderConfigEntity, channel.value)
            return _from_entity(entity) if entity is not None else None

        return await self._transactions.execute(_get)

    async def upsert(self, config: ProviderConfig) -> ProviderConfig:
        async def _upsert() -> ProviderConfig:
            session = current_session()
            entity = await session.get(ProviderConfigEntity, config.channel.value)
            if entity is None:
                entity = ProviderConfigEntity(channel=config.channel.value)
                session.add(entity)
            entity.provider = config.provider
            entity.config = dict(config.config)
            entity.updated_at = to_db_utc(config.updated_at)
            await session.flush()
            return _from_entity(entity)

        return await self._transactions.execute(_upsert)

    async def delete(self, channel: Channel) -> None:
        async def _delete() -> None:
            session = current_session()
            entity = await session.get(ProviderConfigEntity, channel.value)
            if entity is not None:
                await session.delete(entity)
                await session.flush()

        await self._transactions.execute(_delete)
