"""`GET`/`PUT`/`DELETE /channels` — the admin surface for a channel's provider configuration.

The controller maps the edge DTOs to the domain service, which owns every rule (a registered
provider, a secret-shaped key, the per-adapter config shape) and logs the change without values.
Auth and the JSON body guard are router/route dependencies.
"""

from __future__ import annotations

import fastapi

from hablator.httpapi.configuration.auth import bearer_auth
from hablator.httpapi.configuration.guards import json_request_guard
from hablator.httpapi.schema import ChannelConfigRequestDTO, ChannelConfigResponse
from hablator.usecase.channel.model import Channel
from hablator.usecase.channel.service import ChannelConfigService
from hablator.usecase.commons.exceptions import DomainError


class ChannelController:
    def __init__(self, service: ChannelConfigService, *, api_token: str) -> None:
        self._service = service
        self._api_token = api_token

    def router(self) -> fastapi.APIRouter:
        router = fastapi.APIRouter(tags=["channels"], dependencies=[fastapi.Depends(bearer_auth(self._api_token))])

        @router.get("/channels", response_model=list[ChannelConfigResponse])
        async def list_channels() -> list[ChannelConfigResponse]:
            return [ChannelConfigResponse.from_domain(view) for view in await self._service.list()]

        @router.put(
            "/channels/{channel}",
            response_model=ChannelConfigResponse,
            dependencies=[fastapi.Depends(json_request_guard)],
        )
        async def put_channel(
            channel: str,
            payload: ChannelConfigRequestDTO,
            response: fastapi.Response,
        ) -> ChannelConfigResponse:
            result = await self._service.upsert(_channel(channel), payload.provider, payload.config)
            response.status_code = 201 if result.created else 200
            return ChannelConfigResponse.from_domain(result.view)

        @router.delete("/channels/{channel}", status_code=204, response_class=fastapi.Response)
        async def delete_channel(channel: str) -> None:
            await self._service.delete(_channel(channel))

        return router


def _channel(value: str) -> Channel:
    try:
        return Channel(value)
    except ValueError as error:
        raise DomainError(f"Unknown channel '{value}'") from error
