"""add alert_rules and alert_events tables

Revision ID: 0003_alerts
Revises: 0002_backtests
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
from schemas.models import AlertEventRow, AlertRuleRow

revision = "0003_alerts"
down_revision = "0002_backtests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    AlertRuleRow.__table__.create(bind=bind, checkfirst=True)
    AlertEventRow.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    AlertEventRow.__table__.drop(bind=bind, checkfirst=True)
    AlertRuleRow.__table__.drop(bind=bind, checkfirst=True)
