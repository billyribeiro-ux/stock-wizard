"""Signal conflict resolver — combine multiple scanner results into a consensus.

A first-pass ensemble: weight each triggered scanner by its score, net LONG vs SHORT
conviction, and decide a final action (or no-trade when evidence conflicts). The full
regime-aware, calibrated ensemble lands in the ML phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import ScannerResult, Side


@dataclass(frozen=True)
class Consensus:
    direction: Side
    score: float
    agree: int
    disagree: int
    contributors: list[str]
    action: str  # "trade" | "scalp_only" | "no_trade"


def combine(results: list[ScannerResult], conflict_tol: float = 0.25) -> Consensus:
    long_w = 0.0
    short_w = 0.0
    contributors: list[str] = []
    for r in results:
        if not r.triggered or r.direction in (None, Side.NEUTRAL):
            continue
        contributors.append(r.scanner_id)
        if r.direction == Side.LONG:
            long_w += r.score
        elif r.direction == Side.SHORT:
            short_w += r.score

    total = long_w + short_w
    if total == 0:
        return Consensus(Side.NEUTRAL, 0.0, 0, 0, contributors, "no_trade")

    net = long_w - short_w
    direction = Side.LONG if net > 0 else Side.SHORT
    agree = sum(1 for r in results if r.triggered and r.direction == direction)
    disagree = sum(
        1 for r in results if r.triggered and r.direction not in (None, Side.NEUTRAL, direction)
    )
    score = abs(net) / total

    # Conflict handling: opposing evidence weakens or blocks the trade.
    minority = min(long_w, short_w)
    if total > 0 and minority / total > (0.5 - conflict_tol / 2):
        action = "no_trade"
    elif score < 0.4:
        action = "scalp_only"
    else:
        action = "trade"

    return Consensus(direction, round(score, 3), agree, disagree, contributors, action)
