"""`IDeliveryRepository` — the persistence port the dispatcher writes a delivery and its attempt
through. Declared in `delivery` (which owns the dispatch lifecycle) and implemented by
`persistence`'s notification repository.
"""

from __future__ import annotations

from typing import Protocol

from hablator.usecase.notification.model import Attempt, Delivery


class IDeliveryRepository(Protocol):
    async def update_delivery(self, delivery: Delivery) -> None: ...

    async def add_attempt(self, attempt: Attempt) -> Attempt: ...
