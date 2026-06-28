"""initial schema + timescale hypertables

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
from schemas.models import HYPERTABLES, Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # TimescaleDB gives us hypertables in production; it is optional for dev/CI/test, where a
    # plain Postgres works fine. Probe availability *before* CREATE EXTENSION — a failed
    # CREATE would poison the migration transaction — and degrade gracefully when absent.
    available = bind.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'"
    ).scalar()
    has_timescale = False
    if available is not None:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        has_timescale = True

    # Create all ORM tables.
    Base.metadata.create_all(bind=bind)

    # Convert the time-series tables into hypertables (only when TimescaleDB is present).
    if has_timescale:
        for table, time_col in HYPERTABLES.items():
            op.execute(
                f"SELECT create_hypertable('{table}', '{time_col}', "
                f"if_not_exists => TRUE, migrate_data => TRUE)"
            )

    # Helpful descending index for latest-bar lookups.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ohlcv_symbol_tf_ts ON ohlcv (symbol, timeframe, ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_option_chains_underlying_asof "
        "ON option_chains (underlying, as_of DESC)"
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
