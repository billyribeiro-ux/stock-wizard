"""Insider & Congress Flow scanner (catalyst / §6.4).

Aggregates recent corporate-insider transactions (SEC EDGAR Form 4 / Finnhub) and US
congressional trades (Finnhub) into a directional "smart-money" flow signal: clustered
buying by insiders/representatives is bullish evidence, clustered selling bearish.
Treated as catalyst confirmation, not a standalone entry.
"""

from __future__ import annotations

from datetime import timedelta

from ..schemas import (
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    InvalidationRule,
    ScannerResult,
    Side,
)
from .base import ScanContext, Scanner


class InsiderCongressScanner(Scanner):
    scanner_id = "insider_congress_flow"
    name = "Insider & Congress Flow"
    description = (
        "Aggregates SEC Form 4 insider trades and congressional disclosures into a "
        "directional smart-money flow score over a recent window."
    )
    category = "catalyst"
    default_params = {"lookback_days": 90, "min_events": 2, "congress_weight": 1.5}
    params_schema = {
        "type": "object",
        "properties": {
            "lookback_days": {
                "type": "integer",
                "minimum": 7,
                "maximum": 365,
                "default": 90,
                "title": "Lookback window (days)",
            },
            "min_events": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 2,
                "title": "Min events to trigger",
            },
            "congress_weight": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 5,
                "default": 1.5,
                "title": "Weight of a congress trade vs an insider trade",
            },
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        lookback = int(self._p("lookback_days", ctx))
        min_events = int(self._p("min_events", ctx))
        cong_w = float(self._p("congress_weight", ctx))
        cutoff = ctx.as_of.date() - timedelta(days=lookback)

        insider = [t for t in ctx.insider if t.transaction_date >= cutoff]
        congress = [t for t in ctx.congress if t.transaction_date >= cutoff]

        buy_score = 0.0
        sell_score = 0.0
        buyers: set[str] = set()
        sellers: set[str] = set()

        for t in insider:
            w = 1.0
            if t.side == Side.LONG:
                buy_score += w
                buyers.add(t.insider_name)
            elif t.side == Side.SHORT:
                sell_score += w
                sellers.add(t.insider_name)
        for t in congress:
            if t.side == Side.LONG:
                buy_score += cong_w
                buyers.add(t.representative)
            elif t.side == Side.SHORT:
                sell_score += cong_w
                sellers.add(t.representative)

        n_events = len(insider) + len(congress)
        net = buy_score - sell_score
        total = buy_score + sell_score

        triggered = n_events >= min_events and abs(net) > 0
        direction: Side | None = None
        classification = "no_flow"
        if triggered:
            direction = Side.LONG if net > 0 else Side.SHORT
            classification = "insider_accumulation" if net > 0 else "insider_distribution"

        ev_for: list[EvidenceItem] = []
        ev_against: list[EvidenceItem] = []
        if buy_score > 0:
            ev = EvidenceItem(
                kind=EvidenceKind.CATALYST,
                label="buy_flow",
                value=round(buy_score, 1),
                weight=_w(buy_score, total),
                direction=Side.LONG,
                source="insider_congress",
                detail=f"{len(buyers)} unique buyers",
            )
            (ev_for if net > 0 else ev_against).append(ev)
        if sell_score > 0:
            ev = EvidenceItem(
                kind=EvidenceKind.CATALYST,
                label="sell_flow",
                value=round(sell_score, 1),
                weight=_w(sell_score, total),
                direction=Side.SHORT,
                source="insider_congress",
                detail=f"{len(sellers)} unique sellers",
            )
            (ev_for if net < 0 else ev_against).append(ev)
        if congress:
            ev_for.append(
                EvidenceItem(
                    kind=EvidenceKind.CATALYST,
                    label="congress_trades",
                    value=len(congress),
                    weight=0.2,
                    direction=direction or Side.NEUTRAL,
                    source="insider_congress",
                )
            )

        score = _clip((abs(net) / total) if total > 0 else 0.0) * _clip(n_events / (min_events * 3))

        evidence = EvidencePacket(
            why=(
                f"Over {lookback}d: buy flow {buy_score:.1f} vs sell flow {sell_score:.1f} "
                f"across {n_events} insider/congress events."
            ),
            why_now=(
                f"Net smart-money flow is {'bullish' if net > 0 else 'bearish'} "
                f"({len(buyers)} buyers / {len(sellers)} sellers)."
                if triggered
                else "No clustered insider/congress flow in the window."
            ),
            evidence_for=ev_for,
            evidence_against=ev_against,
            invalidation=InvalidationRule(
                description="Flow reverses (net selling overtakes buying) over the window",
                kind="catalyst",
            ),
            confidence=score,
        )

        return ScannerResult(
            run_id=ctx.run_id,
            scanner_id=self.scanner_id,
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            ts=ctx.snapshot.ts,
            triggered=triggered,
            direction=direction,
            score=score,
            classification=classification,
            feature_refs={
                "buy_flow": buy_score,
                "sell_flow": sell_score,
                "events": float(n_events),
            },
            evidence=evidence,
            params=self.params,
        )


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _w(part: float, total: float) -> float:
    return _clip((part / total) * 0.6) if total > 0 else 0.0
