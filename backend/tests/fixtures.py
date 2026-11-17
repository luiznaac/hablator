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
from hablator.usecase.notification.model import Attempt, Delivery, Notification

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

    async def update_delivery(self, delivery: Delivery) -> None:
        assert delivery.id is not None
        self.deliveries[delivery.id] = delivery

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


_HUB_TABLES = ("attempt", "delivery", "notification", "provider_config", "retry_policy")


async def clear_hub_tables(engine: AsyncEngine) -> None:
    """Empty the hub tables between integration tests (child tables first)."""
    async with engine.begin() as connection:
        for table in _HUB_TABLES:
            await connection.execute(text(f"DELETE FROM {table}"))
