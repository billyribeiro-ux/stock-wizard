"""Catalyst scanners (§6.4): Earnings & Guidance event risk + post-earnings drift."""

from __future__ import annotations

from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


class EarningsGuidanceScanner(Scanner):
    scanner_id = "earnings_guidance"
    name = "Earnings & Guidance"
    description = (
        "Flags imminent earnings event risk and post-earnings drift from the EPS surprise."
    )
    category = "catalyst"
    default_params = {"event_window_days": 5, "drift_window_days": 3}
    params_schema = {
        "type": "object",
        "properties": {
            "event_window_days": {"type": "integer", "default": 5},
            "drift_window_days": {"type": "integer", "default": 3},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        if not ctx.earnings:
            return flat(
                self, ctx, "no_earnings_data", "No earnings data (needs Finnhub key).", "catalyst"
            )
        today = ctx.as_of.date()
        ew = self.params["event_window_days"]
        dw = self.params["drift_window_days"]

        # Upcoming earnings within the event window -> event risk (caution / no directional edge).
        upcoming = sorted(
            (e for e in ctx.earnings if e.date >= today and (e.date - today).days <= ew),
            key=lambda e: e.date,
        )
        if upcoming:
            e = upcoming[0]
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=None,
                score=0.5,
                classification="earnings_event_risk",
                why=f"Earnings on {e.date.isoformat()} ({e.hour or 'time TBD'}) — binary event risk ahead.",
                why_now=f"{(e.date - today).days} day(s) to the report; size down / avoid naked directionals.",
                invalidation=InvalidationRule(
                    description="Earnings pass / event window clears",
                    kind="catalyst",
                    expires_at=None,
                ),
                evidence_for=[
                    ev(
                        EK.CATALYST,
                        "days_to_earnings",
                        (e.date - today).days,
                        0.6,
                        Side.NEUTRAL,
                        self.scanner_id,
                    )
                ],
            )

        # Recent earnings within the drift window -> post-earnings drift from the surprise.
        recent = sorted(
            (e for e in ctx.earnings if e.date <= today and (today - e.date).days <= dw),
            key=lambda e: e.date,
            reverse=True,
        )
        for e in recent:
            if e.eps_actual is not None and e.eps_estimate is not None:
                surprise = e.eps_actual - e.eps_estimate
                if abs(surprise) <= 1e-9:
                    continue
                direction = Side.LONG if surprise > 0 else Side.SHORT
                mag = abs(surprise) / (abs(e.eps_estimate) + 1e-9)
                return make_result(
                    self,
                    ctx,
                    triggered=True,
                    direction=direction,
                    score=min(1.0, 0.4 + mag),
                    classification="post_earnings_drift",
                    why=f"EPS {'beat' if surprise > 0 else 'miss'} on {e.date.isoformat()} "
                    f"({e.eps_actual} vs {e.eps_estimate}); drift tends to persist.",
                    why_now=f"{(today - e.date).days} day(s) since the report.",
                    invalidation=InvalidationRule(
                        description="Drift fades / gap fills", kind="catalyst"
                    ),
                    evidence_for=[
                        ev(
                            EK.CATALYST,
                            "eps_surprise",
                            round(surprise, 4),
                            0.6,
                            direction,
                            self.scanner_id,
                        )
                    ],
                )
        return flat(self, ctx, "no_event", "No imminent or recent earnings catalyst.", "catalyst")
