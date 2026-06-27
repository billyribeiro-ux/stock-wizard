"""add backtests table

Revision ID: 0002_backtests
Revises: 0001_initial
Create Date: 2026-06-11
"""

from __future__ import annotations

from typing import cast

from alembic import op
from schemas.models import Backtest
from sqlalchemy import Table

revision = "0002_backtests"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_backtest = cast(Table, Backtest.__table__)


def upgrade() -> None:
    _backtest.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    _backtest.drop(bind=op.get_bind(), checkfirst=True)
