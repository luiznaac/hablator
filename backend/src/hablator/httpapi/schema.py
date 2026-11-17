"""Transport DTOs. Pydantic lives here, at the edge — never in `usecase`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from hablator.usecase.channel.model import MAX_RECIPIENTS, Channel, ChannelConfigView, Content, Recipient
from hablator.usecase.commons.exceptions import require_id
from hablator.usecase.health.checker import HealthCheckResult
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    ChannelRequest,
    Delivery,
    DeliveryStatus,
    NotificationDetail,
    NotificationRequest,
    NotificationStatus,
)

MAX_PART_BYTES = 256 * 1024
MAX_SUBJECT_CHARS = 998
MAX_SOURCE_CHARS = 64
MAX_CHANNELS = 4


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_rfc3339, return_type=str, when_used="json")]


class HealthCheckResponse(BaseModel):
    service_name: str
    is_healthy: bool
    timestamp: datetime

    @classmethod
    def from_domain(cls, result: HealthCheckResult) -> Self:
        return cls(
            service_name=result.service_name,
            is_healthy=result.is_healthy,
            timestamp=result.timestamp,
        )


class ContentDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(max_length=MAX_SUBJECT_CHARS)
    body: str
    body_html: str | None = None

    @field_validator("body", "body_html")
    @classmethod
    def _cap_bytes(cls, value: str | None) -> str | None:
        return _cap_part(value)

    def to_domain(self) -> Content:
        return Content(subject=self.subject, body_text=self.body, body_html=self.body_html)


class ChannelContentDTO(BaseModel):
    """A partial content override merged over the request's base content."""

    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=MAX_SUBJECT_CHARS)
    body: str | None = None
    body_html: str | None = None

    @field_validator("body", "body_html")
    @classmethod
    def _cap_bytes(cls, value: str | None) -> str | None:
        return _cap_part(value)

    def merge_over(self, base: Content) -> Content:
        provided = self.model_fields_set
        subject = self.subject if self.subject is not None else base.subject
        body_text = self.body if self.body is not None else base.body_text
        body_html = self.body_html if "body_html" in provided else base.body_html
        return Content(subject=subject, body_text=body_text, body_html=body_html)


class ChannelRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["email", "push", "sms", "voice"]
    recipients: list[str] | None = Field(default=None, min_length=1, max_length=MAX_RECIPIENTS)
    content: ChannelContentDTO | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("recipients")
    @classmethod
    def _non_empty_addresses(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(not address.strip() for address in value):
            raise ValueError("recipients must be non-empty strings")
        return value

    def to_domain(self, base: Content) -> ChannelRequest:
        return ChannelRequest(
            channel=Channel(self.channel),
            recipients=tuple(Recipient(address) for address in self.recipients or ()),
            content=self.content.merge_over(base) if self.content is not None else None,
            options=dict(self.options),
        )


class NotificationRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, max_length=MAX_SOURCE_CHARS)
    content: ContentDTO
    channels: list[ChannelRequestDTO] = Field(min_length=1, max_length=MAX_CHANNELS)

    def to_domain(self) -> NotificationRequest:
        base = self.content.to_domain()
        return NotificationRequest(
            source=self.source,
            content=base,
            channels=tuple(channel.to_domain(base) for channel in self.channels),
        )


class ContentResponse(BaseModel):
    subject: str | None
    body: str
    body_html: str | None

    @classmethod
    def from_domain(cls, content: Content) -> Self:
        return cls(subject=content.subject, body=content.body_text, body_html=content.body_html)


class AttemptResponse(BaseModel):
    attempt_number: int
    outcome: AttemptOutcome
    provider: str
    provider_status: int | None
    error_kind: str | None
    error_message: str | None
    retriable: bool
    started_at: UtcDateTime
    finished_at: UtcDateTime | None

    @classmethod
    def from_domain(cls, attempt: Attempt) -> Self:
        return cls(
            attempt_number=attempt.attempt_number,
            outcome=attempt.outcome,
            provider=attempt.provider,
            provider_status=attempt.provider_status,
            error_kind=str(attempt.error_kind) if attempt.error_kind is not None else None,
            error_message=attempt.error_message,
            retriable=attempt.retriable,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )


class DeliveryResponse(BaseModel):
    id: int
    channel: Channel
    status: DeliveryStatus
    recipients: list[str]
    content: ContentResponse
    options: dict[str, Any]
    next_attempt_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    attempts: list[AttemptResponse]

    @classmethod
    def from_domain(cls, delivery: Delivery, attempts: tuple[Attempt, ...]) -> Self:
        return cls(
            id=require_id(delivery.id, "delivery"),
            channel=delivery.channel,
            status=delivery.status,
            recipients=[recipient.address for recipient in delivery.recipients],
            content=ContentResponse.from_domain(delivery.content),
            options=dict(delivery.options),
            next_attempt_at=delivery.next_attempt_at,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
            attempts=[AttemptResponse.from_domain(attempt) for attempt in attempts],
        )


class NotificationDetailResponse(BaseModel):
    id: int
    source: str | None
    content: ContentResponse
    status: NotificationStatus
    created_at: UtcDateTime
    deliveries: list[DeliveryResponse]

    @classmethod
    def from_domain(cls, detail: NotificationDetail) -> Self:
        return cls(
            id=require_id(detail.notification.id, "notification"),
            source=detail.notification.source,
            content=ContentResponse.from_domain(detail.notification.content),
            status=detail.status,
            created_at=detail.notification.created_at,
            deliveries=[
                DeliveryResponse.from_domain(delivery.delivery, delivery.attempts) for delivery in detail.deliveries
            ],
        )


class ChannelConfigRequestDTO(BaseModel):
    """The full-replace body of `PUT /channels/{channel}`: the provider and its non-secret config."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    config: dict[str, Any]


class ChannelConfigResponse(BaseModel):
    channel: Channel
    provider: str | None
    configured: bool
    config: dict[str, Any] | None
    updated_at: UtcDateTime | None

    @classmethod
    def from_domain(cls, view: ChannelConfigView) -> Self:
        return cls(
            channel=view.channel,
            provider=view.provider,
            configured=view.configured,
            config=dict(view.config) if view.config is not None else None,
            updated_at=view.updated_at,
        )


def _cap_part(value: str | None) -> str | None:
    if value is not None and len(value.encode("utf-8")) > MAX_PART_BYTES:
        raise ValueError(f"must be at most {MAX_PART_BYTES} bytes")
    return value
