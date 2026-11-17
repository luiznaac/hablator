"""The ntfy push adapter: config shape, request rules and the JSON publish against a stub server."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpserver import HTTPServer

from hablator.gateway.configuration.http_client import build_http_client
from hablator.gateway.push.ntfy_provider import NtfyPushProvider
from hablator.usecase.channel.model import Channel, ChannelMessage, Content, ErrorKind, Recipient
from hablator.usecase.commons.exceptions import DomainError

_TOPIC = "hablator"


def _provider(httpserver: HTTPServer | None = None) -> NtfyPushProvider:
    base_url = httpserver.url_for("/") if httpserver is not None else "http://ntfy.invalid"
    return NtfyPushProvider(build_http_client(), base_url=base_url, token="tk_secret")


def _message(
    *,
    options: dict[str, object] | None = None,
    config: dict[str, object] | None = None,
    subject: str | None = "Backup finished",
    body: str = "done",
    recipients: tuple[Recipient, ...] = (),
) -> ChannelMessage:
    return ChannelMessage(
        channel=Channel.PUSH,
        recipients=recipients,
        content=Content(subject=subject, body_text=body),
        options=options or {},
        config=config if config is not None else {"topic": _TOPIC},
    )


def test_validate_config_accepts_a_topic_and_a_default_priority() -> None:
    provider = _provider()

    validated = provider.validate_config({"topic": _TOPIC, "default_priority": 4})

    assert validated == {"topic": _TOPIC, "default_priority": 4}


def test_validate_config_requires_a_topic() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.validate_config({"default_priority": 3})


def test_validate_config_rejects_an_empty_topic() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.validate_config({"topic": "   "})


def test_validate_config_names_an_unknown_key() -> None:
    provider = _provider()

    with pytest.raises(DomainError) as raised:
        provider.validate_config({"topic": _TOPIC, "server": "typo"})

    assert "server" in str(raised.value)


@pytest.mark.parametrize("priority", [0, 6, "min", True, None])
def test_validate_config_rejects_a_default_priority_out_of_bounds(priority: object) -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.validate_config({"topic": _TOPIC, "default_priority": priority})


def test_prepare_fills_the_single_recipient_from_the_config_topic() -> None:
    provider = _provider()

    resolved = provider.prepare(_message())

    assert [recipient.address for recipient in resolved.recipients] == [_TOPIC]


def test_prepare_rejects_a_request_that_carries_recipients() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(recipients=(Recipient("ops@example.com"),)))


def test_prepare_rejects_a_missing_topic() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(config={}))


def test_prepare_rejects_a_title_over_one_kib() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(subject="x" * 1025))


def test_prepare_accepts_a_title_of_exactly_one_kib() -> None:
    provider = _provider()

    resolved = provider.prepare(_message(subject="x" * 1024))

    assert resolved.content.subject == "x" * 1024


def test_prepare_rejects_a_message_over_4096_bytes() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(body="x" * 4097))


def test_prepare_rejects_a_multibyte_message_over_4096_bytes() -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(body="é" * 2049))


def test_prepare_names_an_unknown_option() -> None:
    provider = _provider()

    with pytest.raises(DomainError) as raised:
        provider.prepare(_message(options={"sound": "alarm"}))

    assert "sound" in str(raised.value)


@pytest.mark.parametrize(
    ("alias", "normalized"),
    [("min", 1), ("low", 2), ("default", 3), ("high", 4), ("urgent", 5)],
)
def test_prepare_normalizes_a_priority_alias_to_its_integer(alias: str, normalized: int) -> None:
    provider = _provider()

    resolved = provider.prepare(_message(options={"priority": alias}))

    assert resolved.options["priority"] == normalized


def test_prepare_keeps_an_integer_priority() -> None:
    provider = _provider()

    resolved = provider.prepare(_message(options={"priority": 2}))

    assert resolved.options["priority"] == 2


@pytest.mark.parametrize("priority", [0, 6, "loud"])
def test_prepare_rejects_a_priority_out_of_bounds(priority: object) -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(options={"priority": priority}))


def test_prepare_applies_the_config_default_priority() -> None:
    provider = _provider()

    resolved = provider.prepare(_message(config={"topic": _TOPIC, "default_priority": 4}))

    assert resolved.options["priority"] == 4


def test_prepare_lets_the_request_override_the_default_priority() -> None:
    provider = _provider()

    resolved = provider.prepare(
        _message(options={"priority": "urgent"}, config={"topic": _TOPIC, "default_priority": 1})
    )

    assert resolved.options["priority"] == 5


def test_prepare_defaults_the_priority_to_three() -> None:
    provider = _provider()

    resolved = provider.prepare(_message())

    assert resolved.options["priority"] == 3


def test_prepare_accepts_tags_and_an_absolute_click() -> None:
    provider = _provider()

    resolved = provider.prepare(
        _message(options={"tags": ["warning", "backup"], "click": "https://hablator.example.com/notifications/42"})
    )

    assert resolved.options["tags"] == ["warning", "backup"]
    assert resolved.options["click"] == "https://hablator.example.com/notifications/42"


@pytest.mark.parametrize("click", ["/relative", "ftp://example.com/x", "example.com", 42])
def test_prepare_rejects_a_non_http_absolute_click(click: object) -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(options={"click": click}))


@pytest.mark.parametrize("tags", ["warning", [""], [42]])
def test_prepare_rejects_a_malformed_tags_option(tags: object) -> None:
    provider = _provider()

    with pytest.raises(DomainError):
        provider.prepare(_message(options={"tags": tags}))


async def test_send_posts_the_json_body_to_the_server_root_with_a_bearer_token(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data('{"id": "abc"}', status=200)
    provider = _provider(httpserver)

    result = await provider.send(_message(options={"priority": 4, "tags": ["warning"]}))

    assert result.provider == "ntfy"
    assert result.provider_status == 200
    assert result.error_kind is None
    assert result.is_success is True

    request = httpserver.log[0][0]
    assert request.headers["Authorization"] == "Bearer tk_secret"
    assert request.headers["Content-Type"] == "application/json"
    assert request.json == {
        "topic": _TOPIC,
        "title": "Backup finished",
        "message": "done",
        "priority": 4,
        "tags": ["warning"],
    }


async def test_send_includes_click_when_configured(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data("{}", status=200)
    provider = _provider(httpserver)

    await provider.send(_message(options={"click": "https://example.com/x"}))

    assert httpserver.log[0][0].json["click"] == "https://example.com/x"


async def test_send_omits_the_title_when_the_subject_is_empty(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data("{}", status=200)
    provider = _provider(httpserver)

    await provider.send(_message(subject=None))

    assert "title" not in httpserver.log[0][0].json


async def test_a_json_error_body_feeds_the_error_message(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data(
        '{"code": 40101, "http": 401, "error": "unauthorized"}',
        status=401,
        content_type="application/json",
    )
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == 401
    assert result.error_message == "unauthorized"


@pytest.mark.parametrize("status", [400, 403, 429, 500, 503])
async def test_non_success_statuses_normalize_to_http_status(httpserver: HTTPServer, status: int) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data("nope", status=status)
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == status
    assert len(httpserver.log) == 1


async def test_a_redirect_is_not_followed(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/", method="POST").respond_with_data("", status=302, headers={"Location": "/elsewhere"})
    httpserver.expect_request("/elsewhere", method="POST").respond_with_data("{}", status=200)
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.provider_status == 302
    assert [request.path for request, _ in httpserver.log] == ["/"]


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (httpx.ReadTimeout("read timed out"), ErrorKind.TIMEOUT),
        (httpx.ConnectError("connection refused"), ErrorKind.NETWORK),
    ],
)
async def test_transport_errors_are_normalized(error: httpx.RequestError, kind: ErrorKind) -> None:
    def _raise(request: httpx.Request) -> httpx.Response:
        raise error

    client = httpx.AsyncClient(transport=httpx.MockTransport(_raise))
    provider = NtfyPushProvider(client, base_url="http://ntfy.invalid", token="tk_secret")

    result = await provider.send(_message())

    assert result.error_kind is kind
    assert result.provider_status is None
