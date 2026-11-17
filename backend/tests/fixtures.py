"""Shared test builders — one stub checker and one metric/log reader per shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, TypeVar

from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from hablator.application.settings import Settings
from hablator.application.telemetry import Telemetry
from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    ErrorKind,
    ProviderConfig,
    ProviderResult,
)
from hablator.usecase.health.checker import HealthCheckResult
from hablator.usecase.notification.model import Attempt, Delivery, DeliveryDetail, Notification, NotificationDetail

_T = TypeVar("_T")


class StubHealthChecker:
    def __init__(self, service_name: str = "app-health", *, is_healthy: bool = True) -> None:
        self._service_name = service_name
        self._is_healthy = is_healthy

    async def get_health_status(self) -> HealthCheckResult:
        return HealthCheckResult(
            service_name=self._service_name,
            is_healthy=self._is_healthy,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )


def build_test_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, app_env="test", **overrides)  # type: ignore[arg-type]


def log_records(telemetry: Telemetry) -> list[ReadableLogRecord]:
    exporter = telemetry.log_exporter
    assert isinstance(exporter, InMemoryLogRecordExporter)
    return list(exporter.get_finished_logs())


def new_log_records(telemetry: Telemetry, start: int) -> list[ReadableLogRecord]:
    return log_records(telemetry)[start:]


def metrics_by_name(telemetry: Telemetry) -> dict[str, Any]:
    reader = telemetry.metric_reader
    assert isinstance(reader, InMemoryMetricReader)
    data = reader.get_metrics_data()
    return {
        metric.name: metric
        for resource_metric in data.resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
    }


def metric_names(telemetry: Telemetry) -> set[str]:
    return set(metrics_by_name(telemetry))


def metric(telemetry: Telemetry, name: str) -> Any:
    metrics = metrics_by_name(telemetry)
    assert name in metrics, f"metric {name} not exported"
    return metrics[name]


class InlineTransaction:
    """Runs each block immediately and records whether a transaction is active."""

    def __init__(self) -> None:
        self._depth = 0

    async def execute(self, block: Callable[[], Awaitable[_T]]) -> _T:
        self._depth += 1
        try:
            return await block()
        finally:
            self._depth -= 1

    @property
    def active(self) -> bool:
        return self._depth > 0


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[int, Notification] = {}
        self.deliveries: dict[int, Delivery] = {}
        self.attempts: list[Attempt] = []
        self._next_notification_id = 1
        self._next_delivery_id = 1
        self._next_attempt_id = 1

    async def create(
        self, notification: Notification, deliveries: Sequence[Delivery]
    ) -> tuple[Notification, list[Delivery]]:
        notification_id = self._next_notification_id
        self._next_notification_id += 1
        stored_notification = replace(notification, id=notification_id)
        self.notifications[notification_id] = stored_notification

        stored_deliveries: list[Delivery] = []
        for delivery in deliveries:
            delivery_id = self._next_delivery_id
            self._next_delivery_id += 1
            stored = replace(delivery, id=delivery_id, notification_id=notification_id)
            self.deliveries[delivery_id] = stored
            stored_deliveries.append(stored)
        return stored_notification, stored_deliveries

    async def get(self, notification_id: int) -> NotificationDetail | None:
        notification = self.notifications.get(notification_id)
        if notification is None:
            return None
        details = tuple(
            DeliveryDetail(
                delivery=delivery,
                attempts=tuple(attempt for attempt in self.attempts if attempt.delivery_id == delivery.id),
            )
            for delivery in self.deliveries.values()
            if delivery.notification_id == notification_id
        )
        return NotificationDetail(notification=notification, deliveries=details)

    async def get_delivery(self, delivery_id: int) -> DeliveryDetail | None:
        delivery = self.deliveries.get(delivery_id)
        if delivery is None:
            return None
        return DeliveryDetail(
            delivery=delivery,
            attempts=tuple(attempt for attempt in self.attempts if attempt.delivery_id == delivery_id),
        )

    async def update_delivery(self, delivery: Delivery) -> None:
        assert delivery.id is not None
        self.deliveries[delivery.id] = delivery

    async def next_attempt_number(self, delivery_id: int) -> int:
        numbers = [attempt.attempt_number for attempt in self.attempts if attempt.delivery_id == delivery_id]
        return max(numbers, default=0) + 1

    async def add_attempt(self, attempt: Attempt) -> Attempt:
        attempt_id = self._next_attempt_id
        self._next_attempt_id += 1
        stored = replace(attempt, id=attempt_id)
        self.attempts.append(stored)
        return stored


class InMemoryProviderConfigRepository:
    def __init__(self, configs: Mapping[Channel, ProviderConfig] | None = None) -> None:
        self._configs = dict(configs or {})

    async def get(self, channel: Channel) -> ProviderConfig | None:
        return self._configs.get(channel)

    async def upsert(self, config: ProviderConfig) -> ProviderConfig:
        self._configs[config.channel] = config
        return config

    async def delete(self, channel: Channel) -> None:
        self._configs.pop(channel, None)


class FakeChannelProvider:
    """A provider that reports a fixed result (or raises) and records what it was sent."""

    def __init__(
        self,
        *,
        name: str = "mailgun",
        channel: Channel = Channel.EMAIL,
        result: ProviderResult | None = None,
        exception: Exception | None = None,
        hook: Callable[[], None] | None = None,
    ) -> None:
        self.name = name
        self.channel = channel
        self.result = result or ProviderResult(
            provider=name,
            provider_status=200,
            error_kind=None,
            error_message=None,
            provider_body="queued",
        )
        self.exception = exception
        self.hook = hook
        self.sent: list[ChannelMessage] = []

    def prepare(self, message: ChannelMessage) -> ChannelMessage:
        return message

    def validate_config(self, config: Mapping[str, object]) -> Mapping[str, object]:
        return dict(config)

    async def send(self, message: ChannelMessage) -> ProviderResult:
        if self.hook is not None:
            self.hook()
        self.sent.append(message)
        if self.exception is not None:
            raise self.exception
        return self.result


def failing_result(status: int = 500, *, error_kind: ErrorKind = ErrorKind.HTTP_STATUS) -> ProviderResult:
    return ProviderResult(
        provider="mailgun",
        provider_status=status,
        error_kind=error_kind,
        error_message="provider failed",
        provider_body="provider failed",
    )


API_TOKEN = "dev-hablator-api-token"
API_AUTH = {"Authorization": f"Bearer {API_TOKEN}"}

_HUB_TABLES = ("attempt", "delivery", "notification", "provider_config", "retry_policy")


async def insert_notification(
    engine: AsyncEngine,
    *,
    created_at: datetime,
    source: str | None = "valoab",
    subject: str = "Backup finished",
    deliveries: Sequence[tuple[str, str]] = (("email", "succeeded"),),
) -> tuple[int, list[int]]:
    """Insert a notification and its deliveries directly, returning their ids.

    Lets a test control `created_at` and every delivery status; everything else is written through
    the API. `deliveries` is a sequence of `(channel, status)` pairs.
    """
    async with engine.begin() as connection:
        result = await connection.execute(
            text(
                "INSERT INTO notification (source, subject, body_text, created_at) "
                "VALUES (:source, :subject, 'body', :created_at)"
            ),
            {"source": source, "subject": subject, "created_at": created_at},
        )
        notification_id = int(result.lastrowid or 0)
        delivery_ids: list[int] = []
        for channel, status in deliveries:
            inserted = await connection.execute(
                text(
                    "INSERT INTO delivery "
                    "(notification_id, channel, status, recipients, subject, body_text, created_at, updated_at) "
                    "VALUES (:notification_id, :channel, :status, :recipients, :subject, 'body', "
                    ":created_at, :created_at)"
                ),
                {
                    "notification_id": notification_id,
                    "channel": channel,
                    "status": status,
                    "recipients": '["ops@example.com"]',
                    "subject": subject,
                    "created_at": created_at,
                },
            )
            delivery_ids.append(int(inserted.lastrowid or 0))
    return notification_id, delivery_ids


async def clear_hub_tables(engine: AsyncEngine) -> None:
    """Empty the hub tables between integration tests (child tables first)."""
    async with engine.begin() as connection:
        for table in _HUB_TABLES:
            await connection.execute(text(f"DELETE FROM {table}"))
