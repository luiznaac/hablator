"""Golden fixtures for the legacy `POST /send-email` contract, pinned at the HTTP boundary.

A stub Mailgun server stands in for the provider; the real app, the real MySQL and the real httpx
stack are exercised. Each case asserts the response bytes and, where it matters, the outgoing form
fields and the recorded history rows.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
from pytest_httpserver import HTTPServer
from sqlalchemy import text
from testcontainers.mysql import MySqlContainer

from hablator.application.container import Container
from hablator.application.settings import Settings
from tests.fixtures import clear_hub_tables

_QUEUED = '{"id": "<20261116.1@hablator.invalid>", "message": "Queued. Thank you."}'
_FROM = "hablator@hablator.invalid"
_BCC = "hablator-archive@hablator.invalid"

_VALID_PAYLOAD = {
    "emails": ["ops@example.com"],
    "subject": "Backup finished",
    "text": "<p>Backup <b>done</b>.</p>",
}


@pytest.fixture
async def legacy_container(mailgun_settings: Settings, migrated_mysql: MySqlContainer) -> AsyncIterator[Container]:
    instance = Container(mailgun_settings)
    try:
        await clear_hub_tables(instance.engine)
        yield instance
    finally:
        await instance.aclose()


@pytest.fixture
async def legacy_client(legacy_container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=legacy_container.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _scalar(container: Container, sql: str) -> object:
    async with container.engine.connect() as connection:
        result = await connection.execute(text(sql))
        return result.scalar()


async def _count(container: Container, table: str) -> int:
    value = await _scalar(container, f"SELECT COUNT(*) FROM {table}")
    assert isinstance(value, int)
    return value


async def test_valid_payload_returns_the_legacy_success_body_byte_for_byte(
    legacy_client: httpx.AsyncClient, legacy_container: Container, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        _QUEUED, status=200, content_type="application/json"
    )

    response = await legacy_client.post("/send-email", json=_VALID_PAYLOAD)

    expected = json.dumps({"message": "Emails sent successfully", "response": _QUEUED})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == expected.encode()

    form = httpserver.log[0][0].form
    assert form["from"] == _FROM
    assert form["to"] == "ops@example.com"
    assert form["bcc"] == _BCC
    assert form["subject"] == "Backup finished"
    assert form["html"] == "<p>Backup <b>done</b>.</p>"
    assert form["text"] == "Backup done."
    assert form["o:tracking"] == "no"

    assert await _count(legacy_container, "notification") == 1
    assert await _count(legacy_container, "delivery") == 1
    assert await _scalar(legacy_container, "SELECT status FROM delivery") == "succeeded"
    assert await _count(legacy_container, "attempt") == 1
    assert await _scalar(legacy_container, "SELECT outcome FROM attempt") == "succeeded"
    assert await _scalar(legacy_container, "SELECT retriable FROM attempt") == 0


async def test_no_provider_config_row_falls_back_to_the_environment(
    legacy_client: httpx.AsyncClient, legacy_container: Container, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        _QUEUED, status=200, content_type="application/json"
    )

    response = await legacy_client.post("/send-email", json=_VALID_PAYLOAD)

    assert response.status_code == 200
    assert await _count(legacy_container, "provider_config") == 0
    assert httpserver.log[0][0].form["from"] == _FROM


async def test_a_provider_client_error_becomes_the_legacy_502(
    legacy_client: httpx.AsyncClient, legacy_container: Container, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        "Forbidden", status=401, content_type="text/plain"
    )

    response = await legacy_client.post("/send-email", json=_VALID_PAYLOAD)

    assert response.status_code == 502
    assert response.json() == {"error": "Failed to send emails", "response": "Forbidden"}
    assert await _scalar(legacy_container, "SELECT status FROM delivery") == "failed"
    assert await _scalar(legacy_container, "SELECT error_kind FROM attempt") == "http_status"
    assert await _scalar(legacy_container, "SELECT retriable FROM attempt") == 0


async def test_a_provider_server_error_is_recorded_retriable_and_returns_502(
    legacy_client: httpx.AsyncClient, legacy_container: Container, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        '{"message": "boom"}', status=500, content_type="application/json"
    )

    response = await legacy_client.post("/send-email", json=_VALID_PAYLOAD)

    assert response.status_code == 502
    assert response.json() == {"error": "Failed to send emails", "response": '{"message": "boom"}'}
    assert await _scalar(legacy_container, "SELECT status FROM delivery") == "failed"
    assert await _scalar(legacy_container, "SELECT retriable FROM attempt") == 1


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "'emails' must be a non-empty list"),
        ({"emails": []}, "'emails' must be a non-empty list"),
        ({"emails": "ops@example.com"}, "'emails' must be a non-empty list"),
        ({"emails": ["ops@example.com"]}, "'subject' and 'text' are required"),
        ({"emails": ["ops@example.com"], "subject": "s"}, "'subject' and 'text' are required"),
    ],
)
async def test_legacy_validation_errors_keep_their_messages(
    legacy_client: httpx.AsyncClient, payload: dict[str, object], message: str
) -> None:
    response = await legacy_client.post("/send-email", json=payload)

    assert response.status_code == 400
    assert response.json() == {"error": message}


async def test_invalid_json_is_a_400(legacy_client: httpx.AsyncClient) -> None:
    response = await legacy_client.post(
        "/send-email", content=b"{not json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid JSON"}


async def test_unknown_path_keeps_its_404_with_the_scaffold_envelope(
    legacy_client: httpx.AsyncClient,
) -> None:
    response = await legacy_client.post("/not-the-legacy-path", json={})

    assert response.status_code == 404
    assert response.json() == {"code": "resource_not_found", "detail": "Not Found"}


async def test_a_streamed_request_body_is_accepted(legacy_client: httpx.AsyncClient, httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        _QUEUED, status=200, content_type="application/json"
    )

    async def _chunks() -> AsyncIterator[bytes]:
        yield b'{"emails": ["ops@example.com"], '
        yield b'"subject": "Backup finished", "text": "<p>done</p>"}'

    response = await legacy_client.post("/send-email", content=_chunks(), headers={"content-type": "application/json"})

    assert response.status_code == 200


async def test_too_many_recipients_keep_the_legacy_error_shape(legacy_client: httpx.AsyncClient) -> None:
    payload = {
        "emails": [f"ops{index}@example.com" for index in range(51)],
        "subject": "Backup finished",
        "text": "<p>done</p>",
    }

    response = await legacy_client.post("/send-email", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert "code" not in body
