"""Attempt instruments and events — never subject, body or recipient.

The adapter is silent; the dispatcher owns this telemetry and reports it here.
"""

from __future__ import annotations

from opentelemetry.metrics import Meter

from hablator.usecase.channel.model import Channel, ErrorKind
from hablator.usecase.commons.logging import get_logger

_MISCONFIGURED_STATUSES = frozenset({401, 403})


class AttemptTelemetry:
    def __init__(self, meter: Meter) -> None:
        self._attempts = meter.create_counter(
            "notification.attempts",
            unit="{attempt}",
            description="The number of delivery attempts, by channel, provider and outcome.",
        )
        self._duration = meter.create_histogram(
            "notification.attempt.duration",
            unit="s",
            description="The duration of a delivery attempt, by channel, provider and outcome.",
        )
        self._log = get_logger(__name__)

    def record(
        self,
        *,
        channel: Channel,
        provider: str,
        succeeded: bool,
        retriable: bool,
        provider_status: int | None,
        error_kind: ErrorKind | None,
        delivery_id: int | None,
        attempt_number: int,
        duration_seconds: float,
    ) -> None:
        outcome = "succeeded" if succeeded else "failed"
        self._attempts.add(
            1,
            {
                "channel": str(channel),
                "provider": provider,
                "outcome": outcome,
                "retriable": retriable,
            },
        )
        self._duration.record(
            duration_seconds,
            {
                "channel": str(channel),
                "provider": provider,
                "outcome": outcome,
            },
        )

        event = "channel.attempt.succeeded" if succeeded else "channel.attempt.failed"
        log_attributes: dict[str, object] = {
            "channel": str(channel),
            "provider": provider,
            "provider.status": provider_status,
            "error.kind": str(error_kind) if error_kind is not None else None,
            "delivery.id": delivery_id,
            "attempt.number": attempt_number,
            "duration": duration_seconds,
        }
        if succeeded:
            self._log.info(event, **log_attributes)
        elif provider_status in _MISCONFIGURED_STATUSES:
            # 401/403 is a broken credential or account, not a transient provider problem.
            self._log.error(event, **log_attributes)
        else:
            self._log.warning(event, **log_attributes)
