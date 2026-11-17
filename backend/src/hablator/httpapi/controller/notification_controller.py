"""`POST /notifications`, `GET /notifications`, `GET /notifications/{id}` and the delivery retry.

The controller maps the edge DTOs to the domain request, calls the service, and reads the
notification back so the create and detail endpoints answer with one representation. Auth and the
body guards are router/route dependencies; the service owns every channel rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import fastapi

from hablator.httpapi.configuration.auth import bearer_auth
from hablator.httpapi.configuration.guards import json_request_guard
from hablator.httpapi.schema import (
    MAX_SOURCE_CHARS,
    DeliveryResponse,
    NotificationDetailResponse,
    NotificationPageResponse,
    NotificationRequestDTO,
)
from hablator.usecase.channel.model import Channel
from hablator.usecase.commons.exceptions import require_id
from hablator.usecase.notification.model import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    HistoryQuery,
    NotificationStatus,
)
from hablator.usecase.notification.service import NotificationService


class NotificationController:
    def __init__(self, service: NotificationService, *, api_token: str) -> None:
        self._service = service
        self._api_token = api_token

    def router(self) -> fastapi.APIRouter:
        router = fastapi.APIRouter(tags=["notifications"], dependencies=[fastapi.Depends(bearer_auth(self._api_token))])

        @router.post(
            "/notifications",
            status_code=201,
            response_model=NotificationDetailResponse,
            dependencies=[fastapi.Depends(json_request_guard)],
        )
        async def create_notification(
            payload: NotificationRequestDTO,
            response: fastapi.Response,
        ) -> NotificationDetailResponse:
            outcome = await self._service.send(payload.to_domain())
            detail = await self._service.read(require_id(outcome.notification.id, "notification"))
            response.headers["Location"] = f"/notifications/{require_id(detail.notification.id, 'notification')}"
            return NotificationDetailResponse.from_domain(detail)

        @router.get("/notifications", response_model=NotificationPageResponse)
        async def list_notifications(
            source: Annotated[str | None, fastapi.Query(max_length=MAX_SOURCE_CHARS)] = None,
            channel: Annotated[Channel | None, fastapi.Query()] = None,
            status: Annotated[NotificationStatus | None, fastapi.Query()] = None,
            created_after: Annotated[datetime | None, fastapi.Query()] = None,
            created_before: Annotated[datetime | None, fastapi.Query()] = None,
            limit: Annotated[int, fastapi.Query(ge=MIN_PAGE_LIMIT, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
            offset: Annotated[int, fastapi.Query(ge=0)] = 0,
        ) -> NotificationPageResponse:
            query = HistoryQuery(
                source=source,
                channel=channel,
                status=status,
                created_after=created_after,
                created_before=created_before,
                limit=limit,
                offset=offset,
            )
            return NotificationPageResponse.from_domain(await self._service.history(query))

        @router.get("/notifications/{notification_id}", response_model=NotificationDetailResponse)
        async def get_notification(notification_id: int) -> NotificationDetailResponse:
            return NotificationDetailResponse.from_domain(await self._service.read(notification_id))

        @router.post("/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
        async def retry_delivery(delivery_id: int) -> DeliveryResponse:
            detail = await self._service.retry(delivery_id)
            return DeliveryResponse.from_domain(detail.delivery, detail.attempts)

        return router
