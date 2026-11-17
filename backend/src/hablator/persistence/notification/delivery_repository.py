"""`IDeliveryRepository` against MySQL. Attempts are inserted, never updated."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hablator.persistence.configuration.timestamps import to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.entity import DeliveryEntity
from hablator.persistence.notification.mapping import attempt_entity, delivery_from_entity
from hablator.usecase.commons.exceptions import ResourceNotFoundError
from hablator.usecase.configuration.transaction import ITransactionTemplate
from hablator.usecase.notification.model import Attempt, Delivery, DeliveryStatus, transition


async def _load_delivery(session: AsyncSession, delivery_id: int) -> DeliveryEntity | None:
    statement = (
        select(DeliveryEntity).options(selectinload(DeliveryEntity.attempts)).where(DeliveryEntity.id == delivery_id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


class SqlAlchemyDeliveryRepository:
    def __init__(self, transactions: ITransactionTemplate) -> None:
        self._transactions = transactions

    async def get(self, delivery_id: int) -> Delivery | None:
        async def _get() -> Delivery | None:
            entity = await _load_delivery(current_session(), delivery_id)
            return delivery_from_entity(entity) if entity is not None else None

        return await self._transactions.execute(_get)

    async def append_attempt(self, delivery_id: int, attempt: Attempt) -> None:
        async def _append() -> None:
            session = current_session()
            session.add(attempt_entity(delivery_id, attempt))
            await session.flush()

        await self._transactions.execute(_append)

    async def transition(
        self,
        delivery_id: int,
        status: DeliveryStatus,
        *,
        next_attempt_at: datetime | None = None,
        now: datetime,
    ) -> Delivery:
        async def _transition() -> Delivery:
            session = current_session()
            entity = await _load_delivery(session, delivery_id)
            if entity is None:
                raise ResourceNotFoundError("delivery", str(delivery_id))
            moved = transition(
                delivery_from_entity(entity),
                status,
                now=now,
                next_attempt_at=next_attempt_at,
            )
            entity.status = moved.status.value
            entity.next_attempt_at = to_db_utc(moved.next_attempt_at) if moved.next_attempt_at is not None else None
            entity.updated_at = to_db_utc(moved.updated_at)
            await session.flush()
            return delivery_from_entity(entity)

        return await self._transactions.execute(_transition)
