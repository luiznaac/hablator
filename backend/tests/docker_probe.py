"""The integration harness's Docker probe.

Testcontainers would fail on its own with an opaque driver error; this probe turns a missing
daemon into one actionable message and a non-zero exit. It never skips the suite.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import docker


class DockerUnavailableError(RuntimeError):
    """The Docker daemon needed by the integration lane is not reachable."""


class _DockerClient(Protocol):
    def ping(self) -> bool: ...


_MESSAGE = (
    "The integration suite needs a reachable Docker daemon to start MySQL 9.4.0 via Testcontainers. "
    "Start Docker (for example `sudo systemctl start docker`) and re-run `uv run poe test-integration`."
)


def require_docker(connect: Callable[[], _DockerClient] | None = None) -> None:
    """Probe the Docker daemon; raise `DockerUnavailableError` with the original cause attached."""
    factory = connect or docker.from_env
    try:
        factory().ping()
    except Exception as exc:
        raise DockerUnavailableError(f"{_MESSAGE} Cause: {exc}") from exc
