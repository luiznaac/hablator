"""The registry is keyed by the (channel, provider) pair a config row names."""

from __future__ import annotations

import pytest

from hablator.usecase.channel.model import Channel, ProviderResult
from hablator.usecase.channel.provider import ChannelRegistry, IChannelProvider, OutboundDelivery
from hablator.usecase.commons.exceptions import UnknownProviderError


class StubProvider:
    def __init__(self, channel: Channel) -> None:
        self._channel = channel

    @property
    def channel(self) -> Channel:
        return self._channel

    async def send(self, delivery: OutboundDelivery) -> ProviderResult:
        return ProviderResult(provider="stub", provider_status=200)


def _provider() -> IChannelProvider:
    return StubProvider(Channel.EMAIL)


def test_resolves_a_registered_pair() -> None:
    provider = _provider()
    registry = ChannelRegistry({(Channel.EMAIL, "mailgun"): provider})

    assert registry.resolve(Channel.EMAIL, "mailgun") is provider
    assert registry.is_registered(Channel.EMAIL, "mailgun") is True


def test_rejects_an_unregistered_pair() -> None:
    registry = ChannelRegistry({(Channel.EMAIL, "mailgun"): _provider()})

    with pytest.raises(UnknownProviderError):
        registry.resolve(Channel.PUSH, "ntfy")


def test_rejects_a_provider_registered_for_another_channel() -> None:
    registry = ChannelRegistry({(Channel.EMAIL, "mailgun"): _provider()})

    with pytest.raises(UnknownProviderError):
        registry.resolve(Channel.PUSH, "mailgun")
