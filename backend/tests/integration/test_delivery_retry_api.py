"""`POST /deliveries/{id}/retry` at the HTTP boundary.

The real dispatcher runs against the stub Mailgun server: a failed delivery is re-attempted
synchronously and gains the next append-only Attempt; the lifecycle guards answer `409`, an
unknown delivery answers `404`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pytest_httpserver import HTTPServer
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fixtures import API_AUTH, insert_notification

_QUEUED = '{"id": "<20261116.1@hablator.invalid>", "message": "Queued. Thank you."}'
_NOW = datetime(2026, 1, 1, 12, 0, 0)

_VALID: dict[str, Any] = {
    "source": "valoab",
    "content": {"subject": "Backup finished", "body": "plain text"},
    "channels": [{"channel": "email", "recipients": ["ops@example.com"]}],
}


async def _create(api_client: httpx.AsyncClient) -> dict[str, Any]:
    response = await api_client.post("/notifications", json=_VALID, headers=API_AUTH)
    assert response.status_code == 201
    return response.json()


async def _insert_delivery(engine: AsyncEngine, *, status: str) -> int:
    _, delivery_ids = await insert_notification(
        engine,
        created_at=_NOW,
        deliveries=(("email", status),),
    )
    return delivery_ids[0]


async def test_a_failed_delivery_retries_synchronously_and_appends_the_next_attempt(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data('{"message": "boom"}', status=500)
    delivery = (await _create(api_client))["deliveries"][0]
    assert delivery["status"] == "failed"
    assert [attempt["attempt_number"] for attempt in delivery["attempts"]] == [1]

    httpserver.clear()
    httpserver.expect_request("/messages", method="POST").respond_with_data(_QUEUED, status=200)
    response = await api_client.post(f"/deliveries/{delivery['id']}/retry", headers=API_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == delivery["id"]
    assert body["status"] == "succeeded"
    assert [attempt["attempt_number"] for attempt in body["attempts"]] == [1, 2]
    assert [attempt["outcome"] for attempt in body["attempts"]] == ["failed", "succeeded"]
    assert len(httpserver.log) == 1


async def test_a_pending_delivery_is_retriable(
    api_client: httpx.AsyncClient, engine: AsyncEngine, httpserver: HTTPServer
) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(_QUEUED, status=200)
    delivery_id = await _insert_delivery(engine, status="pending")

    response = await api_client.post(f"/deliveries/{delivery_id}/retry", headers=API_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert [attempt["attempt_number"] for attempt in body["attempts"]] == [1]


async def test_a_succeeded_delivery_is_409_conflict(api_client: httpx.AsyncClient, httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(_QUEUED, status=200)
    delivery = (await _create(api_client))["deliveries"][0]
    assert delivery["status"] == "succeeded"

    response = await api_client.post(f"/deliveries/{delivery['id']}/retry", headers=API_AUTH)

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert len(httpserver.log) == 1


async def test_an_in_progress_delivery_is_409_conflict(api_client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    delivery_id = await _insert_delivery(engine, status="in_progress")

    response = await api_client.post(f"/deliveries/{delivery_id}/retry", headers=API_AUTH)

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


async def test_an_unknown_delivery_is_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/deliveries/999999/retry", headers=API_AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"


async def test_retry_requires_the_bearer(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/deliveries/1/retry")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["code"] == "unauthorized"
