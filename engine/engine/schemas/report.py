"""Report request contract (CSV/PDF export)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import ReportFormat, ReportKind


class ReportSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: UUID = Field(default_factory=uuid4)
    kind: ReportKind
    format: ReportFormat
    subject_ids: list[UUID] = Field(
        default_factory=list, description="IDs of results/signals/backtests to include"
    )
    run_id: UUID | None = None
    columns: list[str] | None = None
    title: str = "Stock Wizard Report"
    template: str | None = None
    generated_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
