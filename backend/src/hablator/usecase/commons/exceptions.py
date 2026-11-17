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


class UnauthorizedError(DomainError):
    """A missing or invalid API credential."""


class PayloadTooLargeError(DomainError):
    """The request body exceeds the API's size guard."""


class UnsupportedMediaTypeError(DomainError):
    """The request body is not JSON."""


class PersistenceInvariantError(DomainError):
    """A persisted entity came back without its id — a bug, answered as an internal error."""


def require_id(value: int | None, entity: str) -> int:
    """Return a persisted entity's id, or fail loudly when the persistence invariant broke.

    Raises:
        PersistenceInvariantError: when `value` is `None`.
    """
    if value is None:
        raise PersistenceInvariantError(f"{entity} was persisted without an id")
    return value


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
