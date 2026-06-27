"""add alert_rules and alert_events tables

Revision ID: 0003_alerts
Revises: 0002_backtests
Create Date: 2026-06-11
"""

from __future__ import annotations

from typing import cast

from alembic import op
from schemas.models import AlertEventRow, AlertRuleRow
from sqlalchemy import Table

revision = "0003_alerts"
down_revision = "0002_backtests"
branch_labels = None
depends_on = None

_rules = cast(Table, AlertRuleRow.__table__)
_events = cast(Table, AlertEventRow.__table__)


def upgrade() -> None:
    bind = op.get_bind()
    _rules.create(bind=bind, checkfirst=True)
    _events.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    _events.drop(bind=bind, checkfirst=True)
    _rules.drop(bind=bind, checkfirst=True)
