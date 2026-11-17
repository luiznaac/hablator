"""The integration harness probes Docker and fails loudly — it never auto-skips."""

from __future__ import annotations

import pytest

from tests.docker_probe import DockerUnavailableError, require_docker


class _Reachable:
    def ping(self) -> bool:
        return True


class _Unreachable:
    def ping(self) -> bool:
        raise RuntimeError("cannot connect to the Docker daemon")


def test_require_docker_passes_when_the_daemon_answers() -> None:
    require_docker(_Reachable)


def test_require_docker_raises_an_actionable_error_when_the_daemon_is_unreachable() -> None:
    with pytest.raises(DockerUnavailableError) as excinfo:
        require_docker(_Unreachable)

    message = str(excinfo.value)
    assert "Docker daemon" in message
    assert "uv run poe test-integration" in message
    assert "cannot connect to the Docker daemon" in message
