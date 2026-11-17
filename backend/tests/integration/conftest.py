"""Integration harness — the `integrationTest` module equivalent.

Spins up a real MySQL via Testcontainers (needs a Docker daemon), migrates it to head, and
boots the actual FastAPI app in-process, driven over ASGI by httpx. External HTTP is faked
per-test with `pytest-httpserver`.

Docker absence fails the run non-zero with an actionable message — it never auto-skips.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from testcontainers.mysql import MySqlContainer

from hablator.application.container import Container
from hablator.application.settings import MySqlConfig, Settings
from hablator.persistence.configuration.base import Base
from tests.docker_probe import DockerUnavailableError, require_docker

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker("integration")


@pytest.fixture(scope="session", autouse=True)
def _docker_daemon() -> None:
    try:
        require_docker()
    except DockerUnavailableError as error:
        pytest.exit(str(error), returncode=1)


@pytest.fixture(scope="session")
def mysql() -> Iterator[MySqlContainer]:
    with MySqlContainer("mysql:9.4.0") as container:
        yield container


@pytest.fixture(scope="session")
def migrated_database(mysql: MySqlContainer) -> MySqlContainer:
    env = {
        "MYSQL__HOST": mysql.get_container_host_ip(),
        "MYSQL__PORT": str(mysql.get_exposed_port(3306)),
        "MYSQL__USER": mysql.username,
        "MYSQL__PASSWORD": mysql.password,
        "MYSQL__DATABASE": mysql.dbname,
    }
    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    try:
        config = Config(str(_BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
        command.upgrade(config, "head")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return mysql


@pytest.fixture
def settings(migrated_database: MySqlContainer) -> Settings:
    return Settings(
        app_env="test",
        mysql=MySqlConfig(
            host=migrated_database.get_container_host_ip(),
            port=int(migrated_database.get_exposed_port(3306)),
            user=migrated_database.username,
            password=migrated_database.password,
            database=migrated_database.dbname,
        ),
    )


@pytest.fixture
async def container(settings: Settings) -> AsyncIterator[Container]:
    instance = Container(settings)
    try:
        yield instance
    finally:
        await instance.aclose()


@pytest.fixture
async def repositories(container: Container) -> AsyncIterator[Container]:
    """A container whose migrated schema starts empty for every test."""
    async with container.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"DELETE FROM `{table.name}`"))
    yield container


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=container.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
