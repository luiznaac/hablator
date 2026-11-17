"""The Mailgun adapter against a local stub server: real httpx, URL, form encoding and headers."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpserver import HTTPServer

from hablator.gateway.configuration.http_client import build_http_client
from hablator.gateway.email.mailgun_provider import MailgunEmailProvider
from hablator.usecase.channel.model import Channel, ChannelMessage, Content, ErrorKind, Recipient

_FROM = "hablator@example.com"
_BCC = "archive@example.com"


def _provider(httpserver: HTTPServer) -> MailgunEmailProvider:
    client = build_http_client()
    return MailgunEmailProvider(
        client,
        api_url=httpserver.url_for("/messages"),
        api_auth="key-secret",
        from_email=_FROM,
        bcc_email=_BCC,
    )


def _message(*, config: dict[str, object] | None = None, html: str | None = "<p>hi</p>") -> ChannelMessage:
    return ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"), Recipient("dev@example.com")),
        content=Content(subject="Backup finished", body_text="hi", body_html=html),
        options={},
        config=config or {},
    )


async def test_success_posts_the_legacy_form_fields_and_returns_the_raw_body(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        '{"id": "<2026@hablator.invalid>", "message": "Queued. Thank you."}',
        status=200,
        content_type="application/json",
    )
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.provider == "mailgun"
    assert result.provider_status == 200
    assert result.error_kind is None
    assert result.is_success is True
    assert result.provider_body == '{"id": "<2026@hablator.invalid>", "message": "Queued. Thank you."}'

    request = httpserver.log[0][0]
    assert request.headers["Authorization"].startswith("Basic ")
    assert request.form["from"] == _FROM
    assert request.form["to"] == "ops@example.com, dev@example.com"
    assert request.form["bcc"] == _BCC
    assert request.form["subject"] == "Backup finished"
    assert request.form["html"] == "<p>hi</p>"
    assert request.form["text"] == "hi"
    assert request.form["o:tracking"] == "no"


async def test_provider_config_overrides_from_and_bcc(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("queued", status=200)
    provider = _provider(httpserver)

    await provider.send(_message(config={"from": "override@example.com", "bcc": "audit@example.com"}))

    form = httpserver.log[0][0].form
    assert form["from"] == "override@example.com"
    assert form["bcc"] == "audit@example.com"


async def test_html_is_omitted_when_there_is_no_html_part(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("queued", status=200)
    provider = _provider(httpserver)

    await provider.send(_message(html=None))

    assert "html" not in httpserver.log[0][0].form


async def test_a_json_error_body_feeds_the_error_message(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        '{"message": "Forbidden"}', status=401, content_type="application/json"
    )
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == 401
    assert result.error_message == "Forbidden"
    assert result.provider_body == '{"message": "Forbidden"}'


async def test_a_bare_string_error_body_is_kept_verbatim(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data(
        "Forbidden", status=401, content_type="text/plain"
    )
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.error_message == "Forbidden"
    assert result.provider_body == "Forbidden"


async def test_a_server_error_is_an_http_status_failure(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("boom", status=503)
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == 503


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
    provider = MailgunEmailProvider(
        client,
        api_url="https://api.mailgun.invalid/v3/dom/messages",
        api_auth="key",
        from_email=_FROM,
        bcc_email=_BCC,
    )

    result = await provider.send(_message())

    assert result.error_kind is kind
    assert result.provider_status is None
