"""Alembic environment — wired to the app's own `Settings` and `Base.metadata` rather than
duplicating the DB URL or the table list in `alembic.ini`.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Populates Base.metadata as a side effect of import — there is no aggregate "models" module (see
# persistence/configuration/base.py), so every entity module is imported explicitly here. Add a
# new one whenever a new persistence/<feature>/entity.py is added.
from hablator.persistence.channel.entity import ProviderConfigEntity, RetryPolicyEntity  # noqa: F401
from hablator.persistence.configuration.base import Base
from hablator.persistence.notification.entity import (  # noqa: F401
    AttemptEntity,
    DeliveryEntity,
    NotificationEntity,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging. Keep the app's already-configured
# loggers alive: the default (`disable_existing_loggers=True`) disables every
# logger created before this runs, which strands telemetry when a migration runs
# in-process (tests, `poe migrate`).
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _mysql_url() -> str:
    # Imported lazily so `alembic` commands that don't touch the DB (e.g. `alembic history`)
    # never require MYSQL__* to be set. `DatabaseSettings` is the DB half only: migrations must
    # not require the app's provider key or API token.
    from hablator.application.settings import DatabaseSettings

    return DatabaseSettings().mysql.url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=_mysql_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    The app only ever talks to MySQL over `asyncmy` (see persistence/configuration/database.py),
    so this uses Alembic's async recipe — a sync DBAPI URL/driver is never introduced just for
    migrations.
    """
    connectable = async_engine_from_config(
        {"sqlalchemy.url": _mysql_url()},
        prefix="sqlalchemy.",
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
