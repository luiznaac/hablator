"""`NotificationService` — create the notification and its deliveries, then fan the first attempt out.

Persisting the notification and its pending deliveries is one transaction, and it is also where
every channel rule is checked: a duplicate channel, a channel with no registered provider, or a
request the channel's own adapter rejects fails before a row exists. Each delivery is then
dispatched concurrently, and the outcome carries every delivery and attempt.
"""

from __future__ import annotations

from datetime import datetime

from hablator.usecase.channel.defaults import resolve_provider
from hablator.usecase.channel.model import Channel, ChannelMessage
from hablator.usecase.channel.ports import IProviderConfigRepository
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.asyncx import map_async
from hablator.usecase.commons.exceptions import InvalidArgumentError, ResourceNotFoundError
from hablator.usecase.commons.time import IClock
from hablator.usecase.configuration.transaction import ITransactionTemplate
from hablator.usecase.notification.model import (
    ChannelRequest,
    Delivery,
    DeliveryStatus,
    Notification,
    NotificationDetail,
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
        registry: ChannelRegistry,
        provider_configs: IProviderConfigRepository,
    ) -> None:
        self._clock = clock
        self._transaction = transaction
        self._repository = repository
        self._dispatcher = dispatcher
        self._registry = registry
        self._provider_configs = provider_configs

    async def send(self, request: NotificationRequest) -> NotificationOutcome:
        now = self._clock.now()
        notification = Notification(
            id=None,
            source=request.source,
            content=request.content,
            created_at=now,
        )
        persisted_notification, persisted_deliveries = await self._transaction.execute(
            lambda: self._create(notification, request, now)
        )
        outcomes = await map_async(persisted_deliveries, self._dispatcher.dispatch)
        return NotificationOutcome(notification=persisted_notification, deliveries=tuple(outcomes))

    async def read(self, notification_id: int) -> NotificationDetail:
        """Load a notification with its deliveries and attempts.

        Raises:
            ResourceNotFoundError: when no notification has that id.
        """
        detail = await self._transaction.execute(lambda: self._repository.get(notification_id))
        if detail is None:
            raise ResourceNotFoundError("notification", str(notification_id))
        return detail

    async def _create(
        self,
        notification: Notification,
        request: NotificationRequest,
        now: datetime,
    ) -> tuple[Notification, list[Delivery]]:
        seen: set[Channel] = set()
        deliveries: list[Delivery] = []
        for channel_request in request.channels:
            channel = channel_request.channel
            if channel in seen:
                raise InvalidArgumentError(f"Duplicate channel '{channel}'")
            seen.add(channel)
            deliveries.append(await self._delivery_for(channel_request, request, now))
        return await self._repository.create(notification, deliveries)

    async def _delivery_for(
        self,
        channel_request: ChannelRequest,
        request: NotificationRequest,
        now: datetime,
    ) -> Delivery:
        channel = channel_request.channel
        config = await self._provider_configs.get(channel)
        provider, provider_config = resolve_provider(self._registry, channel, config)

        resolved = provider.prepare(
            ChannelMessage(
                channel=channel,
                recipients=channel_request.recipients,
                content=channel_request.content or request.content,
                options=channel_request.options,
                config=provider_config,
            )
        )
        return Delivery(
            id=None,
            notification_id=None,
            channel=channel,
            status=DeliveryStatus.PENDING,
            recipients=resolved.recipients,
            content=resolved.content,
            options=resolved.options,
            next_attempt_at=None,
            created_at=now,
            updated_at=now,
        )
