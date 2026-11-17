"""Outbound ports for the channel slice: the provider contract and the provider-config reader."""

from __future__ import annotations

from typing import Protocol

from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    ProviderConfig,
    ProviderResult,
    RetryPolicy,
)


class IChannelProvider(Protocol):
    """One concrete provider for one channel. Adapters normalize; they never decide retriability.

    `prepare` is the adapter's own validation seam: it fills the channel's defaults (an email
    delivery may take its recipients from provider config) and rejects a request the channel
    cannot carry, before anything is persisted.
    """

    channel: Channel
    name: str

    def prepare(self, message: ChannelMessage) -> ChannelMessage: ...

    async def send(self, message: ChannelMessage) -> ProviderResult: ...


class IProviderConfigRepository(Protocol):
    """Reads and writes a channel's non-secret provider config; `None` means unconfigured."""

    async def get(self, channel: Channel) -> ProviderConfig | None: ...

    async def upsert(self, config: ProviderConfig) -> ProviderConfig: ...

    async def delete(self, channel: Channel) -> None: ...


class IRetryPolicyRepository(Protocol):
    """Reads and writes a channel's retry policy. Modeled now, unused in v1."""

    async def get(self, channel: Channel) -> RetryPolicy | None: ...

    async def upsert(self, policy: RetryPolicy) -> RetryPolicy: ...
