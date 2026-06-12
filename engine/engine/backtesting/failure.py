"""Failure analysis — learn from losing/weak trades.

Tags each non-winning trade with a likely failure reason from its excursions and exit,
then aggregates. This feeds the self-learning loop (which thresholds/filters to tighten)
per the blueprint's "learn from failures, not only winners" mandate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..schemas import TradeRecord


@dataclass
class FailureAnalysis:
    total: int
    losers: int
    reason_counts: dict[str, int]
    tagged: list[dict] = field(default_factory=list)
    worst_trade: dict | None = None


def _tag(t: TradeRecord) -> str:
    mfe = t.mfe or 0.0
    mae = t.mae or 0.0
    reason = "no_edge"
    if t.exit_reason == "time_stop":
        reason = "no_follow_through"
    elif t.exit_reason == "stop":
        # Had meaningful favorable excursion before stopping out => gave back gains.
        if mfe > 0 and abs(mae) > 0 and mfe >= 0.8 * abs(mae):
            reason = "gave_back_gains"
        elif mfe <= 0.2 * abs(mae):
            reason = "wrong_direction"
        else:
            reason = "stopped_then_reversed"
    elif t.exit_reason == "end_of_data":
        reason = "unresolved_at_end"
    return reason


def analyze_failures(trades: list[TradeRecord]) -> FailureAnalysis:
    losers = [t for t in trades if t.pnl is not None and float(t.pnl) <= 0]
    counts: Counter[str] = Counter()
    tagged: list[dict] = []
    for t in losers:
        r = _tag(t)
        counts[r] += 1
        tagged.append(
            {
                "symbol": t.symbol,
                "side": t.side.value,
                "entry_ts": t.entry_ts.isoformat(),
                "pnl": float(t.pnl) if t.pnl is not None else None,
                "mfe": t.mfe,
                "mae": t.mae,
                "exit_reason": t.exit_reason,
                "failure": r,
            }
        )
    worst = min(
        (t for t in trades if t.pnl is not None),
        key=lambda t: float(t.pnl),
        default=None,
    )
    worst_d = None
    if worst is not None:
        worst_d = {
            "symbol": worst.symbol,
            "pnl": float(worst.pnl) if worst.pnl else None,
            "exit_reason": worst.exit_reason,
            "failure": _tag(worst),
        }
    return FailureAnalysis(
        total=len(trades),
        losers=len(losers),
        reason_counts=dict(counts),
        tagged=tagged,
        worst_trade=worst_d,
    )
