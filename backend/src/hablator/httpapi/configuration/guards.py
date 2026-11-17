"""Request guards that run before the body reaches Pydantic.

The API contract rejects a non-JSON body with `415` and a body over 1 MiB with `413`; FastAPI's
own JSON parsing would accept any content type, so the check lives here.
"""

from __future__ import annotations

import fastapi

from hablator.usecase.commons.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError

MAX_REQUEST_BYTES = 1024 * 1024


def _is_json(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _declared_length(request: fastapi.Request) -> int | None:
    declared = request.headers.get("Content-Length")
    if declared is None:
        return None
    try:
        return int(declared)
    except ValueError:
        return None


async def json_request_guard(request: fastapi.Request) -> None:
    """Reject a non-JSON content type, then a body over 1 MiB.

    Raises:
        UnsupportedMediaTypeError: when the `Content-Type` is not JSON.
        PayloadTooLargeError: when the declared or actual body exceeds 1 MiB.
    """
    if not _is_json(request.headers.get("Content-Type", "")):
        raise UnsupportedMediaTypeError("The request body must be application/json")

    declared = _declared_length(request)
    if declared is not None and declared > MAX_REQUEST_BYTES:
        raise PayloadTooLargeError(f"The request body exceeds {MAX_REQUEST_BYTES} bytes")

    body = await request.body()
    if len(body) > MAX_REQUEST_BYTES:
        raise PayloadTooLargeError(f"The request body exceeds {MAX_REQUEST_BYTES} bytes")
