"""The pure channel rules: retriability classification and the provider registry."""

from __future__ import annotations

import pytest

from hablator.usecase.channel.classify import classify
from hablator.usecase.channel.model import (
    Channel,
    ChannelMessage,
    Content,
    ErrorKind,
    ProviderResult,
    Recipient,
)
from hablator.usecase.channel.registry import ChannelRegistry
from hablator.usecase.commons.exceptions import UnknownProviderError


def _result(
    *,
    provider_status: int | None = None,
    error_kind: ErrorKind | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider="mailgun",
        provider_status=provider_status,
        error_kind=error_kind,
        error_message=None if error_kind is None else "boom",
        provider_body="",
    )


def test_a_successful_result_is_not_retriable() -> None:
    assert classify(_result(provider_status=200)) is False


def test_timeout_and_network_are_retriable() -> None:
    assert classify(_result(error_kind=ErrorKind.TIMEOUT)) is True
    assert classify(_result(error_kind=ErrorKind.NETWORK)) is True


def test_rate_limits_and_server_errors_are_retriable() -> None:
    for status in (420, 429, 500, 502, 503):
        assert classify(_result(provider_status=status, error_kind=ErrorKind.HTTP_STATUS)) is True


def test_other_client_errors_and_unexpected_are_not_retriable() -> None:
    assert classify(_result(provider_status=400, error_kind=ErrorKind.HTTP_STATUS)) is False
    assert classify(_result(provider_status=401, error_kind=ErrorKind.HTTP_STATUS)) is False
    assert classify(_result(provider_status=422, error_kind=ErrorKind.HTTP_STATUS)) is False
    assert classify(_result(error_kind=ErrorKind.UNEXPECTED)) is False


class _StubProvider:
    def __init__(self, name: str, channel: Channel) -> None:
        self.name = name
        self.channel = channel

    async def send(self, message: ChannelMessage) -> ProviderResult:  # pragma: no cover - unused
        return _result(provider_status=200)


def test_registry_looks_up_a_provider_by_channel_and_name() -> None:
    registry = ChannelRegistry()
    mailgun = _StubProvider("mailgun", Channel.EMAIL)
    registry.register(mailgun)

    assert registry.get(Channel.EMAIL, "mailgun") is mailgun
    assert registry.get(Channel.EMAIL, "ntfy") is None
    assert registry.get(Channel.PUSH, "mailgun") is None


def test_channel_message_carries_opaque_recipients_content_options_and_config() -> None:
    message = ChannelMessage(
        channel=Channel.EMAIL,
        recipients=(Recipient("ops@example.com"),),
        content=Content(subject="hi", body_text="hello", body_html="<p>hello</p>"),
        options={},
        config={"from": "hablator@example.com"},
    )

    assert message.recipients[0].address == "ops@example.com"
    assert message.config["from"] == "hablator@example.com"


def test_registry_resolve_returns_a_registered_provider() -> None:
    registry = ChannelRegistry()
    mailgun = _StubProvider("mailgun", Channel.EMAIL)
    registry.register(mailgun)

    assert registry.resolve(Channel.EMAIL, "mailgun") is mailgun


@pytest.mark.parametrize(("channel", "name"), [(Channel.EMAIL, "ntfy"), (Channel.PUSH, "mailgun")])
def test_registry_resolve_rejects_an_unregistered_pair(channel: Channel, name: str) -> None:
    registry = ChannelRegistry()
    registry.register(_StubProvider("mailgun", Channel.EMAIL))

    with pytest.raises(UnknownProviderError):
        registry.resolve(channel, name)
