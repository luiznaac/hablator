"""Channel vocabulary and the channel-agnostic values a provider receives."""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


class Channel(enum.StrEnum):
    """The delivery medium. `sms` and `voice` exist only in the vocabulary in v1."""

    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    VOICE = "voice"


class ErrorKind(enum.StrEnum):
    """The narrow failure vocabulary an adapter normalizes a provider response to."""

    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP_STATUS = "http_status"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True, slots=True)
class Content:
    """The content a notification or a delivery carries: subject, plain body, optional HTML."""

    subject: str | None
    body: str
    body_html: str | None = None


@dataclass(frozen=True, slots=True)
class Recipient:
    """An opaque destination address in a channel's own vocabulary."""

    address: str


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """What one provider call returned, normalized by the adapter and classified by the core."""

    provider: str
    provider_status: int | None = None
    error_kind: ErrorKind | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """A result with no normalized error kind means the provider accepted the message."""
        return self.error_kind is None


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """The active provider for one channel and its non-secret configuration."""

    channel: Channel
    provider: str
    config: Mapping[str, object]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """The per-channel retry policy. Modeled now, unused in v1 (chameidor executes retries)."""

    channel: Channel
    max_attempts: int
    backoff_seconds: tuple[int, ...]
    updated_at: datetime
