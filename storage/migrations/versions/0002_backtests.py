"""add backtests table

Revision ID: 0002_backtests
Revises: 0001_initial
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
from schemas.models import Backtest

revision = "0002_backtests"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Backtest.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Backtest.__table__.drop(bind=op.get_bind(), checkfirst=True)
