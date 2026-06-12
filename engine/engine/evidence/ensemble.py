"""Signal conflict resolver — combine multiple scanner results into a consensus.

Each triggered scanner votes with ``score × edge_weight``, where edge_weight is the
scanner's *validated* historical edge (e.g. calibrated win-rate above the base rate, or
a meta-model's lift), defaulting to 1.0 when unknown. Net LONG vs SHORT conviction sets
direction; opposing evidence weakens or blocks the trade. This is the regime/edge-aware
ensemble — scanners that have proven themselves out-of-sample carry more weight than
unproven ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import ScannerResult, Side


@dataclass(frozen=True)
class Consensus:
    direction: Side
    score: float
    agree: int
    disagree: int
    contributors: list[str]
    action: str  # "trade" | "scalp_only" | "no_trade"
    long_weight: float = 0.0
    short_weight: float = 0.0
    weights_used: dict[str, float] = field(default_factory=dict)


def combine(
    results: list[ScannerResult],
    conflict_tol: float = 0.25,
    edge_weights: dict[str, float] | None = None,
) -> Consensus:
    """Edge-weighted consensus. ``edge_weights`` maps scanner_id -> validated edge multiplier
    (>=0); absent scanners default to 1.0 (neutral). Pass calibrated lift / meta-edge here."""
    edge_weights = edge_weights or {}
    long_w = 0.0
    short_w = 0.0
    contributors: list[str] = []
    used: dict[str, float] = {}
    for r in results:
        if not r.triggered or r.direction in (None, Side.NEUTRAL):
            continue
        w = max(0.0, float(edge_weights.get(r.scanner_id, 1.0)))
        contributors.append(r.scanner_id)
        used[r.scanner_id] = w
        vote = r.score * w
        if r.direction == Side.LONG:
            long_w += vote
        elif r.direction == Side.SHORT:
            short_w += vote

    total = long_w + short_w
    if total == 0:
        return Consensus(Side.NEUTRAL, 0.0, 0, 0, contributors, "no_trade", weights_used=used)

    net = long_w - short_w
    direction = Side.LONG if net > 0 else Side.SHORT
    agree = sum(1 for r in results if r.triggered and r.direction == direction)
    disagree = sum(
        1 for r in results if r.triggered and r.direction not in (None, Side.NEUTRAL, direction)
    )
    score = abs(net) / total

    # Conflict handling: opposing (edge-weighted) evidence weakens or blocks the trade.
    minority = min(long_w, short_w)
    if total > 0 and minority / total > (0.5 - conflict_tol / 2):
        action = "no_trade"
    elif score < 0.4:
        action = "scalp_only"
    else:
        action = "trade"

    return Consensus(
        direction,
        round(score, 3),
        agree,
        disagree,
        contributors,
        action,
        long_weight=round(long_w, 4),
        short_weight=round(short_w, 4),
        weights_used=used,
    )


def edge_weight_from_calibrator(calibrator: dict | None) -> float:
    """Derive an edge multiplier from a fitted calibrator: how much its mid-score
    win-rate beats the base rate (clamped to a sensible band)."""
    if not calibrator or not calibrator.get("fitted"):
        return 1.0
    from ..ml.calibration import ScoreCalibrator

    cal = ScoreCalibrator.from_dict(calibrator)
    edge = cal.apply(0.7) - cal.base_rate  # win-rate lift at a typical trigger score
    return max(0.25, min(2.5, 1.0 + 4.0 * edge))
