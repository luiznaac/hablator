"""Domain exception hierarchy. Adapters map these to transport errors (HTTP, etc)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every error the core raises deliberately."""


class ResourceNotFoundError(DomainError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} not found: {identifier}")
        self.resource = resource
        self.identifier = identifier


class InvalidArgumentError(DomainError):
    pass


class UnknownProviderError(DomainError):
    """A channel configuration named a provider that is not registered for that channel."""

    def __init__(self, channel: str, provider: str) -> None:
        super().__init__(f"No provider registered for channel={channel!r} provider={provider!r}")
        self.channel = channel
        self.provider = provider


class InvalidTransitionError(DomainError):
    """A delivery status move the lifecycle does not allow."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot transition a delivery from {current!r} to {target!r}")
        self.current = current
        self.target = target
