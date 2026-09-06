"""Alembic environment — wired to the app's own `Settings`, not to `alembic.ini`.

**Why the URL is not in `alembic.ini`.** That file is committed. A DSN there means the database
password is committed with it, and it means two sources of truth that drift: the app would connect
using `config.py` while migrations connect using the ini. Reading `get_settings().postgres_dsn`
makes the migration tool obey exactly the same precedence chain as the app (`.env` cascade → real
process env), so `APP_ENV=staging alembic upgrade head` targets staging with no extra wiring.

`postgres_dsn` is a `SecretStr`, so the password is unwrapped here on one visible line rather than
being carried around in plain text.

**Running it.** Inside the container, `POSTGRES_HOST=db` resolves via the compose network. From your
host, the compose port mapping means you want `POSTGRES_HOST=localhost`:

    POSTGRES_HOST=localhost uv run alembic upgrade head

**Sync, not async, on purpose.** Migrations are a short-lived batch job run at deploy time; they get
no benefit from an async driver and it costs a `asyncio.run` wrapper plus a second engine
configuration. The app's own runtime engine (Step 2) is the one that needs to be async.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from alembic import context
from app.core.config import get_settings

# Importing the models package registers every table on `SQLModel.metadata`, which is what
# `--autogenerate` diffs against the live database. It is empty until Step 2 adds the first entity;
# the import exists now so a new model is picked up by being defined, not by anyone remembering to
# edit this file.
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    """The one place a migration learns where to connect — the app's settings, never the ini."""
    return get_settings().postgres_dsn.get_secret_value()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (`alembic upgrade head --sql`).

    This is how a change gets reviewed, or handed to a DBA, before it touches a regulated database —
    which is the mode Step 18's change-management story depends on.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and run migrations for real."""
    # NullPool: this process runs a handful of statements and exits. A pool would hold connections
    # open past the work and can leave a migration container lingering on shutdown.
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without these two, autogenerate silently ignores a column whose *type* or *nullability*
            # changed and only notices added/dropped columns -- so `str` -> `Numeric` would produce
            # an empty migration and a schema that quietly disagrees with the models.
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
