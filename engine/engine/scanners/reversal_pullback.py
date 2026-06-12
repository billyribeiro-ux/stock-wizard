"""Reversal Master and Pullback Reason Classifier."""

from __future__ import annotations

from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, levels, make_result
from .base import ScanContext, Scanner


class ReversalMasterScanner(Scanner):
    scanner_id = "reversal_master"
    name = "Reversal Master"
    description = "High-probability top/bottom from exhaustion + volume climax + wick rejection."
    category = "structure"
    default_params = {"stretch_atr": 2.0, "wick_frac": 0.5, "min_rvol": 1.5}
    params_schema = {
        "type": "object",
        "properties": {
            "stretch_atr": {"type": "number", "default": 2.0},
            "wick_frac": {"type": "number", "default": 0.5},
            "min_rvol": {"type": "number", "default": 1.5},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None
        s = ctx.snapshot
        if df is None or len(df) < 20:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        dist = s.get("vwap.dist_atr") or 0.0
        rvol = s.get("rvol.20") or 0.0
        bar = df.iloc[-1]
        hi, lo, o, c = (
            float(bar["high"]),
            float(bar["low"]),
            float(bar["open"]),
            float(bar["close"]),
        )
        rng = hi - lo
        if rng <= 0:
            return flat(self, ctx, "no_reversal", "No range on the last bar.")
        upper_wick = (hi - max(o, c)) / rng
        lower_wick = (min(o, c) - lo) / rng
        wf, st, mr = self.params["wick_frac"], self.params["stretch_atr"], self.params["min_rvol"]

        if dist >= st and upper_wick >= wf and rvol >= mr:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=min(1.0, 0.4 + upper_wick * 0.3 + min(rvol / 3, 0.3)),
                classification="top",
                why="Exhaustion above VWAP with a climactic upper-wick rejection on high volume.",
                why_now=f"{dist:.1f} ATR extended, {upper_wick:.0%} upper wick, RVOL {rvol:.1f}.",
                invalidation=InvalidationRule(
                    description=f"Close above the rejection high {hi:.2f}",
                    kind="price",
                    level=hi,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "upper_wick",
                        round(upper_wick, 2),
                        0.4,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                    ev(
                        EK.PATTERN, "vwap_stretch", round(dist, 2), 0.3, Side.SHORT, self.scanner_id
                    ),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, Side.SHORT, self.scanner_id),
                ],
                level_map=levels(close=c, rejection_high=hi),
            )
        if dist <= -st and lower_wick >= wf and rvol >= mr:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=min(1.0, 0.4 + lower_wick * 0.3 + min(rvol / 3, 0.3)),
                classification="bottom",
                why="Exhaustion below VWAP with a climactic lower-wick rejection on high volume.",
                why_now=f"{dist:.1f} ATR extended, {lower_wick:.0%} lower wick, RVOL {rvol:.1f}.",
                invalidation=InvalidationRule(
                    description=f"Close below the rejection low {lo:.2f}",
                    kind="price",
                    level=lo,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "lower_wick",
                        round(lower_wick, 2),
                        0.4,
                        Side.LONG,
                        self.scanner_id,
                    ),
                    ev(EK.PATTERN, "vwap_stretch", round(dist, 2), 0.3, Side.LONG, self.scanner_id),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, Side.LONG, self.scanner_id),
                ],
                level_map=levels(close=c, rejection_low=lo),
            )
        return flat(self, ctx, "no_reversal", "No climactic reversal signature.")


class PullbackReasonClassifierScanner(Scanner):
    scanner_id = "pullback_classifier"
    name = "Pullback Reason Classifier"
    description = "Explains why a pullback is happening and rates continuation vs reversal."
    category = "structure"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None
        s = ctx.snapshot
        if df is None or len(df) < 25:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        trend = s.get("struct.trend") or 0.0
        if trend == 0.0:
            return flat(self, ctx, "no_trend", "No clear trend to pull back within.")
        close = s.get("price.close") or float(df["close"].iloc[-1])
        atr = s.get("atr.14") or 0.0
        poc = s.get("vp.poc")
        rvol = s.get("rvol.20") or 1.0
        near = 0.4 * atr if atr else 0.0

        reason, cont_prob = "profit_taking", 0.5
        if poc is not None and abs(close - poc) <= near:
            reason, cont_prob = "value_retest", 0.6
        elif rvol < 0.8:
            reason, cont_prob = "low_volume_pullback", 0.7
        elif rvol > 1.5:
            reason, cont_prob = "distribution_risk", 0.35
        direction = Side.LONG if trend > 0 else Side.SHORT
        triggered = cont_prob >= 0.6
        return make_result(
            self,
            ctx,
            triggered=triggered,
            direction=direction if triggered else None,
            score=cont_prob,
            classification=reason,
            why=f"Pullback in a {'up' if trend > 0 else 'down'}trend classified as {reason.replace('_', ' ')}.",
            why_now=f"RVOL {rvol:.1f}; continuation probability ≈ {cont_prob:.0%}.",
            invalidation=InvalidationRule(
                description="Pullback deepens into a trend reversal", kind="structure"
            ),
            evidence_for=[
                ev(EK.PATTERN, "pullback_reason", reason, 0.5, direction, self.scanner_id),
                ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, direction, self.scanner_id),
            ],
        )
