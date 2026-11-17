"""`ChannelRegistry` — the `(channel, provider name) -> provider instance` map.

Providers are stateless and built once in the composition root; the registry is how dispatch finds
the active one without knowing any concrete class.
"""

from __future__ import annotations

from hablator.usecase.channel.model import Channel
from hablator.usecase.channel.ports import IChannelProvider
from hablator.usecase.commons.exceptions import UnknownProviderError


class ChannelRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[Channel, str], IChannelProvider] = {}

    def register(self, provider: IChannelProvider) -> None:
        self._providers[(provider.channel, provider.name)] = provider

    def get(self, channel: Channel, provider_name: str) -> IChannelProvider | None:
        return self._providers.get((channel, provider_name))

    def resolve(self, channel: Channel, provider_name: str) -> IChannelProvider:
        provider = self.get(channel, provider_name)
        if provider is None:
            raise UnknownProviderError(str(channel), provider_name)
        return provider
