"""Outbound ports for the channel slice: the provider contract and the provider-config reader."""

from __future__ import annotations

from typing import Protocol

from hablator.usecase.channel.model import Channel, ChannelMessage, ProviderConfig, ProviderResult


class IChannelProvider(Protocol):
    """One concrete provider for one channel. Adapters normalize; they never decide retriability."""

    channel: Channel
    name: str

    async def send(self, message: ChannelMessage) -> ProviderResult: ...


class IProviderConfigRepository(Protocol):
    """Reads a channel's non-secret provider config; `None` means the channel is unconfigured."""

    async def get(self, channel: Channel) -> ProviderConfig | None: ...
