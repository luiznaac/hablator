"""The one channel port and the registry keyed by `(channel, provider)`.

`IChannelProvider.send` receives an `OutboundDelivery` — the narrow view of a delivery a
provider needs — rather than the notification slice's `Delivery`, which satisfies it
structurally. That keeps the usecase slice DAG `delivery -> notification -> channel`
acyclic: the channel slice never imports a delivery or a notification.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from hablator.usecase.channel.model import Channel, Content, ProviderResult, Recipient
from hablator.usecase.commons.exceptions import UnknownProviderError


class OutboundDelivery(Protocol):
    """What a provider may read from the delivery it sends."""

    @property
    def channel(self) -> Channel: ...

    @property
    def recipients(self) -> Sequence[Recipient]: ...

    @property
    def content(self) -> Content: ...

    @property
    def options(self) -> Mapping[str, object]: ...


class IChannelProvider(Protocol):
    """One adapter for one channel/provider pair. Adapters normalize, never classify retriability."""

    @property
    def channel(self) -> Channel: ...

    async def send(self, delivery: OutboundDelivery) -> ProviderResult: ...


class ChannelRegistry:
    """Resolves the provider a channel's configuration names; an unregistered pair is rejected."""

    def __init__(self, providers: Mapping[tuple[Channel, str], IChannelProvider]) -> None:
        self._providers = dict(providers)

    def resolve(self, channel: Channel, provider: str) -> IChannelProvider:
        try:
            return self._providers[(channel, provider)]
        except KeyError:
            raise UnknownProviderError(channel.value, provider) from None

    def is_registered(self, channel: Channel, provider: str) -> bool:
        return (channel, provider) in self._providers
