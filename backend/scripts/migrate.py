"""Applies pending Alembic migrations to the configured database.

Hablator's schema history starts at an empty `0001_baseline`, and the service that predates it
(`hablator.py`) kept no database at all — so there is no legacy schema to baseline: every
database this script meets is either empty or already versioned. `upgrade head` covers both.

Run via `uv run poe migrate` locally, or from `deploy/entrypoint.sh` in the container — never
from the app itself; a failed migration must abort the container instead of serving traffic
against a stale schema.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
