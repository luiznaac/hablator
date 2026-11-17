"""Which provider serves a channel when no `provider_config` row names one.

One table for both consumers — the notification service (validation, before anything is written)
and the delivery dispatcher (the actual call) — so the two can never disagree.
"""

from __future__ import annotations

from hablator.usecase.channel.model import Channel, ProviderConfig
from hablator.usecase.channel.ports import IChannelProvider
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.exceptions import DomainError

DEFAULT_PROVIDERS: dict[Channel, str] = {Channel.EMAIL: "mailgun"}


def provider_name_for(channel: Channel, config: ProviderConfig | None) -> str | None:
    """The active provider name: the config row's, else the channel's bootstrap default."""
    if config is not None:
        return config.provider
    return DEFAULT_PROVIDERS.get(channel)


def config_mapping(config: ProviderConfig | None) -> dict[str, object]:
    """The non-secret config a provider receives; empty when the channel is unconfigured."""
    return dict(config.config) if config is not None else {}


def resolve_provider(
    registry: ChannelRegistry,
    channel: Channel,
    config: ProviderConfig | None,
) -> tuple[IChannelProvider, dict[str, object]]:
    """Resolve a channel's provider and its non-secret config, or reject the channel.

    Raises:
        DomainError: when no provider is registered for the channel's active provider name.
    """
    provider_name = provider_name_for(channel, config)
    provider = registry.get(channel, provider_name) if provider_name is not None else None
    if provider is None:
        raise DomainError(f"Channel '{channel}' has no registered provider")
    return provider, config_mapping(config)
