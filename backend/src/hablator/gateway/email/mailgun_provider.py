"""Mailgun v3 email provider — the only email adapter in this phase.

One `send` is one Mailgun call with every recipient comma-joined in `to`. It normalizes the
response into a `ProviderResult` and never decides retriability. The non-secret `from`/`bcc`
come from provider config, with the env-backed defaults as the fallback.
"""

from __future__ import annotations

import base64
from dataclasses import replace

import httpx

from hablator.gateway.configuration.provider_response import provider_result, transport_failure
from hablator.usecase.channel.model import (
    MAX_RECIPIENTS,
    Channel,
    ChannelMessage,
    ErrorKind,
    ProviderConfigMapping,
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

    def validate_config(self, config: ProviderConfigMapping) -> ProviderConfigMapping:
        """Validate and normalize an email provider config before it is stored.

        Raises:
            DomainError: on an unknown key, a missing `from`, or a malformed `bcc`/`recipients`.
        """
        unknown = sorted(set(config) - _CONFIG_KEYS)
        if unknown:
            raise DomainError(f"unknown email provider config key: '{unknown[0]}'")
        sender = config.get("from")
        if not isinstance(sender, str) or not sender.strip():
            raise DomainError("email provider config requires a non-empty 'from' address")
        normalized: dict[str, object] = {"from": sender.strip()}
        if "bcc" in config:
            bcc = config["bcc"]
            if not isinstance(bcc, str) or not bcc.strip():
                raise DomainError("email provider config 'bcc' must be a non-empty address")
            normalized["bcc"] = bcc.strip()
        if "recipients" in config:
            normalized["recipients"] = _validated_recipients(config["recipients"])
        return normalized

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
            return transport_failure(_PROVIDER_NAME, ErrorKind.TIMEOUT, error)
        except httpx.RequestError as error:
            return transport_failure(_PROVIDER_NAME, ErrorKind.NETWORK, error)

        return provider_result(_PROVIDER_NAME, response)

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


def _validated_recipients(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DomainError("email provider config 'recipients' must be a non-empty list of addresses")
    if not all(isinstance(address, str) and address.strip() for address in value):
        raise DomainError("email provider config 'recipients' must be a non-empty list of addresses")
    if len(value) > MAX_RECIPIENTS:
        raise DomainError(f"email provider config allows at most {MAX_RECIPIENTS} recipients, got {len(value)}")
    return [str(address).strip() for address in value]


def _config_recipients(config: ProviderConfigMapping) -> tuple[Recipient, ...]:
    configured = config.get("recipients")
    if not isinstance(configured, list):
        return ()
    return tuple(Recipient(str(address)) for address in configured if str(address))
