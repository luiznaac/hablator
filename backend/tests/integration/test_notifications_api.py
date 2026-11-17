"""`POST /notifications` and `GET /notifications/{id}` at the HTTP boundary.

A stub Mailgun server stands in for the provider; the real app, the real MySQL and the real httpx
stack are exercised. The error cases pin the scaffold envelope and the field path.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pytest_httpserver import HTTPServer
from sqlalchemy import text

from hablator.application.container import Container

_TOKEN = "dev-hablator-api-token"
_QUEUED = '{"id": "<20261116.1@hablator.invalid>", "message": "Queued. Thank you."}'
_FROM = "hablator@hablator.invalid"
_BCC = "hablator-archive@hablator.invalid"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_VALID = {
    "source": "valoab",
    "content": {"subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>"},
    "channels": [{"channel": "email", "recipients": ["ops@example.com"]}],
}


def _expect_send(httpserver: HTTPServer, *, status: int = 200, body: str = _QUEUED) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(body, status=status)


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "content": {"subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>"},
        "channels": [{"channel": "email", "recipients": ["ops@example.com"]}],
    }
    payload.update(overrides)
    return payload


async def test_a_valid_email_returns_201_location_and_the_full_representation(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    _expect_send(httpserver)

    response = await api_client.post("/notifications", json=_VALID, headers=_AUTH)

    assert response.status_code == 201
    body = response.json()
    assert response.headers["Location"] == f"/notifications/{body['id']}"
    assert body["source"] == "valoab"
    assert body["content"] == {"subject": "Backup finished", "body": "plain text", "body_html": "<p>rich</p>"}
    assert body["status"] == "succeeded"
    assert body["created_at"].endswith("Z")
    delivery = body["deliveries"][0]
    assert delivery["channel"] == "email"
    assert delivery["status"] == "succeeded"
    assert delivery["recipients"] == ["ops@example.com"]
    assert delivery["attempts"][0]["attempt_number"] == 1
    assert delivery["attempts"][0]["outcome"] == "succeeded"
    assert delivery["attempts"][0]["provider"] == "mailgun"
    assert delivery["attempts"][0]["provider_status"] == 200
    assert delivery["attempts"][0]["retriable"] is False

    form = httpserver.log[0][0].form
    assert form["from"] == _FROM
    assert form["to"] == "ops@example.com"
    assert form["bcc"] == _BCC
    assert form["subject"] == "Backup finished"
    assert form["text"] == "plain text"
    assert form["html"] == "<p>rich</p>"
    assert form["o:tracking"] == "no"


async def test_get_returns_the_same_representation(api_client: httpx.AsyncClient, httpserver: HTTPServer) -> None:
    _expect_send(httpserver)
    created = await api_client.post("/notifications", json=_VALID, headers=_AUTH)

    response = await api_client.get(f"/notifications/{created.json()['id']}", headers=_AUTH)

    assert response.status_code == 200
    assert response.json() == created.json()


async def test_a_failing_provider_still_returns_201_with_a_failed_delivery(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    _expect_send(httpserver, status=500, body='{"message": "boom"}')

    response = await api_client.post("/notifications", json=_VALID, headers=_AUTH)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    attempt = body["deliveries"][0]["attempts"][0]
    assert attempt["outcome"] == "failed"
    assert attempt["retriable"] is True
    assert attempt["provider_status"] == 500
    assert attempt["error_message"] == "boom"


async def test_get_an_unknown_notification_is_not_found(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/notifications/999999", headers=_AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"


async def test_an_unknown_path_is_the_scaffold_envelope(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/nope")

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"


@pytest.mark.parametrize("header", [None, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}])
async def test_the_new_api_rejects_a_missing_or_wrong_bearer(api_client: httpx.AsyncClient, header: Any) -> None:
    response = await api_client.get("/notifications/1", headers=header)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["code"] == "unauthorized"


async def test_health_legacy_and_docs_stay_open(api_client: httpx.AsyncClient) -> None:
    assert (await api_client.get("/health")).status_code == 200
    assert (await api_client.get("/openapi.json")).status_code == 200
    assert (await api_client.get("/docs")).status_code == 200


async def test_a_duplicate_channel_is_400_invalid_argument(api_client: httpx.AsyncClient) -> None:
    payload = _payload(
        channels=[
            {"channel": "email", "recipients": ["a@example.com"]},
            {"channel": "email", "recipients": ["b@example.com"]},
        ]
    )

    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_argument"


@pytest.mark.parametrize("channel", ["sms", "voice", "push"])
async def test_an_unavailable_channel_is_422_domain_error(api_client: httpx.AsyncClient, channel: str) -> None:
    response = await api_client.post("/notifications", json=_payload(channels=[{"channel": channel}]), headers=_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_an_unknown_email_option_is_422_domain_error(api_client: httpx.AsyncClient) -> None:
    payload = _payload(channels=[{"channel": "email", "recipients": ["ops@example.com"], "options": {"priority": 1}}])

    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_email_without_recipients_and_no_default_is_422_domain_error(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/notifications", json=_payload(channels=[{"channel": "email"}]), headers=_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {"content": {"body": "b"}, "channels": [{"channel": "email", "recipients": ["a@example.com"]}]},
            "content.subject",
        ),
        (
            {"content": {"subject": "s"}, "channels": [{"channel": "email", "recipients": ["a@example.com"]}]},
            "content.body",
        ),
        ({"content": {"subject": "s", "body": "b"}, "channels": []}, "channels"),
        (
            {"content": {"subject": "s", "body": "b"}, "channels": [{"channel": "email", "recipients": []}]},
            "channels.0.recipients",
        ),
        (
            {
                "content": {"subject": "s", "body": "b"},
                "channels": [{"channel": "email", "recipients": [f"a{index}@example.com" for index in range(51)]}],
            },
            "channels.0.recipients",
        ),
        (
            {
                "content": {"subject": "s" * 999, "body": "b"},
                "channels": [{"channel": "email", "recipients": ["a@example.com"]}],
            },
            "content.subject",
        ),
        (
            {
                "source": "s" * 65,
                "content": {"subject": "s", "body": "b"},
                "channels": [{"channel": "email", "recipients": ["a@example.com"]}],
            },
            "source",
        ),
        (
            {
                "content": {"subject": "s", "body": "b"},
                "channels": [{"channel": "email", "recipients": ["a@example.com"]}] * 5,
            },
            "channels",
        ),
        (
            {
                "content": {"subject": "s", "body": "b", "body_html": "x" * (256 * 1024 + 1)},
                "channels": [{"channel": "email", "recipients": ["a@example.com"]}],
            },
            "content.body_html",
        ),
    ],
)
async def test_shape_and_cap_violations_are_422_validation_error_with_a_field_path(
    api_client: httpx.AsyncClient, payload: dict[str, Any], field: str
) -> None:
    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == field
    assert body["errors"][0]["message"]


async def test_an_unknown_field_anywhere_is_422_validation_error(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/notifications", json=_payload(metadata={}), headers=_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_a_body_part_over_256_kib_is_422_validation_error(api_client: httpx.AsyncClient) -> None:
    payload = _payload(content={"subject": "s", "body": "x" * (256 * 1024 + 1)})

    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == "content.body"


async def test_a_request_body_over_1_mib_is_413(api_client: httpx.AsyncClient) -> None:
    payload = _payload(content={"subject": "s", "body": "x" * (1024 * 1024)})

    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


async def test_a_non_json_content_type_is_415(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/notifications",
        content=b"subject=hello",
        headers={**_AUTH, "Content-Type": "text/plain"},
    )

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


async def test_a_channel_content_override_merges_over_the_base(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    _expect_send(httpserver)
    payload = _payload(
        channels=[
            {
                "channel": "email",
                "recipients": ["ops@example.com"],
                "content": {"subject": "Override"},
            }
        ]
    )

    response = await api_client.post("/notifications", json=payload, headers=_AUTH)

    assert response.status_code == 201
    content = response.json()["deliveries"][0]["content"]
    assert content == {"subject": "Override", "body": "plain text", "body_html": "<p>rich</p>"}


async def test_an_unhandled_error_is_the_internal_error_envelope(
    api_client: httpx.AsyncClient, api_container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(_: object) -> object:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(api_container.notification_service, "send", _boom)

    response = await api_client.post("/notifications", json=_VALID, headers=_AUTH)

    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "detail": "Internal Server Error"}


async def test_an_unknown_provider_config_key_is_422_domain_error(
    api_client: httpx.AsyncClient, api_container: Container
) -> None:
    async with api_container.engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO provider_config (channel, provider, config, updated_at) "
                "VALUES ('email', 'mailgun', JSON_OBJECT('sender', 'typo@example.com'), NOW(6))"
            )
        )

    response = await api_client.post("/notifications", json=_VALID, headers=_AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"
