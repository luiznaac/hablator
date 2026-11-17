"""The retriability table is the one place a failure is classified — adapters never decide."""

from __future__ import annotations

import pytest

from hablator.usecase.channel.model import ErrorKind
from hablator.usecase.channel.retriability import is_retriable


@pytest.mark.parametrize(
    ("error_kind", "provider_status", "expected"),
    [
        (ErrorKind.TIMEOUT, None, True),
        (ErrorKind.NETWORK, None, True),
        (ErrorKind.HTTP_STATUS, 420, True),
        (ErrorKind.HTTP_STATUS, 429, True),
        (ErrorKind.HTTP_STATUS, 500, True),
        (ErrorKind.HTTP_STATUS, 503, True),
        (ErrorKind.HTTP_STATUS, 400, False),
        (ErrorKind.HTTP_STATUS, 401, False),
        (ErrorKind.HTTP_STATUS, 404, False),
        (ErrorKind.UNEXPECTED, None, False),
        (ErrorKind.UNEXPECTED, 500, True),
        (None, None, False),
        (None, 200, False),
    ],
)
def test_retriability_table(error_kind: ErrorKind | None, provider_status: int | None, expected: bool) -> None:
    assert is_retriable(error_kind, provider_status) is expected
