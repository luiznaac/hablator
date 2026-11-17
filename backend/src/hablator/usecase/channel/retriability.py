"""The single retriability classification. No adapter decides this."""

from __future__ import annotations

from hablator.usecase.channel.model import ErrorKind

_RETRIABLE_KINDS = frozenset({ErrorKind.TIMEOUT, ErrorKind.NETWORK})
_RETRIABLE_STATUSES = frozenset({420, 429})


def is_retriable(error_kind: ErrorKind | None, provider_status: int | None) -> bool:
    """Classify one failed attempt: transient timeout/network, provider rate limit, or 5xx."""
    if error_kind in _RETRIABLE_KINDS:
        return True
    if provider_status in _RETRIABLE_STATUSES:
        return True
    return provider_status is not None and provider_status >= 500
