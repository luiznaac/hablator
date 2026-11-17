"""`NotificationRepository` — the `INotificationRepository` adapter over the notification tables."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from hablator.persistence.configuration.transaction import current_session
from hablator.persistence.notification.entity import AttemptEntity, DeliveryEntity, NotificationEntity
from hablator.usecase.commons.exceptions import ResourceNotFoundError
from hablator.usecase.notification.model import Attempt, Delivery, Notification


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
            created_at=notification.created_at,
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

    async def update_delivery(self, delivery: Delivery) -> None:
        session = current_session()
        entity = await session.get(DeliveryEntity, delivery.id)
        if entity is None:
            raise ResourceNotFoundError("delivery", str(delivery.id))
        entity.status = str(delivery.status)
        entity.next_attempt_at = delivery.next_attempt_at
        entity.updated_at = delivery.updated_at

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
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )
        session.add(entity)
        await session.flush()
        return replace(attempt, id=entity.id)

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
            next_attempt_at=delivery.next_attempt_at,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )
