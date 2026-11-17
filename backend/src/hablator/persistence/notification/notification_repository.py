"""`INotificationRepository` against MySQL — creation, aggregate read and the history query."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.entity import DeliveryEntity, NotificationEntity
from hablator.persistence.notification.mapping import notification_entity, notification_from_entity
from hablator.usecase.channel.model import Channel
from hablator.usecase.configuration.transaction import ITransactionTemplate
from hablator.usecase.notification.model import (
    DeliveryStatus,
    HistoryQuery,
    NewNotification,
    Notification,
    NotificationStatus,
    NotificationSummary,
    Page,
    derive_notification_status,
)

_DeliveryView = tuple[tuple[Channel, DeliveryStatus], ...]


class SqlAlchemyNotificationRepository:
    def __init__(self, transactions: ITransactionTemplate) -> None:
        self._transactions = transactions

    async def create(self, notification: NewNotification, *, now: datetime) -> Notification:
        async def _create() -> Notification:
            session = current_session()
            entity = notification_entity(notification, now)
            session.add(entity)
            await session.flush()
            return notification_from_entity(entity)

        return await self._transactions.execute(_create)

    async def get(self, notification_id: int) -> Notification | None:
        async def _get() -> Notification | None:
            session = current_session()
            statement = (
                select(NotificationEntity)
                .options(selectinload(NotificationEntity.deliveries).selectinload(DeliveryEntity.attempts))
                .where(NotificationEntity.id == notification_id)
            )
            entity = (await session.execute(statement)).scalar_one_or_none()
            return notification_from_entity(entity) if entity is not None else None

        return await self._transactions.execute(_get)

    async def history(self, query: HistoryQuery) -> Page[NotificationSummary]:
        async def _history() -> Page[NotificationSummary]:
            session = current_session()
            filters = _filters(query)
            ordered = (
                select(
                    NotificationEntity.id,
                    NotificationEntity.source,
                    NotificationEntity.subject,
                    NotificationEntity.created_at,
                )
                .where(*filters)
                .order_by(NotificationEntity.created_at.desc(), NotificationEntity.id.desc())
            )

            if query.status is None:
                count_statement = select(func.count()).select_from(NotificationEntity).where(*filters)
                total = int(await session.scalar(count_statement) or 0)
                rows = (await session.execute(ordered.limit(query.limit).offset(query.offset))).all()
                views = await _delivery_views(session, [row.id for row in rows])
            else:
                candidates = (await session.execute(ordered)).all()
                all_views = await _delivery_views(session, [row.id for row in candidates])
                matching = [row for row in candidates if _derived(all_views, row.id) is query.status]
                total = len(matching)
                rows = matching[query.offset : query.offset + query.limit]
                views = {row.id: all_views.get(row.id, ()) for row in rows}

            items = tuple(
                NotificationSummary(
                    id=row.id,
                    source=row.source,
                    subject=row.subject,
                    status=_derived(views, row.id),
                    created_at=from_db_utc(row.created_at),
                    channels=tuple(channel for channel, _ in views.get(row.id, ())),
                )
                for row in rows
            )
            return Page(items=items, total=total, limit=query.limit, offset=query.offset)

        return await self._transactions.execute(_history)


def _filters(query: HistoryQuery) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.source is not None:
        filters.append(NotificationEntity.source == query.source)
    if query.channel is not None:
        filters.append(
            exists()
            .where(DeliveryEntity.notification_id == NotificationEntity.id)
            .where(DeliveryEntity.channel == query.channel.value)
        )
    if query.created_after is not None:
        filters.append(NotificationEntity.created_at >= to_db_utc(query.created_after))
    if query.created_before is not None:
        filters.append(NotificationEntity.created_at < to_db_utc(query.created_before))
    return filters


def _derived(views: dict[int, _DeliveryView], notification_id: int) -> NotificationStatus:
    return derive_notification_status(status for _, status in views.get(notification_id, ()))


async def _delivery_views(session: AsyncSession, notification_ids: Sequence[int]) -> dict[int, _DeliveryView]:
    """The channel and status of every delivery of the given notifications, ordered by delivery id."""
    if not notification_ids:
        return {}
    statement: Select[tuple[int, str, str]] = (
        select(DeliveryEntity.notification_id, DeliveryEntity.channel, DeliveryEntity.status)
        .where(DeliveryEntity.notification_id.in_(notification_ids))
        .order_by(DeliveryEntity.id)
    )
    grouped: dict[int, list[tuple[Channel, DeliveryStatus]]] = defaultdict(list)
    for notification_id, channel, status in (await session.execute(statement)).all():
        grouped[notification_id].append((Channel(channel), DeliveryStatus(status)))
    return {notification_id: tuple(views) for notification_id, views in grouped.items()}
