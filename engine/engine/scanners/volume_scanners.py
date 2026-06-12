"""Volume-behavior scanners: accumulation/distribution, effort-vs-result divergence,
low-volume pullback continuation, volume dry-up reversal, relative-volume expansion.
"""

from __future__ import annotations

from ..features import volume as vol
from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


def _frame(ctx):
    return ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None


class AccumulationDistributionScanner(Scanner):
    scanner_id = "accumulation_distribution"
    name = "Subtle Accumulation / Distribution"
    description = (
        "Slow, repeated OBV/volume drift that hints at quiet accumulation or distribution."
    )
    category = "volume"
    default_params = {"window": 20, "threshold": 0.05}
    params_schema = {
        "type": "object",
        "properties": {
            "window": {"type": "integer", "default": 20},
            "threshold": {"type": "number", "default": 0.05},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None or len(df) < self.params["window"] + 2:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        slope = vol.obv_slope(df, self.params["window"])
        ud = ctx.snapshot.get("vol.updown")
        if slope is None:
            return flat(self, ctx, "insufficient_data", "OBV slope unavailable.")
        thr = self.params["threshold"]
        if slope > thr:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=min(1.0, slope * 4),
                classification="accumulation",
                why="OBV is drifting up over time — quiet accumulation under the surface.",
                why_now=f"OBV slope {slope:+.3f} with up/down volume {ud}.",
                invalidation=InvalidationRule(
                    description="OBV rolls over (distribution)", kind="volume"
                ),
                evidence_for=[
                    ev(EK.VOLUME, "obv_slope", round(slope, 3), 0.6, Side.LONG, self.scanner_id)
                ],
            )
        if slope < -thr:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=min(1.0, -slope * 4),
                classification="distribution",
                why="OBV is drifting down over time — quiet distribution under the surface.",
                why_now=f"OBV slope {slope:+.3f} with up/down volume {ud}.",
                invalidation=InvalidationRule(
                    description="OBV turns up (accumulation)", kind="volume"
                ),
                evidence_for=[
                    ev(EK.VOLUME, "obv_slope", round(slope, 3), 0.6, Side.SHORT, self.scanner_id)
                ],
            )
        return flat(self, ctx, "neutral_flow", "No clear accumulation/distribution drift.")


class VolumeDivergenceScanner(Scanner):
    scanner_id = "volume_divergence"
    name = "Volume Divergence / Effort-vs-Result"
    description = (
        "High volume with little price progress = absorption; flags effort/result mismatch."
    )
    category = "volume"
    default_params = {"absorption_ratio": 2.0}
    params_schema = {
        "type": "object",
        "properties": {"absorption_ratio": {"type": "number", "default": 2.0}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None or len(df) < 21:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        evr = vol.effort_vs_result(df)
        rvol = ctx.snapshot.get("rvol.20") or 1.0
        if evr is None:
            return flat(self, ctx, "insufficient_data", "Effort/result unavailable.")
        bar = df.iloc[-1]
        if evr >= self.params["absorption_ratio"] and rvol >= 1.3:
            # absorption against the bar direction -> fade
            direction = Side.SHORT if bar["close"] >= bar["open"] else Side.LONG
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=min(1.0, evr / 5),
                classification="absorption",
                why="Heavy volume produced little price progress — one side is absorbing.",
                why_now=f"Effort/result ratio {evr:.1f} with RVOL {rvol:.1f}.",
                invalidation=InvalidationRule(
                    description="Price breaks out of the absorption zone", kind="volume"
                ),
                evidence_for=[
                    ev(
                        EK.VOLUME,
                        "effort_vs_result",
                        round(evr, 2),
                        0.6,
                        direction,
                        self.scanner_id,
                    )
                ],
            )
        return flat(self, ctx, "no_divergence", "Effort and result are aligned.")


class LowVolumePullbackScanner(Scanner):
    scanner_id = "low_volume_pullback"
    name = "Low-Volume Pullback"
    description = "Healthy continuation: pullback on drying volume that holds above structure."
    category = "volume"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        if df is None or len(df) < 25:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        trend = s.get("struct.trend") or 0.0
        dry = vol.volume_dry_up(df)
        last_low = s.get("struct.last_low")
        close = float(df["close"].iloc[-1])
        if trend > 0 and dry and (last_low is None or close > last_low):
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.55,
                classification="pullback_continuation_long",
                why="Uptrend pullback on drying volume that holds structure — continuation setup.",
                why_now="Volume dried up while price held above the last higher-low.",
                invalidation=InvalidationRule(
                    description=f"Loss of the last higher-low {last_low}",
                    kind="structure",
                    level=float(last_low) if last_low else None,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(EK.VOLUME, "volume_dry_up", 1.0, 0.5, Side.LONG, self.scanner_id),
                    ev(EK.PATTERN, "uptrend", trend, 0.3, Side.LONG, self.scanner_id),
                ],
            )
        if trend < 0 and dry:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.5,
                classification="pullback_continuation_short",
                why="Downtrend bounce on drying volume — continuation lower likely.",
                why_now="Volume dried up on the counter-trend bounce.",
                invalidation=InvalidationRule(
                    description="Bounce gains volume and reclaims structure", kind="structure"
                ),
                evidence_for=[
                    ev(EK.VOLUME, "volume_dry_up", 1.0, 0.5, Side.SHORT, self.scanner_id)
                ],
            )
        return flat(self, ctx, "no_setup", "No low-volume pullback continuation.")


class VolumeDryUpReversalScanner(Scanner):
    scanner_id = "volume_dryup_reversal"
    name = "Volume Dry-Up Reversal"
    description = "Sellers/buyers exhausting after an extended move (bottoming/topping fuel)."
    category = "volume"
    default_params = {"stretch_atr": 2.0}
    params_schema = {
        "type": "object",
        "properties": {"stretch_atr": {"type": "number", "default": 2.0}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        if df is None or len(df) < 25:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        dist = s.get("vwap.dist_atr") or 0.0
        dry = vol.volume_dry_up(df)
        if dry and dist <= -self.params["stretch_atr"]:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.5,
                classification="dryup_bottom_watch",
                why="Extended below VWAP with sellers drying up — bottoming fuel.",
                why_now=f"Volume dried up while {dist:.1f} ATR below VWAP.",
                invalidation=InvalidationRule(
                    description="New low on rising volume", kind="volume"
                ),
                evidence_for=[ev(EK.VOLUME, "dry_up", 1.0, 0.5, Side.LONG, self.scanner_id)],
            )
        if dry and dist >= self.params["stretch_atr"]:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.5,
                classification="dryup_top_watch",
                why="Extended above VWAP with buyers drying up — topping fuel.",
                why_now=f"Volume dried up while {dist:.1f} ATR above VWAP.",
                invalidation=InvalidationRule(
                    description="New high on rising volume", kind="volume"
                ),
                evidence_for=[ev(EK.VOLUME, "dry_up", 1.0, 0.5, Side.SHORT, self.scanner_id)],
            )
        return flat(self, ctx, "no_dryup", "No dry-up reversal context.")


class RvolExpansionScanner(Scanner):
    scanner_id = "rvol_expansion"
    name = "Relative Volume Expansion"
    description = "Unusual participation versus the same-period historical baseline."
    category = "volume"
    default_params = {"min_rvol": 2.0}
    params_schema = {
        "type": "object",
        "properties": {"min_rvol": {"type": "number", "default": 2.0}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        rvol = ctx.snapshot.get("rvol.20")
        if rvol is None:
            return flat(self, ctx, "insufficient_data", "RVOL unavailable.")
        if rvol >= self.params["min_rvol"]:
            df = _frame(ctx)
            bar = df.iloc[-1]
            direction = Side.LONG if bar["close"] >= bar["open"] else Side.SHORT
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=min(1.0, rvol / 4),
                classification="rvol_expansion",
                why=f"Participation is {rvol:.1f}× the baseline — the move has real fuel.",
                why_now=f"RVOL {rvol:.1f} exceeded the {self.params['min_rvol']}× threshold.",
                invalidation=InvalidationRule(
                    description="Volume reverts to baseline", kind="volume"
                ),
                evidence_for=[
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.6, direction, self.scanner_id)
                ],
                feature_refs={"rvol.20": rvol},
            )
        return flat(self, ctx, "normal_volume", "Volume near baseline.")
