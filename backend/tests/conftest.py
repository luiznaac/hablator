from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from ipaddress import ip_address
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from hablator.application.telemetry import Telemetry

# The test profile never exports: set it before any test module imports the app.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http,database")
# The two secrets have no default in code; tests supply the dev fixtures.
os.environ.setdefault("MAILGUN__API_KEY", "dev-hablator-mailgun-key")
os.environ.setdefault("AUTH__API_TOKEN", "dev-hablator-api-token")

_LOOPBACK_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})


def _is_loopback(address: object) -> bool:
    """Loopback IPv4/IPv6 and AF_UNIX addresses are allowed; everything else is a test leak."""
    if not isinstance(address, tuple) or not address:
        return True
    host = address[0]
    if not isinstance(host, str):
        return False
    if host in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject any outbound connection whose host is not loopback.

    No test may reach a real provider. The stub servers, MySQL in Testcontainers and the
    Docker daemon are all loopback or Unix-socket, so this never fires on legitimate traffic.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self: socket.socket, address: object) -> None:
        if not _is_loopback(address):
            raise RuntimeError(f"no_network: blocked an outbound connection to {address!r}")
        real_connect(self, address)  # type: ignore[arg-type]

    def guarded_connect_ex(self: socket.socket, address: object) -> int:
        if not _is_loopback(address):
            raise RuntimeError(f"no_network: blocked an outbound connection to {address!r}")
        return real_connect_ex(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture(autouse=True)
def _quiet_logging() -> None:
    from hablator.usecase.commons.logging import configure_logging

    configure_logging("WARNING", json=False)


@pytest.fixture
def telemetry() -> Iterator[Telemetry]:
    """In-memory telemetry with the log bridge installed — the shared capture seam."""
    from hablator.application.telemetry import build_telemetry
    from hablator.usecase.commons.logging import configure_logging
    from tests.fixtures import build_test_settings

    instance = build_telemetry(build_test_settings())
    configure_logging("INFO", json=True)
    instance.install_log_bridge()
    try:
        yield instance
    finally:
        instance.shutdown()
