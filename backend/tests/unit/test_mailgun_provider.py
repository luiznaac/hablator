"""The Mailgun adapter against a local stub server: real httpx, URL, form encoding and headers."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpserver import HTTPServer

from hablator.gateway.configuration.http_client import build_http_client
from hablator.gateway.email.mailgun_provider import MailgunEmailProvider
from hablator.usecase.channel.model import Channel, ChannelMessage, Content, ErrorKind, Recipient
from hablator.usecase.commons.exceptions import DomainError

_FROM = "hablator@example.com"
_BCC = "archive@example.com"


def _provider(httpserver: HTTPServer) -> MailgunEmailProvider:
    client = build_http_client()
    return MailgunEmailProvider(
        client,
        api_url=httpserver.url_for("/messages"),
        api_key="key-secret",
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
        api_key="key",
        from_email=_FROM,
        bcc_email=_BCC,
    )

    result = await provider.send(_message())

    assert result.error_kind is kind
    assert result.provider_status is None


async def test_html_only_when_the_plain_part_is_empty(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("queued", status=200)
    provider = _provider(httpserver)

    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="", body_html="<p>only html</p>"),
        options={},
        config={},
    )
    await provider.send(message)

    form = httpserver.log[0][0].form
    assert form["html"] == "<p>only html</p>"
    assert "text" not in form


def test_resolve_fills_recipients_from_the_provider_config_default(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(),
        content=Content(subject="s", body_text="b"),
        options={},
        config={"recipients": ["default@example.com"]},
    )

    resolved = provider.prepare(message)

    assert tuple(recipient.address for recipient in resolved.recipients) == ("default@example.com",)


def test_resolve_keeps_explicit_recipients(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="b"),
        options={},
        config={"recipients": ["default@example.com"]},
    )

    resolved = provider.prepare(message)

    assert tuple(recipient.address for recipient in resolved.recipients) == ("ops@example.com",)


def test_resolve_rejects_email_options(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="b"),
        options={"priority": 3},
        config={},
    )

    with pytest.raises(DomainError):
        provider.prepare(message)


def test_resolve_rejects_a_request_with_no_recipients_and_no_default(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(),
        content=Content(subject="s", body_text="b"),
        options={},
        config={},
    )

    with pytest.raises(DomainError):
        provider.prepare(message)


def test_resolve_rejects_more_than_fifty_default_recipients(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(),
        content=Content(subject="s", body_text="b"),
        options={},
        config={"recipients": [f"ops{index}@example.com" for index in range(51)]},
    )

    with pytest.raises(DomainError):
        provider.prepare(message)


def test_resolve_rejects_an_unknown_provider_config_key(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="s", body_text="b"),
        options={},
        config={"sender": "typo@example.com"},
    )

    with pytest.raises(DomainError):
        provider.prepare(message)


@pytest.mark.parametrize("status", [420, 429])
async def test_rate_limit_statuses_normalize_to_http_status(httpserver: HTTPServer, status: int) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("rate limited", status=status)
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == status


async def test_a_generic_client_error_is_an_http_status_failure(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/messages", method="POST").respond_with_data("bad request", status=400)
    provider = _provider(httpserver)

    result = await provider.send(_message())

    assert result.error_kind is ErrorKind.HTTP_STATUS
    assert result.provider_status == 400
    assert result.error_message == "bad request"


def test_validate_config_accepts_from_and_bcc(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    validated = provider.validate_config({"from": "ops@example.com", "bcc": "archive@example.com"})

    assert validated == {"from": "ops@example.com", "bcc": "archive@example.com"}


def test_validate_config_requires_from(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    with pytest.raises(DomainError):
        provider.validate_config({"bcc": "archive@example.com"})


def test_validate_config_rejects_an_empty_from(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    with pytest.raises(DomainError):
        provider.validate_config({"from": "   "})


def test_validate_config_names_an_unknown_key(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    with pytest.raises(DomainError) as raised:
        provider.validate_config({"from": "ops@example.com", "sender": "typo@example.com"})

    assert "sender" in str(raised.value)


def test_validate_config_accepts_the_recipients_default(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    validated = provider.validate_config({"from": "ops@example.com", "recipients": ["default@example.com"]})

    assert validated["recipients"] == ["default@example.com"]


def test_validate_config_rejects_more_than_fifty_default_recipients(httpserver: HTTPServer) -> None:
    provider = _provider(httpserver)

    with pytest.raises(DomainError):
        provider.validate_config({"from": "ops@example.com", "recipients": [f"a{i}@example.com" for i in range(51)]})
