"""ntfy push provider — the only push adapter in this phase.

One `send` is one JSON publish to the ntfy server root with the admin Bearer token. The topic is
fixed by provider config (a request cannot choose one), the subject maps to `title`, the body to
`message`, and `priority`/`tags`/`click` are the only per-delivery options. It normalizes the
response into a `ProviderResult` and never decides retriability.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from dataclasses import replace

import httpx

from hablator.gateway.configuration.provider_response import provider_result, transport_failure
from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    ErrorKind,
    ProviderConfigMapping,
    ProviderResult,
    Recipient,
)
from hablator.usecase.commons.exceptions import DomainError

_PROVIDER_NAME = "ntfy"
_CONFIG_KEYS = frozenset({"topic", "default_priority"})
_OPTION_KEYS = frozenset({"priority", "tags", "click"})
_MAX_TITLE_BYTES = 1024
_MAX_MESSAGE_BYTES = 4096
_DEFAULT_PRIORITY = 3
_PRIORITY_ALIASES = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}
_PRIORITY_MESSAGE = "priority must be 1-5 or one of min|low|default|high|urgent"


class NtfyPushProvider:
    channel = Channel.PUSH
    name = _PROVIDER_NAME

    def __init__(self, http_client: httpx.AsyncClient, *, base_url: str, token: str) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._token = token

    def validate_config(self, config: ProviderConfigMapping) -> ProviderConfigMapping:
        """Validate and normalize a push provider config before it is stored.

        Raises:
            DomainError: on an unknown key, a missing topic, or a `default_priority` outside 1-5.
        """
        unknown = sorted(set(config) - _CONFIG_KEYS)
        if unknown:
            raise DomainError(f"unknown push provider config key: '{unknown[0]}'")
        normalized: dict[str, object] = {"topic": _topic(config)}
        if "default_priority" in config:
            normalized["default_priority"] = _config_priority(config["default_priority"])
        return normalized

    def prepare(self, message: ChannelMessage) -> ChannelMessage:
        """Validate a push request and fill its single recipient from the configured topic.

        Raises:
            DomainError: when the request carries recipients, the config has no topic, the
                content exceeds its cap, or an option is invalid.
        """
        if message.recipients:
            raise DomainError("push does not accept recipients; the topic comes from provider config")
        topic = _topic(message.config)
        _cap_bytes(message.content.subject or "", _MAX_TITLE_BYTES, "title")
        _cap_bytes(message.content.body_text, _MAX_MESSAGE_BYTES, "message")
        options = _resolve_options(message.options, message.config)
        return replace(message, recipients=(Recipient(topic),), options=options)

    async def send(self, message: ChannelMessage) -> ProviderResult:
        payload = self._payload(message)
        try:
            response = await self._http_client.post(
                self._base_url,
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
                follow_redirects=False,
            )
        except httpx.TimeoutException as error:
            return transport_failure(_PROVIDER_NAME, ErrorKind.TIMEOUT, error)
        except httpx.RequestError as error:
            return transport_failure(_PROVIDER_NAME, ErrorKind.NETWORK, error)

        return provider_result(_PROVIDER_NAME, response, error_keys=("error", "message"))

    def _payload(self, message: ChannelMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "topic": _topic(message.config),
            "message": message.content.body_text,
        }
        if message.content.subject:
            payload["title"] = message.content.subject
        priority = message.options.get("priority")
        if priority is not None:
            payload["priority"] = normalize_priority(priority)
        tags = message.options.get("tags")
        if tags is not None:
            payload["tags"] = _validated_tags(tags)
        click = message.options.get("click")
        if click is not None:
            payload["click"] = _validated_click(click)
        return payload


def normalize_priority(value: object) -> int:
    """Normalize a priority integer or alias to 1-5.

    Raises:
        DomainError: when the value is neither an integer 1-5 nor a known alias.
    """
    if isinstance(value, bool):
        raise DomainError(_PRIORITY_MESSAGE)
    if isinstance(value, int):
        priority = value
    elif isinstance(value, str) and value.strip().lower() in _PRIORITY_ALIASES:
        priority = _PRIORITY_ALIASES[value.strip().lower()]
    else:
        raise DomainError(_PRIORITY_MESSAGE)
    if not 1 <= priority <= 5:
        raise DomainError(_PRIORITY_MESSAGE)
    return priority


def _config_priority(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise DomainError("push provider config 'default_priority' must be an integer 1-5")
    return value


def _resolve_options(options: Mapping[str, object], config: ProviderConfigMapping) -> dict[str, object]:
    unknown = sorted(set(options) - _OPTION_KEYS)
    if unknown:
        raise DomainError(f"unknown push option: '{unknown[0]}'")
    default_priority = config.get("default_priority", _DEFAULT_PRIORITY)
    resolved: dict[str, object] = {"priority": normalize_priority(options.get("priority", default_priority))}
    if "tags" in options:
        resolved["tags"] = _validated_tags(options["tags"])
    if "click" in options:
        resolved["click"] = _validated_click(options["click"])
    return resolved


def _validated_tags(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)) or not value:
        raise DomainError("push option 'tags' must be a non-empty list of strings")
    if not all(isinstance(tag, str) and tag.strip() for tag in value):
        raise DomainError("push option 'tags' must be a non-empty list of strings")
    return [str(tag).strip() for tag in value]


def _validated_click(value: object) -> str:
    if not isinstance(value, str) or not _is_absolute_http(value):
        raise DomainError("push option 'click' must be an absolute http(s) URL")
    return value


def _is_absolute_http(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _topic(config: ProviderConfigMapping) -> str:
    topic = config.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise DomainError("push provider config requires a non-empty 'topic'")
    return topic.strip()


def _cap_bytes(value: str, limit: int, label: str) -> None:
    if len(value.encode("utf-8")) > limit:
        raise DomainError(f"push {label} exceeds {limit} bytes")
