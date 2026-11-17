"""Delivery persistence port. Attempts are append-only: there is deliberately no update."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hablator.usecase.notification.model import Attempt, Delivery, DeliveryStatus


class IDeliveryRepository(Protocol):
    async def get(self, delivery_id: int) -> Delivery | None: ...

    async def append_attempt(self, delivery_id: int, attempt: Attempt) -> None: ...

    async def transition(
        self,
        delivery_id: int,
        status: DeliveryStatus,
        *,
        next_attempt_at: datetime | None = None,
        now: datetime,
    ) -> Delivery: ...
