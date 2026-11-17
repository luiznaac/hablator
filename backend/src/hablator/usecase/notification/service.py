"""`NotificationService` — create the notification and its deliveries, then fan the first attempt out.

Persisting the notification and its pending deliveries is one transaction; each delivery is then
dispatched concurrently, and the outcome carries every delivery and attempt.
"""

from __future__ import annotations

from hablator.usecase.commons.asyncx import map_async
from hablator.usecase.commons.time import IClock
from hablator.usecase.configuration.transaction import ITransactionTemplate
from hablator.usecase.notification.model import (
    Delivery,
    DeliveryStatus,
    Notification,
    NotificationOutcome,
    NotificationRequest,
)
from hablator.usecase.notification.ports import IDeliveryDispatcher, INotificationRepository


class NotificationService:
    def __init__(
        self,
        *,
        clock: IClock,
        transaction: ITransactionTemplate,
        repository: INotificationRepository,
        dispatcher: IDeliveryDispatcher,
    ) -> None:
        self._clock = clock
        self._transaction = transaction
        self._repository = repository
        self._dispatcher = dispatcher

    async def send(self, request: NotificationRequest) -> NotificationOutcome:
        now = self._clock.now()
        notification = Notification(
            id=None,
            source=request.source,
            content=request.content,
            created_at=now,
        )
        deliveries = [
            Delivery(
                id=None,
                notification_id=None,
                channel=channel.channel,
                status=DeliveryStatus.PENDING,
                recipients=channel.recipients,
                content=channel.content or request.content,
                options=channel.options,
                next_attempt_at=None,
                created_at=now,
                updated_at=now,
            )
            for channel in request.channels
        ]
        persisted_notification, persisted_deliveries = await self._transaction.execute(
            lambda: self._repository.create(notification, deliveries)
        )
        outcomes = await map_async(persisted_deliveries, self._dispatcher.dispatch)
        return NotificationOutcome(notification=persisted_notification, deliveries=tuple(outcomes))
