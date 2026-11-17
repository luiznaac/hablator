"""`IRetryPolicyRepository` against MySQL — modeled now, unused in v1."""

from __future__ import annotations

from hablator.persistence.channel.entity import RetryPolicyEntity
from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.usecase.channel.model import Channel, RetryPolicy
from hablator.usecase.configuration.transaction import ITransactionTemplate


def _from_entity(entity: RetryPolicyEntity) -> RetryPolicy:
    return RetryPolicy(
        channel=Channel(entity.channel),
        max_attempts=entity.max_attempts,
        backoff_seconds=tuple(entity.backoff_seconds),
        updated_at=from_db_utc(entity.updated_at),
    )


class SqlAlchemyRetryPolicyRepository:
    def __init__(self, transactions: ITransactionTemplate) -> None:
        self._transactions = transactions

    async def get(self, channel: Channel) -> RetryPolicy | None:
        async def _get() -> RetryPolicy | None:
            session = current_session()
            entity = await session.get(RetryPolicyEntity, channel.value)
            return _from_entity(entity) if entity is not None else None

        return await self._transactions.execute(_get)

    async def upsert(self, policy: RetryPolicy) -> RetryPolicy:
        async def _upsert() -> RetryPolicy:
            session = current_session()
            entity = await session.get(RetryPolicyEntity, policy.channel.value)
            if entity is None:
                entity = RetryPolicyEntity(channel=policy.channel.value)
                session.add(entity)
            entity.max_attempts = policy.max_attempts
            entity.backoff_seconds = list(policy.backoff_seconds)
            entity.updated_at = to_db_utc(policy.updated_at)
            await session.flush()
            return _from_entity(entity)

        return await self._transactions.execute(_upsert)
