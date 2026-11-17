"""Shared test builders — one stub checker, one metric/log reader and the hub's builders per shape."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from hablator.application.container import Container
from hablator.application.settings import Settings
from hablator.application.telemetry import Telemetry
from hablator.usecase.channel.model import Channel, Content, ErrorKind, Recipient
from hablator.usecase.health.checker import HealthCheckResult
from hablator.usecase.notification.model import (
    Attempt,
    AttemptOutcome,
    NewDelivery,
    NewNotification,
    Notification,
)

NOW = datetime(2026, 11, 16, 22, 41, 3, 123456, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


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


def new_notification(
    source: str | None = "valoab",
    channels: tuple[Channel, ...] = (Channel.EMAIL,),
) -> NewNotification:
    return NewNotification(
        source=source,
        content=Content(subject="Backup finished", body="plain text", body_html="<p>rich</p>"),
        deliveries=tuple(
            NewDelivery(
                channel=channel,
                recipients=(Recipient("ops@example.com"),),
                content=Content(subject=f"{channel.value} subject", body="done"),
                options={},
            )
            for channel in channels
        ),
    )


async def create_notification(
    container: Container,
    *,
    source: str | None = "valoab",
    channels: tuple[Channel, ...] = (Channel.EMAIL,),
    now: datetime = NOW,
) -> Notification:
    return await container.notification_repository.create(new_notification(source, channels), now=now)


def attempt(
    number: int = 1,
    *,
    outcome: AttemptOutcome = AttemptOutcome.SUCCEEDED,
    finished_at: datetime = NOW,
) -> Attempt:
    succeeded = outcome is AttemptOutcome.SUCCEEDED
    return Attempt(
        attempt_number=number,
        outcome=outcome,
        provider="mailgun",
        provider_status=200 if succeeded else 503,
        error_kind=None if succeeded else ErrorKind.HTTP_STATUS,
        error_message=None if succeeded else "service unavailable",
        retriable=not succeeded,
        started_at=NOW,
        finished_at=finished_at,
    )
