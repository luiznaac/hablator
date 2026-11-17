"""`NotificationRepository` — the `INotificationRepository`/`IDeliveryRepository` adapter.

The write methods convert the domain's aware-UTC timestamps to naive UTC at the database boundary
(`to_db_utc`); every read converts back (`from_db_utc`). History's derived-status filter is the
spec's in-app aggregate, while the channel filter is a delivery-level `EXISTS`.
"""

from __future__ import annotations

import collections
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

import sqlalchemy
import sqlalchemy.ext.asyncio

from hablator.persistence.configuration.timestamps import from_db_utc, to_db_utc
from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.entity import AttemptEntity, DeliveryEntity, NotificationEntity
from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient
from hablator.usecase.commons.exceptions import ResourceNotFoundError
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    Delivery,
    DeliveryDetail,
    DeliveryStatus,
    HistoryQuery,
    Notification,
    NotificationDetail,
    NotificationSummary,
    Page,
    derive_status_from_statuses,
)

_DeliveryView = tuple[tuple[Channel, DeliveryStatus], ...]


class NotificationRepository:
    async def create(
        self, notification: Notification, deliveries: Sequence[Delivery]
    ) -> tuple[Notification, list[Delivery]]:
        session = current_session()
        notification_entity = NotificationEntity(
            source=notification.source,
            subject=notification.content.subject,
            body_text=notification.content.body_text,
            body_html=notification.content.body_html,
            created_at=to_db_utc(notification.created_at),
        )
        session.add(notification_entity)
        await session.flush()

        delivery_entities = [self._to_delivery_entity(delivery, notification_entity.id) for delivery in deliveries]
        session.add_all(delivery_entities)
        await session.flush()

        persisted_notification = replace(notification, id=notification_entity.id)
        persisted_deliveries = [
            replace(delivery, id=entity.id, notification_id=notification_entity.id)
            for delivery, entity in zip(deliveries, delivery_entities, strict=True)
        ]
        return persisted_notification, persisted_deliveries

    async def get(self, notification_id: int) -> NotificationDetail | None:
        session = current_session()
        statement = sqlalchemy.select(NotificationEntity).where(NotificationEntity.id == notification_id)
        notification_entity = (await session.execute(statement)).scalar_one_or_none()
        if notification_entity is None:
            return None

        delivery_statement = (
            sqlalchemy.select(DeliveryEntity)
            .where(DeliveryEntity.notification_id == notification_id)
            .order_by(DeliveryEntity.id)
        )
        delivery_entities = list((await session.execute(delivery_statement)).scalars().all())
        attempts_by_delivery: dict[int, list[Attempt]] = collections.defaultdict(list)
        for attempt_entity in await _attempts_for(session, [entity.id for entity in delivery_entities]):
            attempts_by_delivery[attempt_entity.delivery_id].append(_attempt_from_entity(attempt_entity))

        return NotificationDetail(
            notification=_notification_from_entity(notification_entity),
            deliveries=tuple(
                DeliveryDetail(
                    delivery=_delivery_from_entity(entity),
                    attempts=tuple(attempts_by_delivery.get(entity.id, ())),
                )
                for entity in delivery_entities
            ),
        )

    async def update_delivery(self, delivery: Delivery) -> None:
        session = current_session()
        entity = await session.get(DeliveryEntity, delivery.id)
        if entity is None:
            raise ResourceNotFoundError("delivery", str(delivery.id))
        entity.status = str(delivery.status)
        entity.next_attempt_at = to_db_utc(delivery.next_attempt_at) if delivery.next_attempt_at is not None else None
        entity.updated_at = to_db_utc(delivery.updated_at)

    async def add_attempt(self, attempt: Attempt) -> Attempt:
        session = current_session()
        entity = AttemptEntity(
            delivery_id=attempt.delivery_id,
            attempt_number=attempt.attempt_number,
            outcome=str(attempt.outcome),
            provider=attempt.provider,
            provider_status=attempt.provider_status,
            error_kind=str(attempt.error_kind) if attempt.error_kind is not None else None,
            error_message=attempt.error_message,
            retriable=attempt.retriable,
            started_at=to_db_utc(attempt.started_at),
            finished_at=to_db_utc(attempt.finished_at) if attempt.finished_at is not None else None,
        )
        session.add(entity)
        await session.flush()
        return replace(attempt, id=entity.id)

    async def history(self, query: HistoryQuery) -> Page[NotificationSummary]:
        """One page of notification history, newest first.

        Args:
            query: The source/channel/derived-status/date filters and offset pagination.

        Returns:
            A page of summaries; `total` is the count after filtering.
        """
        session = current_session()
        filters = _filters(query)
        ordered = (
            sqlalchemy.select(
                NotificationEntity.id,
                NotificationEntity.source,
                NotificationEntity.subject,
                NotificationEntity.created_at,
            )
            .where(*filters)
            .order_by(NotificationEntity.created_at.desc(), NotificationEntity.id.desc())
        )

        if query.status is None:
            count_statement = sqlalchemy.select(sqlalchemy.func.count()).select_from(NotificationEntity).where(*filters)
            total = int(await session.scalar(count_statement) or 0)
            rows = (await session.execute(ordered.limit(query.limit).offset(query.offset))).all()
            views = await _delivery_views(session, [row.id for row in rows])
        else:
            candidates = (await session.execute(ordered)).all()
            all_views = await _delivery_views(session, [row.id for row in candidates])
            matching = [
                row
                for row in candidates
                if derive_status_from_statuses(status for _, status in all_views.get(row.id, ())) is query.status
            ]
            total = len(matching)
            rows = matching[query.offset : query.offset + query.limit]
            views = {row.id: all_views.get(row.id, ()) for row in rows}

        items = tuple(_summary(row.id, row.source, row.subject, row.created_at, views.get(row.id, ())) for row in rows)
        return Page(items=items, total=total, limit=query.limit, offset=query.offset)

    def _to_delivery_entity(self, delivery: Delivery, notification_id: int) -> DeliveryEntity:
        return DeliveryEntity(
            notification_id=notification_id,
            channel=str(delivery.channel),
            status=str(delivery.status),
            recipients=[recipient.address for recipient in delivery.recipients],
            subject=delivery.content.subject,
            body_text=delivery.content.body_text,
            body_html=delivery.content.body_html,
            options=dict(delivery.options),
            next_attempt_at=to_db_utc(delivery.next_attempt_at) if delivery.next_attempt_at is not None else None,
            created_at=to_db_utc(delivery.created_at),
            updated_at=to_db_utc(delivery.updated_at),
        )


def _content(subject: str | None, body_text: str, body_html: str | None) -> Content:
    return Content(subject=subject, body_text=body_text, body_html=body_html)


def _notification_from_entity(entity: NotificationEntity) -> Notification:
    return Notification(
        id=entity.id,
        source=entity.source,
        content=_content(entity.subject, entity.body_text, entity.body_html),
        created_at=from_db_utc(entity.created_at),
    )


def _delivery_from_entity(entity: DeliveryEntity) -> Delivery:
    return Delivery(
        id=entity.id,
        notification_id=entity.notification_id,
        channel=Channel(entity.channel),
        status=DeliveryStatus(entity.status),
        recipients=tuple(Recipient(address) for address in entity.recipients),
        content=_content(entity.subject, entity.body_text, entity.body_html),
        options=dict(entity.options),
        next_attempt_at=from_db_utc(entity.next_attempt_at) if entity.next_attempt_at is not None else None,
        created_at=from_db_utc(entity.created_at),
        updated_at=from_db_utc(entity.updated_at),
    )


def _attempt_from_entity(entity: AttemptEntity) -> Attempt:
    return Attempt(
        id=entity.id,
        delivery_id=entity.delivery_id,
        attempt_number=entity.attempt_number,
        outcome=AttemptOutcome(entity.outcome),
        provider=entity.provider,
        provider_status=entity.provider_status,
        error_kind=ErrorKind(entity.error_kind) if entity.error_kind is not None else None,
        error_message=entity.error_message,
        retriable=bool(entity.retriable),
        started_at=from_db_utc(entity.started_at),
        finished_at=from_db_utc(entity.finished_at) if entity.finished_at is not None else None,
    )


async def _attempts_for(
    session: sqlalchemy.ext.asyncio.AsyncSession, delivery_ids: Sequence[int]
) -> list[AttemptEntity]:
    if not delivery_ids:
        return []
    statement = (
        sqlalchemy.select(AttemptEntity)
        .where(AttemptEntity.delivery_id.in_(delivery_ids))
        .order_by(AttemptEntity.delivery_id, AttemptEntity.attempt_number)
    )
    return list((await session.execute(statement)).scalars().all())


def _filters(query: HistoryQuery) -> list[sqlalchemy.ColumnElement[bool]]:
    filters: list[sqlalchemy.ColumnElement[bool]] = []
    if query.source is not None:
        filters.append(NotificationEntity.source == query.source)
    if query.channel is not None:
        filters.append(
            sqlalchemy.exists()
            .where(DeliveryEntity.notification_id == NotificationEntity.id)
            .where(DeliveryEntity.channel == str(query.channel))
        )
    if query.created_after is not None:
        filters.append(NotificationEntity.created_at >= to_db_utc(query.created_after))
    if query.created_before is not None:
        filters.append(NotificationEntity.created_at < to_db_utc(query.created_before))
    return filters


async def _delivery_views(
    session: sqlalchemy.ext.asyncio.AsyncSession, notification_ids: Sequence[int]
) -> dict[int, _DeliveryView]:
    """The channel and status of every delivery of the given notifications, ordered by delivery id."""
    if not notification_ids:
        return {}
    statement = (
        sqlalchemy.select(DeliveryEntity.notification_id, DeliveryEntity.channel, DeliveryEntity.status)
        .where(DeliveryEntity.notification_id.in_(notification_ids))
        .order_by(DeliveryEntity.id)
    )
    grouped: dict[int, list[tuple[Channel, DeliveryStatus]]] = collections.defaultdict(list)
    for notification_id, channel, status in (await session.execute(statement)).all():
        grouped[notification_id].append((Channel(channel), DeliveryStatus(status)))
    return {notification_id: tuple(views) for notification_id, views in grouped.items()}


def _summary(
    notification_id: int,
    source: str | None,
    subject: str | None,
    created_at: datetime,
    views: _DeliveryView,
) -> NotificationSummary:
    return NotificationSummary(
        id=notification_id,
        source=source,
        subject=subject,
        status=derive_status_from_statuses(status for _, status in views),
        created_at=from_db_utc(created_at),
        channels=tuple(channel for channel, _ in views),
    )
