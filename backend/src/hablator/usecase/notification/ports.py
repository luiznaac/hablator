"""Ports consumed by `NotificationService`: the repository it persists through and the dispatcher
it fans deliveries out to. `IDeliveryDispatcher` lives here (where the service consumes it) and is
implemented in `usecase/delivery`, so the slice graph stays acyclic.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from hablator.usecase.notification.model import (
    Delivery,
    DeliveryDetail,
    DeliveryOutcome,
    HistoryQuery,
    Notification,
    NotificationDetail,
    NotificationSummary,
    Page,
)


class INotificationRepository(Protocol):
    async def create(
        self, notification: Notification, deliveries: Sequence[Delivery]
    ) -> tuple[Notification, list[Delivery]]: ...

    async def get(self, notification_id: int) -> NotificationDetail | None: ...

    async def get_delivery(self, delivery_id: int) -> DeliveryDetail | None: ...

    async def history(self, query: HistoryQuery) -> Page[NotificationSummary]: ...


class IDeliveryDispatcher(Protocol):
    async def dispatch(self, delivery: Delivery) -> DeliveryOutcome: ...
