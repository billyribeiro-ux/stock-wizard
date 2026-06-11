"""Scanner output + descriptor contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import Side, Timeframe
from .evidence import EvidencePacket


class ScannerSpec(BaseModel):
    """Self-describing scanner metadata exposed to the dashboard."""

    model_config = ConfigDict(extra="forbid")

    scanner_id: str
    name: str
    description: str
    category: str = Field(description="e.g. structure | volume | options_gamma | internals")
    params_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema of the scanner's params"
    )
    default_params: dict[str, Any] = Field(default_factory=dict)


class ScannerResult(BaseModel):
    """One scanner's verdict for one symbol/timeframe at one point in time."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID | None = None
    scanner_id: str
    symbol: str
    timeframe: Timeframe
    ts: datetime
    triggered: bool
    direction: Side | None = None
    score: float = Field(ge=0.0, le=1.0, description="Confidence 0..1")
    classification: str = Field(
        description="Scanner-specific label, e.g. 'reversal_long', 'no_trade'"
    )
    levels: dict[str, Decimal] = Field(
        default_factory=dict, description="Named price levels: entry/poc/wall/flip/..."
    )
    feature_refs: dict[str, float | None] = Field(
        default_factory=dict, description="Snapshot of key feature inputs"
    )
    evidence: EvidencePacket
    params: dict[str, Any] = Field(default_factory=dict)
