"""Notification persistence and dispatch ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hablator.usecase.notification.model import (
    Delivery,
    HistoryQuery,
    NewNotification,
    Notification,
    NotificationSummary,
    Page,
)


class INotificationRepository(Protocol):
    async def create(self, notification: NewNotification, *, now: datetime) -> Notification: ...

    async def get(self, notification_id: int) -> Notification | None: ...

    async def history(self, query: HistoryQuery) -> Page[NotificationSummary]: ...


class IDeliveryDispatcher(Protocol):
    """Declared where the notification service consumes it; implemented in the delivery slice."""

    async def dispatch(self, delivery: Delivery) -> Delivery: ...
