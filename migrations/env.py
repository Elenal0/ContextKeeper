"""
Alembic environment — reads DATABASE_URL from env/settings so the same
env.py works identically in local dev, Docker, and Fly.io.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Make sure 'app' package is importable ────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Pull SQLAlchemy metadata from our models ──────────────────────────────────
from app.db.base import Base  # noqa: E402  — must come after sys.path fix
from app.db import models as _models  # noqa: F401  — ensures all models are registered
from app.config import settings  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url with the runtime DATABASE_URL env var
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # needed for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Enable WAL and foreign keys for SQLite
        if settings.DATABASE_URL.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # needed for SQLite ALTER TABLE support
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
