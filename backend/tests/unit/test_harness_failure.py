"""Without a Docker daemon the integration lane exits non-zero with the actionable message."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_integration_lane_exits_non_zero_when_docker_is_absent() -> None:
    environment = {**os.environ, "DOCKER_HOST": "unix:///nonexistent/docker.sock"}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/integration/test_migrations.py", "-q", "--no-header"],
        cwd=_BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "The integration suite needs a reachable Docker daemon" in output
    assert "uv run poe test-integration" in output
