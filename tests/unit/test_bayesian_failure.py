"""Bayesian evidence scoring + failure analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from engine.backtesting import analyze_failures
from engine.evidence import confidence_band, posterior_probability
from engine.schemas import (
    EvidenceItem,
    EvidencePacket,
    InvalidationRule,
    Side,
    TradeRecord,
)

NOW = datetime(2026, 6, 11, tzinfo=UTC)


def _packet(for_w, against_w):
    return EvidencePacket(
        why="w",
        why_now="n",
        evidence_for=[
            EvidenceItem(kind="options", label=f"f{i}", value=1, weight=w, direction=Side.LONG)
            for i, w in enumerate(for_w)
        ],
        evidence_against=[
            EvidenceItem(kind="volume", label=f"a{i}", value=1, weight=w, direction=Side.SHORT)
            for i, w in enumerate(against_w)
        ],
        invalidation=InvalidationRule(description="x", kind="price"),
        confidence=0.5,
    )


def test_posterior_rises_with_supporting_evidence():
    base = posterior_probability(_packet([], []), prior=0.5)
    strong = posterior_probability(_packet([0.6, 0.5], []), prior=0.5)
    assert abs(base - 0.5) < 1e-9
    assert strong > 0.7


def test_posterior_falls_with_opposing_evidence():
    weak = posterior_probability(_packet([], [0.6, 0.5]), prior=0.5)
    assert weak < 0.3


def test_posterior_bounded():
    p = posterior_probability(_packet([1, 1, 1, 1], []), prior=0.9)
    assert 0.0 < p < 1.0


def test_confidence_band_widens_with_conflict():
    calm_lo, calm_hi = confidence_band(_packet([0.6], []))
    conf_lo, conf_hi = confidence_band(_packet([0.6], [0.5, 0.5]))
    assert (conf_hi - conf_lo) > 0  # has width
    assert (conf_hi - conf_lo) >= (calm_hi - calm_lo)  # opposing evidence widens it


def _trade(pnl, mfe, mae, reason):
    return TradeRecord(
        symbol="X",
        side=Side.LONG,
        entry_ts=NOW,
        entry_price=Decimal("100"),
        exit_ts=NOW,
        exit_price=Decimal("99"),
        pnl=Decimal(str(pnl)),
        mfe=mfe,
        mae=mae,
        exit_reason=reason,
    )


def test_failure_analysis_tags_and_aggregates():
    trades = [
        _trade(-50, 5.0, -6.0, "stop"),  # gave back gains
        _trade(-40, 0.2, -5.0, "stop"),  # wrong direction
        _trade(-10, 1.0, -1.0, "time_stop"),  # no follow through
        _trade(120, 8.0, -1.0, "target"),  # winner (ignored)
    ]
    fa = analyze_failures(trades)
    assert fa.total == 4
    assert fa.losers == 3
    assert sum(fa.reason_counts.values()) == 3
    assert "no_follow_through" in fa.reason_counts
    assert fa.worst_trade is not None and fa.worst_trade["pnl"] == -50.0
