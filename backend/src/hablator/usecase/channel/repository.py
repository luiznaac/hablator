"""Outbound ports for the channel slice's own persistence."""

from __future__ import annotations

from typing import Protocol

from hablator.usecase.channel.model import Channel, ProviderConfig, RetryPolicy


class IProviderConfigRepository(Protocol):
    async def get(self, channel: Channel) -> ProviderConfig | None: ...

    async def upsert(self, config: ProviderConfig) -> ProviderConfig: ...

    async def delete(self, channel: Channel) -> None: ...


class IRetryPolicyRepository(Protocol):
    async def get(self, channel: Channel) -> RetryPolicy | None: ...

    async def upsert(self, policy: RetryPolicy) -> RetryPolicy: ...
