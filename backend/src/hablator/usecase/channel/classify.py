"""The one place retriability is decided.

An adapter only normalizes a provider response into `ErrorKind` + status; whether a failure is
worth another attempt is a core rule.
"""

from __future__ import annotations

from hablator.usecase.channel.model import ErrorKind, ProviderResult

_RETRIABLE_ERROR_KINDS = frozenset({ErrorKind.TIMEOUT, ErrorKind.NETWORK})
_RETRIABLE_STATUSES = frozenset({420, 429})


def classify(result: ProviderResult) -> bool:
    """Return whether a failed attempt may produce another attempt."""
    if result.error_kind in _RETRIABLE_ERROR_KINDS:
        return True
    status = result.provider_status
    if status is None:
        return False
    return status in _RETRIABLE_STATUSES or status >= 500
