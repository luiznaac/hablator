"""`POST /notifications` and `GET /notifications/{id}`.

The controller maps the edge DTOs to the domain request, calls the service, and reads the
notification back so both endpoints answer with one representation. Auth and the body guards are
router/route dependencies; the service owns every channel rule.
"""

from __future__ import annotations

import fastapi

from hablator.httpapi.configuration.auth import bearer_auth
from hablator.httpapi.configuration.guards import json_request_guard
from hablator.httpapi.schema import NotificationDetailResponse, NotificationRequestDTO
from hablator.usecase.commons.exceptions import require_id
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

        @router.get("/notifications/{notification_id}", response_model=NotificationDetailResponse)
        async def get_notification(notification_id: int) -> NotificationDetailResponse:
            return NotificationDetailResponse.from_domain(await self._service.read(notification_id))

        return router
