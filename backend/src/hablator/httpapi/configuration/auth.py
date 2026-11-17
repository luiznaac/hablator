"""Bearer authentication for the new API.

One token from the environment (`AUTH__API_TOKEN`), compared in constant time. Attached as a
router dependency so the legacy `/send-email`, `/health*`, `/docs` and `/openapi.json` stay open.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

import fastapi

from hablator.usecase.commons.exceptions import UnauthorizedError


def bearer_auth(expected_token: str) -> Callable[[fastapi.Request], Awaitable[None]]:
    """Build the FastAPI dependency that enforces `Authorization: Bearer <expected_token>`."""
    expected = expected_token.encode("utf-8")

    async def _verify(request: fastapi.Request) -> None:
        header = request.headers.get("Authorization", "")
        scheme, _, credentials = header.partition(" ")
        if scheme.lower() != "bearer" or not credentials:
            raise UnauthorizedError("Missing bearer token")
        if not hmac.compare_digest(credentials.encode("utf-8"), expected):
            raise UnauthorizedError("Invalid bearer token")

    return _verify
