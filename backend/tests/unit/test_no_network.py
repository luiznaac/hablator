"""The `no_network` autouse fixture: loopback is allowed, any real host is blocked."""

from __future__ import annotations

import socket

import pytest


def test_loopback_connections_are_allowed() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect(server.getsockname())


def test_a_non_loopback_connection_is_blocked() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client,
        pytest.raises(RuntimeError, match="no_network"),
    ):
        client.connect(("203.0.113.1", 80))
