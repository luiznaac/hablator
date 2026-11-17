"""`GET`/`PUT`/`DELETE /channels` at the HTTP boundary, plus the push channel end-to-end.

The real app, the real MySQL and the real httpx stack are exercised; both provider adapters point
at the per-test stub server, so a fan-out never reaches a real Mailgun or ntfy.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pytest_httpserver import HTTPServer
from sqlalchemy import text

from hablator.application.container import Container

_TOKEN = "dev-hablator-api-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}
_FROM = "hablator@hablator.invalid"
_BCC = "hablator-archive@hablator.invalid"

_EMAIL_CONFIG = {"from": "ops@example.com", "bcc": "archive@example.com"}
_PUSH_CONFIG = {"topic": "hablator", "default_priority": 4}


async def _count(container: Container, table: str) -> int:
    async with container.engine.connect() as connection:
        result = await connection.execute(text(f"SELECT COUNT(*) FROM {table}"))
        value = result.scalar()
        assert isinstance(value, int)
        return value


async def _configure(client: httpx.AsyncClient, channel: str, payload: dict[str, Any]) -> None:
    response = await client.put(f"/channels/{channel}", json=payload, headers=_AUTH)
    assert response.status_code in {200, 201}, response.text


async def test_get_lists_every_channel_unconfigured(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/channels", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert [item["channel"] for item in body] == ["email", "push", "sms", "voice"]
    assert all(item["configured"] is False for item in body)
    assert all(item["provider"] is None for item in body)
    assert all(item["config"] is None for item in body)
    assert all(item["updated_at"] is None for item in body)


async def test_put_creates_with_201_then_replaces_with_200(api_client: httpx.AsyncClient) -> None:
    created = await api_client.put(
        "/channels/email", json={"provider": "mailgun", "config": _EMAIL_CONFIG}, headers=_AUTH
    )

    assert created.status_code == 201
    body = created.json()
    assert body["channel"] == "email"
    assert body["provider"] == "mailgun"
    assert body["configured"] is True
    assert body["config"] == _EMAIL_CONFIG
    assert body["updated_at"].endswith("Z")

    replaced = await api_client.put(
        "/channels/email",
        json={"provider": "mailgun", "config": {"from": "new@example.com"}},
        headers=_AUTH,
    )

    assert replaced.status_code == 200
    assert replaced.json()["config"] == {"from": "new@example.com"}

    listed = await api_client.get("/channels", headers=_AUTH)
    email = next(item for item in listed.json() if item["channel"] == "email")
    assert email["config"] == {"from": "new@example.com"}


async def test_put_push_config_is_created_and_lists_non_secret_values(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put("/channels/push", json={"provider": "ntfy", "config": _PUSH_CONFIG}, headers=_AUTH)

    assert response.status_code == 201
    listed = await api_client.get("/channels", headers=_AUTH)
    push = next(item for item in listed.json() if item["channel"] == "push")
    assert push["configured"] is True
    assert push["provider"] == "ntfy"
    assert push["config"] == _PUSH_CONFIG


async def test_put_rejects_a_provider_not_registered_for_the_channel(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/channels/email",
        json={"provider": "ntfy", "config": _PUSH_CONFIG},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


@pytest.mark.parametrize("channel", ["sms", "voice"])
async def test_put_rejects_a_channel_with_no_registered_provider(api_client: httpx.AsyncClient, channel: str) -> None:
    response = await api_client.put(
        f"/channels/{channel}",
        json={"provider": "ntfy", "config": _PUSH_CONFIG},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_put_rejects_an_unknown_channel(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/channels/telegram",
        json={"provider": "ntfy", "config": _PUSH_CONFIG},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_put_rejects_an_unknown_config_key_naming_it(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/channels/email",
        json={"provider": "mailgun", "config": {"from": "ops@example.com", "sender": "typo@example.com"}},
        headers=_AUTH,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "domain_error"
    assert "sender" in body["detail"]


@pytest.mark.parametrize(
    ("channel", "provider", "config", "env_var"),
    [
        ("push", "ntfy", {"topic": "hablator", "token": "leak"}, "NTFY__TOKEN"),
        ("email", "mailgun", {"from": "ops@example.com", "api_key": "leak"}, "MAILGUN__API_KEY"),
    ],
)
async def test_put_rejects_a_secret_shaped_key_naming_the_env_var(
    api_client: httpx.AsyncClient, channel: str, provider: str, config: dict[str, Any], env_var: str
) -> None:
    response = await api_client.put(
        f"/channels/{channel}", json={"provider": provider, "config": config}, headers=_AUTH
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "domain_error"
    assert env_var in body["detail"]
    assert "leak" not in body["detail"]


async def test_put_rejects_a_default_priority_out_of_bounds(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/channels/push",
        json={"provider": "ntfy", "config": {"topic": "hablator", "default_priority": 6}},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_put_rejects_an_unknown_top_level_field(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/channels/push",
        json={"provider": "ntfy", "config": _PUSH_CONFIG, "extra": True},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_channels_requires_the_bearer(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/channels")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_delete_is_idempotent_and_returns_204(api_client: httpx.AsyncClient) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})

    first = await api_client.delete("/channels/push", headers=_AUTH)
    second = await api_client.delete("/channels/push", headers=_AUTH)

    assert first.status_code == 204
    assert second.status_code == 204
    listed = await api_client.get("/channels", headers=_AUTH)
    push = next(item for item in listed.json() if item["channel"] == "push")
    assert push["configured"] is False


async def test_after_deleting_email_the_channel_falls_back_to_the_environment(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    await _configure(api_client, "email", {"provider": "mailgun", "config": _EMAIL_CONFIG})
    await api_client.delete("/channels/email", headers=_AUTH)
    httpserver.expect_request("/messages", method="POST").respond_with_data('{"message": "Queued."}', status=200)

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "s", "body": "b"},
            "channels": [{"channel": "email", "recipients": ["ops@example.com"]}],
        },
        headers=_AUTH,
    )

    assert response.status_code == 201
    assert response.json()["deliveries"][0]["status"] == "succeeded"
    assert httpserver.log[0][0].form["from"] == _FROM
    assert httpserver.log[0][0].form["bcc"] == _BCC


async def test_after_deleting_push_the_channel_rejects_with_422(api_client: httpx.AsyncClient) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})
    await api_client.delete("/channels/push", headers=_AUTH)

    response = await api_client.post(
        "/notifications",
        json={"content": {"subject": "s", "body": "b"}, "channels": [{"channel": "push"}]},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"


async def test_email_failing_does_not_fail_push_or_the_request(
    api_client: httpx.AsyncClient, httpserver: HTTPServer, api_container: Container
) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})
    httpserver.expect_request("/messages", method="POST").respond_with_data('{"message": "boom"}', status=500)
    httpserver.expect_request("/", method="POST").respond_with_data('{"id": "abc"}', status=200)

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "Backup finished", "body": "done"},
            "channels": [
                {"channel": "email", "recipients": ["ops@example.com"]},
                {"channel": "push"},
            ],
        },
        headers=_AUTH,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    statuses = {delivery["channel"]: delivery["status"] for delivery in body["deliveries"]}
    assert statuses == {"email": "failed", "push": "succeeded"}
    attempts = {delivery["channel"]: delivery["attempts"][0] for delivery in body["deliveries"]}
    assert attempts["email"]["provider"] == "mailgun"
    assert attempts["email"]["retriable"] is True
    assert attempts["push"]["provider"] == "ntfy"
    assert attempts["push"]["outcome"] == "succeeded"

    ntfy_request = next(request for request, _ in httpserver.log if request.path == "/")
    assert ntfy_request.json["topic"] == "hablator"
    assert ntfy_request.json["title"] == "Backup finished"
    assert ntfy_request.json["message"] == "done"
    assert ntfy_request.json["priority"] == 4
    assert await _count(api_container, "delivery") == 2


async def test_push_caps_reject_the_whole_request_and_create_nothing(
    api_client: httpx.AsyncClient, api_container: Container
) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})

    response = await api_client.post(
        "/notifications",
        json={"content": {"subject": "s", "body": "x" * 4097}, "channels": [{"channel": "push"}]},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"
    assert await _count(api_container, "notification") == 0
    assert await _count(api_container, "delivery") == 0


async def test_push_title_cap_rejects_the_whole_request(
    api_client: httpx.AsyncClient, api_container: Container
) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})

    response = await api_client.post(
        "/notifications",
        json={"content": {"subject": "é" * 600, "body": "b"}, "channels": [{"channel": "push"}]},
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"
    assert await _count(api_container, "notification") == 0


async def test_push_rejects_recipients_and_creates_nothing(
    api_client: httpx.AsyncClient, api_container: Container
) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "s", "body": "b"},
            "channels": [{"channel": "push", "recipients": ["ops@example.com"]}],
        },
        headers=_AUTH,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "domain_error"
    assert await _count(api_container, "notification") == 0


async def test_push_rejects_an_unknown_option(api_client: httpx.AsyncClient) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": _PUSH_CONFIG})

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "s", "body": "b"},
            "channels": [{"channel": "push", "options": {"sound": "alarm"}}],
        },
        headers=_AUTH,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "domain_error"
    assert "sound" in body["detail"]


async def test_push_priority_alias_is_normalized_before_persistence(
    api_client: httpx.AsyncClient, httpserver: HTTPServer
) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": {"topic": "hablator"}})
    httpserver.expect_request("/", method="POST").respond_with_data("{}", status=200)

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "s", "body": "b"},
            "channels": [{"channel": "push", "options": {"priority": "urgent", "tags": ["warning"]}}],
        },
        headers=_AUTH,
    )

    assert response.status_code == 201
    delivery = response.json()["deliveries"][0]
    assert delivery["options"]["priority"] == 5
    assert delivery["options"]["tags"] == ["warning"]
    ntfy_request = next(request for request, _ in httpserver.log if request.path == "/")
    assert ntfy_request.json["priority"] == 5
    assert ntfy_request.json["tags"] == ["warning"]


async def test_push_click_is_published(api_client: httpx.AsyncClient, httpserver: HTTPServer) -> None:
    await _configure(api_client, "push", {"provider": "ntfy", "config": {"topic": "hablator"}})
    httpserver.expect_request("/", method="POST").respond_with_data("{}", status=200)

    response = await api_client.post(
        "/notifications",
        json={
            "content": {"subject": "s", "body": "b"},
            "channels": [{"channel": "push", "options": {"click": "https://example.com/x"}}],
        },
        headers=_AUTH,
    )

    assert response.status_code == 201
    ntfy_request = next(request for request, _ in httpserver.log if request.path == "/")
    assert ntfy_request.json["click"] == "https://example.com/x"
