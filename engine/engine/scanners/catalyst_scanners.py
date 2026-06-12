"""Catalyst scanners (§6.4): earnings event risk / post-earnings drift, and the
Catalyst & News Event scanner that decides whether a move has an obvious catalyst.
"""

from __future__ import annotations

from datetime import timedelta

from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner

# Crude headline sentiment lexicon — replaced by an ML classifier in a later phase.
_POSITIVE = {
    "beats",
    "beat",
    "surge",
    "surges",
    "soars",
    "soar",
    "upgrade",
    "upgraded",
    "raises",
    "raised",
    "record",
    "strong",
    "growth",
    "rally",
    "approval",
    "approves",
    "wins",
    "win",
    "partnership",
    "buyback",
    "dividend",
    "outperform",
    "bullish",
    "tops",
}
_NEGATIVE = {
    "miss",
    "misses",
    "plunge",
    "plunges",
    "falls",
    "fall",
    "downgrade",
    "downgraded",
    "cuts",
    "cut",
    "weak",
    "lawsuit",
    "probe",
    "investigation",
    "recall",
    "warning",
    "bankruptcy",
    "layoffs",
    "fraud",
    "halt",
    "halted",
    "underperform",
    "bearish",
    "sinks",
}


def _headline_score(text: str) -> int:
    words = {w.strip(".,:;!?'\"()").lower() for w in text.split()}
    return sum(1 for w in words if w in _POSITIVE) - sum(1 for w in words if w in _NEGATIVE)


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


class CatalystNewsScanner(Scanner):
    scanner_id = "catalyst_news"
    name = "Catalyst & News Event"
    description = (
        "Connects price action to recent headlines: marks whether a move has an obvious "
        "catalyst (and its sentiment lean) or is flow-driven."
    )
    category = "catalyst"
    default_params = {"lookback_hours": 48, "min_items": 1}
    params_schema = {
        "type": "object",
        "properties": {
            "lookback_hours": {"type": "integer", "default": 48},
            "min_items": {"type": "integer", "default": 1},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        if not ctx.news:
            return flat(self, ctx, "no_news_data", "No news data (needs Finnhub key).", "catalyst")
        cutoff = ctx.as_of - timedelta(hours=int(self.params["lookback_hours"]))
        recent = [n for n in ctx.news if n.published_at >= cutoff]
        if len(recent) < int(self.params["min_items"]):
            return flat(
                self,
                ctx,
                "flow_driven",
                "No recent headlines — any move is likely flow-driven.",
                "catalyst",
            )

        scores = [(_headline_score(f"{n.headline} {n.summary or ''}"), n) for n in recent]
        net = sum(s for s, _ in scores)
        pos = sum(1 for s, _ in scores if s > 0)
        neg = sum(1 for s, _ in scores if s < 0)
        top = max(scores, key=lambda sn: abs(sn[0]))[1] if scores else None

        if net == 0 and pos == neg:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=None,
                score=0.4,
                classification="catalyst_mixed",
                why=f"{len(recent)} recent headlines with mixed sentiment ({pos} pos / {neg} neg).",
                why_now="A catalyst exists but the lean is unclear — trade the tape, not the news.",
                invalidation=InvalidationRule(
                    description="A decisive headline lands", kind="catalyst"
                ),
                evidence_for=[
                    ev(EK.CATALYST, "headlines", len(recent), 0.4, Side.NEUTRAL, self.scanner_id)
                ],
            )
        direction = Side.LONG if net > 0 else Side.SHORT
        strength = min(1.0, 0.4 + abs(net) * 0.08 + len(recent) * 0.02)
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=strength,
            classification="catalyst_bullish" if net > 0 else "catalyst_bearish",
            why=(
                f"{len(recent)} headlines in the window lean "
                f"{'bullish' if net > 0 else 'bearish'} (net {net:+d}; {pos} pos / {neg} neg)."
            ),
            why_now=(f'Latest driver: "{top.headline[:90]}"' if top else "Recent news flow."),
            invalidation=InvalidationRule(
                description="News flow flips or is digested", kind="catalyst"
            ),
            evidence_for=[
                ev(EK.CATALYST, "net_sentiment", net, 0.5, direction, self.scanner_id),
                ev(EK.CATALYST, "headline_count", len(recent), 0.25, direction, self.scanner_id),
            ],
        )
