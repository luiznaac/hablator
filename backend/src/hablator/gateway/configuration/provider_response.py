"""Shared normalization of a provider's HTTP response into the core's `ProviderResult`.

Every channel adapter turns a 2xx into a success and any other status into an `http_status`
failure; transport exceptions become `timeout`/`network`. The adapter never decides retriability —
`usecase.channel.classify` owns that rule.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from hablator.usecase.channel.model import ErrorKind, ProviderResult


def provider_result(
    provider: str,
    response: httpx.Response,
    *,
    error_keys: Sequence[str] = ("message",),
) -> ProviderResult:
    """Normalize one provider response; `error_keys` are the JSON fields that carry its message."""
    body = response.text
    if 200 <= response.status_code < 300:
        return ProviderResult(
            provider=provider,
            provider_status=response.status_code,
            error_kind=None,
            error_message=None,
            provider_body=body,
        )
    return ProviderResult(
        provider=provider,
        provider_status=response.status_code,
        error_kind=ErrorKind.HTTP_STATUS,
        error_message=_error_message(body, error_keys),
        provider_body=body,
    )


def transport_failure(provider: str, kind: ErrorKind, error: httpx.RequestError) -> ProviderResult:
    """Normalize a transport exception into a `ProviderResult` with no provider status."""
    return ProviderResult(
        provider=provider,
        provider_status=None,
        error_kind=kind,
        error_message=str(error),
        provider_body="",
    )


def _error_message(body: str, keys: Sequence[str]) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(parsed, dict):
        for key in keys:
            value = parsed.get(key)
            if isinstance(value, str):
                return value
    return body
