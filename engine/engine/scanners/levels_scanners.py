"""Level-based scanners: key reference levels, anchored VWAP, opening range, gaps."""

from __future__ import annotations

from ..features import levels as lv
from ..features import vwap as vwap_mod
from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, levels, make_result
from .base import ScanContext, Scanner


def _frame(ctx):
    return ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None


class KeyLevelScanner(Scanner):
    scanner_id = "key_levels"
    name = "Key Level Intelligence"
    description = "Tracks prior-day high/low/close and round numbers; flags reactions near them."
    category = "structure"
    default_params = {"near_atr": 0.4}
    params_schema = {
        "type": "object",
        "properties": {"near_atr": {"type": "number", "default": 0.4}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if df is None or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough data / ATR.")
        sl = lv.session_levels(df)
        if sl is None:
            return flat(self, ctx, "insufficient_data", "Session levels unavailable.")
        close = float(df["close"].iloc[-1])
        near = self.params["near_atr"] * atr
        candidates = {
            "prev_high": sl.prev_high,
            "prev_low": sl.prev_low,
            "prev_close": sl.prev_close,
            "round": lv.nearest_round_number(close),
        }
        for name, level in candidates.items():
            if level is None:
                continue
            if abs(close - level) <= near:
                direction = (
                    Side.LONG
                    if name in ("prev_low",)
                    else (Side.SHORT if name in ("prev_high",) else Side.NEUTRAL)
                )
                return make_result(
                    self,
                    ctx,
                    triggered=True,
                    direction=direction or None,
                    score=0.45,
                    classification=f"at_{name}",
                    why=f"Price is reacting at the {name.replace('_', ' ')} level {level:.2f}.",
                    why_now=f"Close {close:.2f} is within {self.params['near_atr']} ATR of {level:.2f}.",
                    invalidation=InvalidationRule(
                        description=f"Acceptance through {level:.2f}",
                        kind="price",
                        level=float(level),
                    ),
                    evidence_for=[
                        ev(
                            EK.LEVEL,
                            name,
                            round(level, 2),
                            0.5,
                            direction or Side.NEUTRAL,
                            self.scanner_id,
                        )
                    ],
                    level_map=levels(close=close, level=float(level)),
                )
        return flat(self, ctx, "no_level_reaction", "Price not near a key level.")


class AnchoredVwapScanner(Scanner):
    scanner_id = "anchored_vwap"
    name = "Anchored VWAP Institutional Level"
    description = "Anchors VWAP from the most significant recent swing; flags reclaim/fail."
    category = "structure"
    default_params = {"near_atr": 0.4}
    params_schema = {
        "type": "object",
        "properties": {"near_atr": {"type": "number", "default": 0.4}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if df is None or len(df) < 30 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars / ATR.")
        # Anchor at the lowest low of the lookback (a natural institutional anchor).
        anchor_idx = int(df["low"].iloc[-100:].argmin()) + max(0, len(df) - 100)
        avwap = vwap_mod.anchored_vwap(df, anchor_idx)
        if avwap.empty or avwap.iloc[-1] != avwap.iloc[-1]:
            return flat(self, ctx, "insufficient_data", "AVWAP unavailable.")
        level = float(avwap.iloc[-1])
        close = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        near = self.params["near_atr"] * atr
        if prev < level <= close:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.5,
                classification="avwap_reclaim",
                why=f"Price reclaimed anchored VWAP at {level:.2f} (buyers regaining average price).",
                why_now="Close crossed back above the anchored VWAP.",
                invalidation=InvalidationRule(
                    description=f"Loss of AVWAP {level:.2f}",
                    kind="price",
                    level=level,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(EK.LEVEL, "avwap", round(level, 2), 0.5, Side.LONG, self.scanner_id)
                ],
                level_map=levels(close=close, avwap=level),
            )
        if prev > level >= close:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.5,
                classification="avwap_fail",
                why=f"Price lost anchored VWAP at {level:.2f} (sellers regaining control).",
                why_now="Close crossed back below the anchored VWAP.",
                invalidation=InvalidationRule(
                    description=f"Reclaim of AVWAP {level:.2f}",
                    kind="price",
                    level=level,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(EK.LEVEL, "avwap", round(level, 2), 0.5, Side.SHORT, self.scanner_id)
                ],
                level_map=levels(close=close, avwap=level),
            )
        if abs(close - level) <= near:
            return make_result(
                self,
                ctx,
                triggered=False,
                direction=None,
                score=0.3,
                classification="avwap_test",
                why=f"Price is testing anchored VWAP at {level:.2f}.",
                why_now="Awaiting a reclaim or fail.",
                invalidation=InvalidationRule(
                    description="Decisive break either way", kind="price"
                ),
                level_map=levels(close=close, avwap=level),
            )
        return flat(self, ctx, "away_from_avwap", "Price away from anchored VWAP.")


class OpeningRangeScanner(Scanner):
    scanner_id = "opening_range"
    name = "Opening Range & Session Timing"
    description = "Opening-range breakout/breakdown with session-timing context (intraday)."
    category = "structure"
    default_params = {"minutes": 30}
    params_schema = {
        "type": "object",
        "properties": {"minutes": {"type": "integer", "default": 30}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None or not ctx.timeframe.is_intraday:
            return flat(self, ctx, "not_intraday", "Opening range needs intraday bars.")
        sl = lv.session_levels(df, self.params["minutes"])
        if sl is None or sl.opening_range_high is None or sl.opening_range_low is None:
            return flat(self, ctx, "insufficient_data", "Opening range unavailable.")
        close = float(df["close"].iloc[-1])
        if close > sl.opening_range_high:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.5,
                classification="orb_long",
                why=f"Opening-range breakout above {sl.opening_range_high:.2f}.",
                why_now="Close cleared the opening-range high.",
                invalidation=InvalidationRule(
                    description=f"Back inside the range below {sl.opening_range_high:.2f}",
                    kind="price",
                    level=sl.opening_range_high,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(
                        EK.LEVEL,
                        "or_high",
                        round(sl.opening_range_high, 2),
                        0.5,
                        Side.LONG,
                        self.scanner_id,
                    )
                ],
                level_map=levels(
                    close=close, or_high=sl.opening_range_high, or_low=sl.opening_range_low
                ),
            )
        if close < sl.opening_range_low:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.5,
                classification="orb_short",
                why=f"Opening-range breakdown below {sl.opening_range_low:.2f}.",
                why_now="Close lost the opening-range low.",
                invalidation=InvalidationRule(
                    description=f"Back inside the range above {sl.opening_range_low:.2f}",
                    kind="price",
                    level=sl.opening_range_low,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(
                        EK.LEVEL,
                        "or_low",
                        round(sl.opening_range_low, 2),
                        0.5,
                        Side.SHORT,
                        self.scanner_id,
                    )
                ],
                level_map=levels(
                    close=close, or_high=sl.opening_range_high, or_low=sl.opening_range_low
                ),
            )
        return flat(self, ctx, "inside_range", "Price inside the opening range.")


class GapScanner(Scanner):
    scanner_id = "gap_scan"
    name = "Gap & Gap-Fill"
    description = "Classifies the session gap and tracks gap-and-go vs gap-fill behavior."
    category = "structure"
    default_params = {"min_gap_pct": 0.005}
    params_schema = {
        "type": "object",
        "properties": {"min_gap_pct": {"type": "number", "default": 0.005}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None:
            return flat(self, ctx, "insufficient_data", "No data.")
        sl = lv.session_levels(df)
        if sl is None or sl.gap_pct is None or sl.prev_close is None:
            return flat(self, ctx, "insufficient_data", "Gap data unavailable.")
        gap = sl.gap_pct
        if abs(gap) < self.params["min_gap_pct"]:
            return flat(self, ctx, "no_gap", "No meaningful gap.")
        close = float(df["close"].iloc[-1])
        filled = (gap > 0 and close <= sl.prev_close) or (gap < 0 and close >= sl.prev_close)
        direction = Side.LONG if gap > 0 else Side.SHORT
        if filled:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=(Side.SHORT if gap > 0 else Side.LONG),
                score=0.5,
                classification="gap_fill",
                why=f"The {gap:+.1%} gap has filled back to the prior close.",
                why_now=f"Price returned to {sl.prev_close:.2f}.",
                invalidation=InvalidationRule(
                    description="Trends away from the prior close", kind="price"
                ),
                evidence_for=[
                    ev(
                        EK.LEVEL,
                        "gap_pct",
                        round(gap, 4),
                        0.5,
                        Side.SHORT if gap > 0 else Side.LONG,
                        self.scanner_id,
                    )
                ],
                level_map=levels(close=close, prev_close=sl.prev_close),
            )
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=0.45,
            classification="gap_and_go",
            why=f"A {gap:+.1%} gap is holding (gap-and-go bias).",
            why_now=f"Price has not filled back to {sl.prev_close:.2f}.",
            invalidation=InvalidationRule(
                description=f"Gap fills to {sl.prev_close:.2f}",
                kind="price",
                level=sl.prev_close,
                comparator="lt" if gap > 0 else "gt",
            ),
            evidence_for=[ev(EK.LEVEL, "gap_pct", round(gap, 4), 0.45, direction, self.scanner_id)],
            level_map=levels(close=close, prev_close=sl.prev_close),
        )
