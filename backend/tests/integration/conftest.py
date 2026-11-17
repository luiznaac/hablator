"""Integration harness — the `integrationTest` module equivalent.

Spins up a real MySQL via Testcontainers (needs a Docker daemon) and boots the
actual FastAPI app in-process, driven over ASGI by httpx. External HTTP is
faked per-test with `pytest-httpserver`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.mysql import MySqlContainer

from hablator.application.container import Container
from hablator.application.settings import MySqlConfig, Settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker("integration")


@pytest.fixture(scope="session")
def mysql() -> Iterator[MySqlContainer]:
    with MySqlContainer("mysql:9.4.0") as container:
        yield container


@pytest.fixture(scope="session")
def migrated_mysql(mysql: MySqlContainer) -> MySqlContainer:
    """Apply the schema once for the whole lane (the migration guard has its own container)."""
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
def settings(mysql: MySqlContainer) -> Settings:
    return Settings(
        app_env="test",
        mysql=MySqlConfig(
            host=mysql.get_container_host_ip(),
            port=int(mysql.get_exposed_port(3306)),
            user=mysql.username,
            password=mysql.password,
            database=mysql.dbname,
        ),
    )


@pytest.fixture
async def container(settings: Settings, migrated_mysql: MySqlContainer) -> AsyncIterator[Container]:
    instance = Container(settings)
    try:
        yield instance
    finally:
        await instance.aclose()


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=container.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
