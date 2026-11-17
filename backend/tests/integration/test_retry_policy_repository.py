"""Retry-policy repository against real MySQL: modeled now, unused in v1."""

from __future__ import annotations

from datetime import datetime

from hablator.application.container import Container
from hablator.usecase.channel.model import Channel, RetryPolicy
from tests.fixtures import LATER, NOW


def _policy(max_attempts: int = 3, *, updated_at: datetime = NOW) -> RetryPolicy:
    return RetryPolicy(
        channel=Channel.EMAIL,
        max_attempts=max_attempts,
        backoff_seconds=(30, 120, 600),
        updated_at=updated_at,
    )


async def test_get_returns_none_for_an_unconfigured_channel(repositories: Container) -> None:
    assert await repositories.retry_policy_repository.get(Channel.EMAIL) is None


async def test_upsert_creates_then_reads_back(repositories: Container) -> None:
    saved = await repositories.retry_policy_repository.upsert(_policy())

    assert saved == _policy()
    assert await repositories.retry_policy_repository.get(Channel.EMAIL) == _policy()


async def test_upsert_replaces_the_policy(repositories: Container) -> None:
    await repositories.retry_policy_repository.upsert(_policy())

    await repositories.retry_policy_repository.upsert(_policy(5, updated_at=LATER))

    stored = await repositories.retry_policy_repository.get(Channel.EMAIL)
    assert stored is not None
    assert stored.max_attempts == 5
    assert stored.backoff_seconds == (30, 120, 600)
    assert stored.updated_at == LATER
