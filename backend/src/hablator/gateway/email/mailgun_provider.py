"""Mailgun v3 email provider — the only email adapter in this phase.

One `send` is one Mailgun call with every recipient comma-joined in `to`. It normalizes the
response into a `ProviderResult` and never decides retriability. The non-secret `from`/`bcc`
come from provider config, with the env-backed defaults as the fallback.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import replace

import httpx

from hablator.usecase.channel.model import (
    MAX_RECIPIENTS,
    Channel,
    ChannelMessage,
    ErrorKind,
    ProviderResult,
    Recipient,
)
from hablator.usecase.commons.exceptions import DomainError

_PROVIDER_NAME = "mailgun"
_CONFIG_KEYS = frozenset({"from", "bcc", "recipients"})


class MailgunEmailProvider:
    channel = Channel.EMAIL
    name = _PROVIDER_NAME

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_url: str,
        api_key: str,
        from_email: str,
        bcc_email: str,
    ) -> None:
        self._http_client = http_client
        self._api_url = api_url
        self._api_key = api_key
        self._from_email = from_email
        self._bcc_email = bcc_email

    def prepare(self, message: ChannelMessage) -> ChannelMessage:
        """Validate the email request and fill its recipient default from provider config.

        Email takes no per-delivery options in v1 (`from`/`bcc` are provider config). A request
        without recipients falls back to the provider config's `recipients` list.

        Raises:
            DomainError: on any email option, or when no recipient exists either way.
        """
        if message.options:
            raise DomainError(f"email takes no delivery options, got {sorted(message.options)}")

        unknown = set(message.config) - _CONFIG_KEYS
        if unknown:
            raise DomainError(f"unknown email provider config keys: {sorted(unknown)}")

        recipients = message.recipients or _config_recipients(message.config)
        if not recipients:
            raise DomainError("email requires at least one recipient (request or provider-config default)")
        if len(recipients) > MAX_RECIPIENTS:
            raise DomainError(f"email allows at most {MAX_RECIPIENTS} recipients, got {len(recipients)}")
        return replace(message, recipients=recipients)

    async def send(self, message: ChannelMessage) -> ProviderResult:
        data = self._form_fields(message)
        authorization = base64.b64encode(f"api:{self._api_key}".encode()).decode()

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
            "o:tracking": "no",
        }
        if bcc_email:
            fields["bcc"] = str(bcc_email)
        if message.content.body_html is not None:
            fields["html"] = message.content.body_html
        if message.content.body_text:
            fields["text"] = message.content.body_text
        elif message.content.body_html is None:
            fields["text"] = ""
        return fields

    def _transport_failure(self, kind: ErrorKind, error: httpx.RequestError) -> ProviderResult:
        return ProviderResult(
            provider=_PROVIDER_NAME,
            provider_status=None,
            error_kind=kind,
            error_message=str(error),
            provider_body="",
        )


def _config_recipients(config: Mapping[str, object]) -> tuple[Recipient, ...]:
    configured = config.get("recipients")
    if not isinstance(configured, list):
        return ()
    return tuple(Recipient(str(address)) for address in configured if str(address))


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
