"""Cross-asset / volatility scanners that read peer symbols from ctx.aux.

The scan orchestrator populates ctx.aux with peers (^VIX, SPY, QQQ, IWM, TLT, ...).
When a needed peer is absent these degrade gracefully to a data-quality no-trade.
"""

from __future__ import annotations

from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


def _returns(ohlcv, n=20):
    if ohlcv is None or len(ohlcv) < n + 1:
        return None
    df = ohlcv_to_frame(ohlcv)
    return df["close"].pct_change().dropna()


class VixTailRiskScanner(Scanner):
    scanner_id = "vix_tail_risk"
    name = "VIX / VVIX / MOVE Tail Risk"
    description = "Volatility stress: rising VIX and VIX-vs-equity divergence flag risk-off."
    category = "volatility"
    default_params = {"vix_spike_pct": 0.08}
    params_schema = {
        "type": "object",
        "properties": {"vix_spike_pct": {"type": "number", "default": 0.08}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        vix = ctx.aux.get("^VIX")
        if vix is None or len(vix) < 5:
            return flat(self, ctx, "no_vix_data", "VIX data unavailable.", "internals")
        vdf = ohlcv_to_frame(vix)
        vix_chg = float(vdf["close"].iloc[-1] / vdf["close"].iloc[-2] - 1)
        vix_level = float(vdf["close"].iloc[-1])
        spike = vix_chg >= self.params["vix_spike_pct"]
        elevated = vix_level >= 20
        if spike or (elevated and vix_chg > 0):
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=min(1.0, 0.4 + abs(vix_chg) * 3),
                classification="risk_off",
                why=f"VIX is signaling stress (level {vix_level:.1f}, {vix_chg:+.1%}).",
                why_now="Volatility spiking — equity risk skewed to the downside.",
                invalidation=InvalidationRule(
                    description="VIX rolls back over / equities stabilize", kind="internals"
                ),
                evidence_for=[
                    ev(
                        EK.INTERNAL,
                        "vix_change",
                        round(vix_chg, 4),
                        0.6,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                    ev(
                        EK.INTERNAL,
                        "vix_level",
                        round(vix_level, 1),
                        0.3,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                ],
            )
        return make_result(
            self,
            ctx,
            triggered=False,
            direction=None,
            score=0.3,
            classification="risk_on",
            why=f"VIX calm (level {vix_level:.1f}, {vix_chg:+.1%}).",
            why_now="No volatility stress.",
            invalidation=InvalidationRule(description="VIX spikes", kind="internals"),
        )


class IndexDivergenceScanner(Scanner):
    scanner_id = "index_divergence"
    name = "Index Leadership Divergence"
    description = "Flags when the symbol diverges from the broad index (SPY) leadership."
    category = "volatility"
    default_params = {"peer": "SPY", "window": 20}
    params_schema = {
        "type": "object",
        "properties": {
            "peer": {"type": "string", "default": "SPY"},
            "window": {"type": "integer", "default": 20},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        peer = ctx.aux.get(self.params["peer"])
        own = _returns(ctx.ohlcv, self.params["window"])
        peer_r = _returns(peer, self.params["window"])
        if own is None or peer_r is None:
            return flat(self, ctx, "no_peer_data", "Peer index data unavailable.", "internals")
        n = self.params["window"]
        own_cum = float((1 + own.iloc[-n:]).prod() - 1)
        peer_cum = float((1 + peer_r.iloc[-n:]).prod() - 1)
        rs = own_cum - peer_cum
        if abs(rs) < 0.01:
            return flat(self, ctx, "in_line", "Moving in line with the index.", "internals")
        direction = Side.LONG if rs > 0 else Side.SHORT
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, abs(rs) * 10),
            classification="outperformance" if rs > 0 else "underperformance",
            why=f"{ctx.symbol} is {'leading' if rs > 0 else 'lagging'} {self.params['peer']} by {rs:+.1%}.",
            why_now=f"{n}-bar relative strength = {rs:+.1%}.",
            invalidation=InvalidationRule(
                description="Relative strength reverts", kind="internals"
            ),
            evidence_for=[
                ev(EK.INTERNAL, "rel_strength", round(rs, 4), 0.6, direction, self.scanner_id)
            ],
        )


class CrossAssetRiskScanner(Scanner):
    scanner_id = "cross_asset_risk"
    name = "Cross-Asset Risk-On/Risk-Off"
    description = "Macro risk gauge from equities vs bonds (TLT) and volatility (^VIX)."
    category = "volatility"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        spy = _returns(ctx.aux.get("SPY"), 5)
        tlt = _returns(ctx.aux.get("TLT"), 5)
        vix = ctx.aux.get("^VIX")
        if spy is None and ctx.ohlcv is not None:
            spy = _returns(ctx.ohlcv, 5)
        if spy is None:
            return flat(self, ctx, "no_data", "Insufficient cross-asset data.", "internals")
        spy_5 = float((1 + spy.iloc[-5:]).prod() - 1)
        score = 0.0
        bits = []
        if spy_5 > 0:
            score += 1
            bits.append("equities up")
        if tlt is not None:
            tlt_5 = float((1 + tlt.iloc[-5:]).prod() - 1)
            if tlt_5 < 0:
                score += 1
                bits.append("bonds down")
        if vix is not None and len(vix) >= 2:
            vdf = ohlcv_to_frame(vix)
            if vdf["close"].iloc[-1] < vdf["close"].iloc[-2]:
                score += 1
                bits.append("VIX falling")
        risk_on = score >= 2
        direction = Side.LONG if risk_on else Side.SHORT
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, score / 3 + 0.2),
            classification="risk_on" if risk_on else "risk_off",
            why=f"Macro backdrop is {'risk-on' if risk_on else 'risk-off'} ({', '.join(bits) or 'mixed'}).",
            why_now=f"Cross-asset score {int(score)}/3.",
            invalidation=InvalidationRule(
                description="Macro risk backdrop flips", kind="internals"
            ),
            evidence_for=[
                ev(EK.INTERNAL, "risk_score", int(score), 0.5, direction, self.scanner_id)
            ],
        )
