"""Alembic environment — uses the sync DB URL from common settings."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the storage package importable when alembic runs from storage/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.models import Base

try:
    from common.settings import get_settings

    _DB_URL = get_settings().database_url_sync
except Exception:  # pragma: no cover - settings optional at migration time
    _DB_URL = "postgresql+psycopg://wizard:wizard@localhost:5432/stockwizard"

config = context.config
config.set_main_option("sqlalchemy.url", _DB_URL)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": _DB_URL}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
