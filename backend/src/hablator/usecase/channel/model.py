"""Channel-agnostic values: a delivery payload every provider understands, and the result
it reports back. Nothing here knows a concrete provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Channel(StrEnum):
    """The delivery medium. SMS and voice exist only in the vocabulary in this phase."""

    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    VOICE = "voice"


class ErrorKind(StrEnum):
    """A provider normalizes its own failure into one of these; the core classifies retriability."""

    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP_STATUS = "http_status"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True, slots=True)
class Content:
    """The content actually sent by a delivery: the channel override or a copy of the base."""

    subject: str | None
    body_text: str
    body_html: str | None = None


@dataclass(frozen=True, slots=True)
class Recipient:
    """A destination address in a channel's own vocabulary (email address, push topic)."""

    address: str


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """The non-secret provider config read from the database on every dispatch."""

    channel: Channel
    provider: str
    config: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """What one provider call reported. `provider_body` is the raw response body the legacy
    `/send-email` contract echoes back to its consumers.
    """

    provider: str
    provider_status: int | None
    error_kind: ErrorKind | None
    error_message: str | None
    provider_body: str = ""

    @property
    def is_success(self) -> bool:
        return self.error_kind is None


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    """The channel-agnostic input a provider receives: recipients, resolved content, options and
    the non-secret provider config. Kept here (not `notification.Delivery`) so the slice DAG
    `delivery -> notification -> channel` stays acyclic.
    """

    channel: Channel
    recipients: tuple[Recipient, ...]
    content: Content
    options: Mapping[str, object]
    config: Mapping[str, object]
