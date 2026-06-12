"""Shared helpers for scanner implementations (keep individual scanners terse)."""

from __future__ import annotations

from decimal import Decimal

from ..schemas import (
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    InvalidationRule,
    ScannerResult,
    Side,
)
from .base import ScanContext, Scanner


def clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def ev(
    kind: EvidenceKind,
    label: str,
    value,
    weight: float,
    direction: Side,
    source: str,
    detail: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        kind=kind,
        label=label,
        value=value,
        weight=clip(weight),
        direction=direction,
        source=source,
        detail=detail,
    )


def levels(**kv: float | None) -> dict[str, Decimal]:
    return {k: Decimal(str(round(v, 4))) for k, v in kv.items() if v is not None}


def make_result(
    scanner: Scanner,
    ctx: ScanContext,
    *,
    triggered: bool,
    direction: Side | None,
    score: float,
    classification: str,
    why: str,
    why_now: str,
    invalidation: InvalidationRule,
    evidence_for: list[EvidenceItem] | None = None,
    evidence_against: list[EvidenceItem] | None = None,
    level_map: dict | None = None,
    feature_refs: dict | None = None,
) -> ScannerResult:
    return ScannerResult(
        run_id=ctx.run_id,
        scanner_id=scanner.scanner_id,
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        ts=ctx.snapshot.ts,
        triggered=triggered,
        direction=direction,
        score=clip(score),
        classification=classification,
        levels=level_map or {},
        feature_refs=feature_refs or {},
        evidence=EvidencePacket(
            why=why,
            why_now=why_now,
            evidence_for=evidence_for or [],
            evidence_against=evidence_against or [],
            invalidation=invalidation,
            confidence=clip(score),
        ),
        params=scanner.params,
    )


def flat(
    scanner: Scanner, ctx: ScanContext, classification: str, why: str, kind: str = "price"
) -> ScannerResult:
    return make_result(
        scanner,
        ctx,
        triggered=False,
        direction=None,
        score=0.0,
        classification=classification,
        why=why,
        why_now="—",
        invalidation=InvalidationRule(description="n/a", kind=kind),
    )
