"""Attempt instruments and events: the spec's attributes, and never subject, body or recipient."""

from __future__ import annotations

import pytest

from hablator.application.telemetry import Telemetry
from hablator.usecase.channel.model import Channel, ErrorKind
from hablator.usecase.channel.telemetry import AttemptTelemetry
from tests.fixtures import log_records, metric

_CONTENT_ATTRIBUTES = {"subject", "body", "body_html", "recipients", "recipient", "to"}


def _record(telemetry: Telemetry, *, succeeded: bool, status: int | None, kind: ErrorKind | None) -> None:
    AttemptTelemetry(telemetry.meter).record(
        channel=Channel.EMAIL,
        provider="mailgun",
        succeeded=succeeded,
        retriable=not succeeded and status in {420, 429, 500},
        provider_status=status,
        error_kind=kind,
        delivery_id=77,
        attempt_number=1,
        duration_seconds=0.25,
    )


def test_the_counter_and_histogram_carry_the_spec_attributes(telemetry: Telemetry) -> None:
    _record(telemetry, succeeded=True, status=200, kind=None)

    counter = metric(telemetry, "notification.attempts")
    point = counter.data.data_points[0]
    assert point.value == 1
    assert point.attributes == {
        "channel": "email",
        "provider": "mailgun",
        "outcome": "succeeded",
        "retriable": False,
    }

    histogram = metric(telemetry, "notification.attempt.duration")
    assert histogram.unit == "s"
    assert histogram.data.data_points[0].attributes == {
        "channel": "email",
        "provider": "mailgun",
        "outcome": "succeeded",
    }
    assert histogram.data.data_points[0].count == 1


def test_a_success_event_is_logged_without_content(telemetry: Telemetry) -> None:
    _record(telemetry, succeeded=True, status=200, kind=None)

    record = log_records(telemetry)[0].log_record
    assert record.body == "channel.attempt.succeeded"
    assert record.severity_text == "INFO"
    assert record.attributes["delivery.id"] == 77
    assert record.attributes["attempt.number"] == 1
    assert record.attributes["duration"] == 0.25
    assert record.attributes["provider"] == "mailgun"
    assert record.attributes["provider.status"] == 200
    assert _CONTENT_ATTRIBUTES.isdisjoint(record.attributes)


def test_a_failed_event_is_a_warning(telemetry: Telemetry) -> None:
    _record(telemetry, succeeded=False, status=500, kind=ErrorKind.HTTP_STATUS)

    record = log_records(telemetry)[0].log_record
    assert record.body == "channel.attempt.failed"
    assert record.severity_text == "WARN"
    assert record.attributes["error.kind"] == "http_status"


@pytest.mark.parametrize("status", [401, 403])
def test_a_misconfiguration_failure_is_an_error(telemetry: Telemetry, status: int) -> None:
    _record(telemetry, succeeded=False, status=status, kind=ErrorKind.HTTP_STATUS)

    record = log_records(telemetry)[0].log_record
    assert record.body == "channel.attempt.failed"
    assert record.severity_text == "ERROR"
