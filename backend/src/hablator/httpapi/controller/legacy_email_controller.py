"""`POST /send-email` — the legacy compatibility adapter.

The controller only maps the legacy payload (`emails`, `subject`, `text`) to a notification request
and the service outcome back to the legacy response shape. Provider logic lives behind
`NotificationService`; the plain-text alternative is derived here because only this legacy path
does so.

Deliberate divergence from the `httpapi/schema.py` DTO convention: the legacy contract is pinned
byte-for-byte (including `json.dumps` spacing and the absence of a charset), and it must answer
invalid JSON with a `400` rather than FastAPI's `422`. A Pydantic request model would change both,
so this one controller parses raw JSON and serializes raw JSON.
"""

from __future__ import annotations

import json

import fastapi

from hablator.httpapi.legacy_text import strip_html
from hablator.usecase.channel.model import Channel, Content, Recipient
from hablator.usecase.commons.exceptions import DomainError
from hablator.usecase.notification.model import ChannelRequest, NotificationRequest
from hablator.usecase.notification.service import NotificationService

_LEGACY_CHANNEL = Channel.EMAIL


class LegacyEmailController:
    def __init__(self, notification_service: NotificationService) -> None:
        self._service = notification_service

    def router(self) -> fastapi.APIRouter:
        router = fastapi.APIRouter(tags=["legacy"])

        @router.post("/send-email")
        async def send_email(request: fastapi.Request) -> fastapi.Response:
            payload = await _parse_payload(request)
            if payload is None:
                return _legacy_json(400, {"error": "Invalid JSON"})

            emails = payload.get("emails")
            subject = payload.get("subject")
            text = payload.get("text")

            if not emails or not isinstance(emails, list):
                return _legacy_json(400, {"error": "'emails' must be a non-empty list"})
            if not isinstance(subject, str) or not isinstance(text, str) or not subject or not text:
                return _legacy_json(400, {"error": "'subject' and 'text' are required"})

            content = Content(subject=subject, body_text=strip_html(text), body_html=text)
            try:
                outcome = await self._service.send(
                    NotificationRequest(
                        content=content,
                        channels=(
                            ChannelRequest(
                                channel=_LEGACY_CHANNEL,
                                recipients=tuple(Recipient(address=email) for email in emails),
                            ),
                        ),
                    )
                )
            except DomainError as error:
                # The legacy endpoint keeps its own `{"error": ...}` 400 shape for a rejected
                # request; the new API's envelope never leaks here.
                return _legacy_json(400, {"error": str(error)})

            delivery = outcome.deliveries[0]
            if delivery.succeeded:
                return _legacy_json(200, {"message": "Emails sent successfully", "response": delivery.provider_body})
            return _legacy_json(502, {"error": "Failed to send emails", "response": delivery.provider_body})

        return router


async def _parse_payload(request: fastapi.Request) -> dict[str, object] | None:
    try:
        payload = await request.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _legacy_json(status: int, body: dict[str, object]) -> fastapi.Response:
    """Serialize exactly like the legacy proxy: `json.dumps` defaults, no charset in the header."""
    return fastapi.Response(content=json.dumps(body), status_code=status, media_type="application/json")
