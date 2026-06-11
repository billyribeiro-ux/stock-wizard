"""Evidence / explainability contracts — the "why" behind every signal.

The blueprint mandates that no signal is a bare arrow: each carries why, why-now,
ranked evidence for and against, an invalidation condition, and historical analogs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import EvidenceKind, Side


class EvidenceItem(BaseModel):
    """A single piece of weighted evidence for or against a thesis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EvidenceKind
    label: str
    value: float | str
    weight: float = Field(ge=0.0, le=1.0, description="Relative importance 0..1")
    direction: Side = Field(description="LONG/SHORT lean this item supports (NEUTRAL if context)")
    source: str = "engine"
    detail: str | None = None


class Analog(BaseModel):
    """A historically similar setup. forward_return/outcome filled by the ML phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    symbol: str
    similarity: float = Field(ge=0.0, le=1.0)
    outcome: str | None = None
    forward_return: float | None = None


class InvalidationRule(BaseModel):
    """Structured invalidation: human text plus a machine-checkable condition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str
    kind: str = Field(description="price | time | structure | internals | options")
    level: float | None = None
    comparator: str | None = Field(default=None, description="lt | gt | crosses")
    expires_at: datetime | None = None


class EvidencePacket(BaseModel):
    """Full explanation object attached to a ScannerResult / SignalPacket."""

    model_config = ConfigDict(extra="forbid")

    why: str = Field(description="One-paragraph trade thesis")
    why_now: str = Field(description="The trigger condition that just fired")
    evidence_for: list[EvidenceItem] = Field(default_factory=list)
    evidence_against: list[EvidenceItem] = Field(default_factory=list)
    invalidation: InvalidationRule
    historical_analogs: list[Analog] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def net_evidence_weight(self) -> float:
        """Sum(for weights) - Sum(against weights); a quick conflict gauge."""
        return sum(e.weight for e in self.evidence_for) - sum(
            e.weight for e in self.evidence_against
        )
