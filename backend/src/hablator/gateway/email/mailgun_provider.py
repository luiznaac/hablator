"""Mailgun v3 email provider — the only email adapter in this phase.

One `send` is one Mailgun call with every recipient comma-joined in `to`. It normalizes the
response into a `ProviderResult` and never decides retriability. The non-secret `from`/`bcc`
come from provider config, with the env-backed defaults as the fallback.
"""

from __future__ import annotations

import base64
import json

import httpx

from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    ErrorKind,
    ProviderResult,
)

_PROVIDER_NAME = "mailgun"


class MailgunEmailProvider:
    channel = Channel.EMAIL
    name = _PROVIDER_NAME

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_url: str,
        api_auth: str,
        from_email: str,
        bcc_email: str,
    ) -> None:
        self._http_client = http_client
        self._api_url = api_url
        self._api_auth = api_auth
        self._from_email = from_email
        self._bcc_email = bcc_email

    async def send(self, message: ChannelMessage) -> ProviderResult:
        data = self._form_fields(message)
        authorization = base64.b64encode(f"api:{self._api_auth}".encode()).decode()

        try:
            response = await self._http_client.post(
                self._api_url,
                data=data,
                headers={"Authorization": f"Basic {authorization}"},
            )
        except httpx.TimeoutException as error:
            return self._transport_failure(ErrorKind.TIMEOUT, error)
        except httpx.RequestError as error:
            return self._transport_failure(ErrorKind.NETWORK, error)

        body = response.text
        if 200 <= response.status_code < 300:
            return ProviderResult(
                provider=_PROVIDER_NAME,
                provider_status=response.status_code,
                error_kind=None,
                error_message=None,
                provider_body=body,
            )
        return ProviderResult(
            provider=_PROVIDER_NAME,
            provider_status=response.status_code,
            error_kind=ErrorKind.HTTP_STATUS,
            error_message=_error_message(body),
            provider_body=body,
        )

    def _form_fields(self, message: ChannelMessage) -> dict[str, str]:
        from_email = str(message.config.get("from", self._from_email))
        bcc_email = message.config.get("bcc", self._bcc_email)
        fields = {
            "from": from_email,
            "to": ", ".join(recipient.address for recipient in message.recipients),
            "subject": message.content.subject or "",
            "text": message.content.body_text,
            "o:tracking": "no",
        }
        if bcc_email:
            fields["bcc"] = str(bcc_email)
        if message.content.body_html is not None:
            fields["html"] = message.content.body_html
        return fields

    def _transport_failure(self, kind: ErrorKind, error: httpx.RequestError) -> ProviderResult:
        return ProviderResult(
            provider=_PROVIDER_NAME,
            provider_status=None,
            error_kind=kind,
            error_message=str(error),
            provider_body="",
        )


def _error_message(body: str) -> str:
    """Mailgun's error body is usually `{"message": ...}` but can be a bare string."""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(parsed, dict):
        message = parsed.get("message")
        if isinstance(message, str):
            return message
    return body
