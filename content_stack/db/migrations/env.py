"""Alembic environment.

Reads the DB URL from `Settings.db_path` (env-overridable via
`CONTENT_STACK_*`) instead of `alembic.ini`. Importing
`content_stack.db.models` registers all 30 tables on
`SQLModel.metadata`, which Alembic's autogenerate uses as the target.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# Importing the models package as a side effect populates
# `SQLModel.metadata` with the 30 table definitions. Without this,
# `alembic check` and autogenerate run against an empty metadata.
import content_stack.db.models  # noqa: F401  (import for side effect)
from content_stack.config import get_settings
from content_stack.db.connection import make_engine

# this is the Alembic Config object, which provides access to values within
# the .ini file in use.
config = context.config

# Configure stdlib logging from alembic.ini if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `target_metadata` drives autogenerate. SQLModel.metadata is empty until M1
# imports models; that's intentional — M0 ships an empty initial migration.
target_metadata = SQLModel.metadata


def _resolve_db_url() -> str:
    """Resolve the DB URL from settings unless alembic.ini overrides it."""
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    settings = get_settings()
    settings.ensure_dirs()
    return f"sqlite:///{settings.db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout, no DB connection."""
    url = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a fresh engine + WAL PRAGMAs."""
    settings = get_settings()
    settings.ensure_dirs()
    engine = make_engine(settings.db_path)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
