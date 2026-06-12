"""Price-action scanners: traps, liquidity sweeps, breakout quality, reversals,
trend exhaustion, momentum ignition, squeeze, failed moves, abnormal moves.

Each reads the FeatureSnapshot plus the recent bar window; all emit ScannerResult +
EvidencePacket via the shared helpers in ``_common``.
"""

from __future__ import annotations

import numpy as np

from ..features import squeeze as sq
from ..features.base import ohlcv_to_frame
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, levels, make_result
from .base import ScanContext, Scanner

_LB = 20


def _frame(ctx):
    return ohlcv_to_frame(ctx.ohlcv) if ctx.ohlcv is not None else None


def _prior_extremes(df, lookback=_LB):
    win = df.iloc[-(lookback + 1) : -1]
    return float(win["high"].max()), float(win["low"].min())


class LiquiditySweepScanner(Scanner):
    scanner_id = "liquidity_sweep"
    name = "Liquidity Sweep / Stop-Hunt"
    description = "Detects a wick beyond an obvious high/low that immediately fails back inside."
    category = "structure"
    default_params = {"lookback": _LB, "wick_atr": 0.5}
    params_schema = {
        "type": "object",
        "properties": {
            "lookback": {"type": "integer", "default": _LB},
            "wick_atr": {"type": "number", "default": 0.5},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if df is None or len(df) < self.params["lookback"] + 2 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        ph, pl = _prior_extremes(df, self.params["lookback"])
        bar = df.iloc[-1]
        hi, lo, close = float(bar["high"]), float(bar["low"]), float(bar["close"])
        rvol = ctx.snapshot.get("rvol.20") or 1.0
        up_sweep = hi > ph and close < ph  # swept highs, closed back below -> short
        dn_sweep = lo < pl and close > pl  # swept lows, closed back above -> long
        if dn_sweep:
            score = 0.4 + 0.2 * (rvol >= 1.2) + min(0.3, (pl - lo) / atr * 0.3)
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=score,
                classification="sweep_long",
                why="Lows were swept and immediately reclaimed.",
                why_now=f"Price wicked below {pl:.2f} and closed back above.",
                invalidation=InvalidationRule(
                    description=f"Close below the swept low {lo:.2f}",
                    kind="price",
                    level=lo,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(EK.PATTERN, "reclaim_low", round(pl, 2), 0.5, Side.LONG, self.scanner_id),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, Side.LONG, self.scanner_id),
                ],
                level_map=levels(close=close, swept_low=lo, level=pl),
            )
        if up_sweep:
            score = 0.4 + 0.2 * (rvol >= 1.2) + min(0.3, (hi - ph) / atr * 0.3)
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=score,
                classification="sweep_short",
                why="Highs were swept and immediately rejected.",
                why_now=f"Price wicked above {ph:.2f} and closed back below.",
                invalidation=InvalidationRule(
                    description=f"Close above the swept high {hi:.2f}",
                    kind="price",
                    level=hi,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(EK.PATTERN, "reject_high", round(ph, 2), 0.5, Side.SHORT, self.scanner_id),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, Side.SHORT, self.scanner_id),
                ],
                level_map=levels(close=close, swept_high=hi, level=ph),
            )
        return flat(self, ctx, "no_sweep", "No liquidity sweep detected on the last bar.")


class ShortTrapScanner(Scanner):
    scanner_id = "short_trap"
    name = "Short Trap"
    description = "Failed breakdown: sellers trapped below support/value, price reclaims."
    category = "structure"
    default_params = {"lookback": _LB}
    params_schema = {
        "type": "object",
        "properties": {"lookback": {"type": "integer", "default": _LB}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        atr = s.get("atr.14") or 0.0
        if df is None or len(df) < self.params["lookback"] + 3 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        level = s.get("vp.val") or s.get("struct.last_low")
        if level is None:
            _, level = _prior_extremes(df, self.params["lookback"])
        recent = df.iloc[-3:]
        broke = float(recent["low"].min()) < level
        close = float(df["close"].iloc[-1])
        reclaimed = close > level
        rvol = s.get("rvol.20") or 1.0
        if broke and reclaimed:
            score = 0.45 + 0.2 * (rvol >= 1.2) + 0.15 * (close - level > 0.25 * atr)
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=score,
                classification="short_trap_long",
                why="Sellers were trapped below support; price reclaimed the level.",
                why_now=f"Price broke below {level:.2f} then reclaimed it on the close.",
                invalidation=InvalidationRule(
                    description=f"Close back below {level:.2f}",
                    kind="price",
                    level=float(level),
                    comparator="lt",
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "failed_breakdown",
                        round(level, 2),
                        0.5,
                        Side.LONG,
                        self.scanner_id,
                    ),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.25, Side.LONG, self.scanner_id),
                ],
                level_map=levels(close=close, level=float(level)),
            )
        return flat(self, ctx, "no_trap", "No short-trap reclaim detected.")


class LongTrapScanner(Scanner):
    scanner_id = "long_trap"
    name = "Long Trap"
    description = "Failed breakout: buyers trapped above resistance/value, price rejects."
    category = "structure"
    default_params = {"lookback": _LB}
    params_schema = {
        "type": "object",
        "properties": {"lookback": {"type": "integer", "default": _LB}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        atr = s.get("atr.14") or 0.0
        if df is None or len(df) < self.params["lookback"] + 3 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        level = s.get("vp.vah") or s.get("struct.last_high")
        if level is None:
            level, _ = _prior_extremes(df, self.params["lookback"])
        recent = df.iloc[-3:]
        broke = float(recent["high"].max()) > level
        close = float(df["close"].iloc[-1])
        rejected = close < level
        rvol = s.get("rvol.20") or 1.0
        if broke and rejected:
            score = 0.45 + 0.2 * (rvol >= 1.2) + 0.15 * (level - close > 0.25 * atr)
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=score,
                classification="long_trap_short",
                why="Buyers were trapped above resistance; price rejected back below.",
                why_now=f"Price broke above {level:.2f} then failed back below on the close.",
                invalidation=InvalidationRule(
                    description=f"Close back above {level:.2f}",
                    kind="price",
                    level=float(level),
                    comparator="gt",
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "failed_breakout",
                        round(level, 2),
                        0.5,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.25, Side.SHORT, self.scanner_id),
                ],
                level_map=levels(close=close, level=float(level)),
            )
        return flat(self, ctx, "no_trap", "No long-trap rejection detected.")


class BreakoutQualityScanner(Scanner):
    scanner_id = "breakout_quality"
    name = "Breakout Quality"
    description = "Grades breakouts via range expansion, RVOL, and close location."
    category = "structure"
    default_params = {"lookback": _LB, "min_rvol": 1.3}
    params_schema = {
        "type": "object",
        "properties": {
            "lookback": {"type": "integer", "default": _LB},
            "min_rvol": {"type": "number", "default": 1.3},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        atr = s.get("atr.14") or 0.0
        if df is None or len(df) < self.params["lookback"] + 2 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        ph, _pl = _prior_extremes(df, self.params["lookback"])
        bar = df.iloc[-1]
        hi, lo, close = float(bar["high"]), float(bar["low"]), float(bar["close"])
        rng = hi - lo
        rvol = s.get("rvol.20") or 1.0
        close_loc = (close - lo) / rng if rng > 0 else 0.5
        if close > ph:
            quality = 0.3 + 0.3 * min(rvol / 2, 1) + 0.2 * close_loc + 0.2 * min(rng / atr / 1.5, 1)
            grade = "strong" if quality >= 0.7 else "weak"
            return make_result(
                self,
                ctx,
                triggered=quality >= 0.5,
                direction=Side.LONG,
                score=quality,
                classification=f"breakout_{grade}",
                why=f"Upside breakout above {ph:.2f}, graded {grade}.",
                why_now=f"Close {close:.2f} cleared the {self.params['lookback']}-bar high with RVOL {rvol:.1f}.",
                invalidation=InvalidationRule(
                    description=f"Close back below {ph:.2f}",
                    kind="price",
                    level=ph,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "range_expansion",
                        round(rng / atr, 2),
                        0.3,
                        Side.LONG,
                        self.scanner_id,
                    ),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, Side.LONG, self.scanner_id),
                    ev(
                        EK.PATTERN,
                        "close_location",
                        round(close_loc, 2),
                        0.2,
                        Side.LONG,
                        self.scanner_id,
                    ),
                ],
                level_map=levels(close=close, level=ph),
            )
        return flat(self, ctx, "no_breakout", "No fresh breakout on the last bar.")


class TrendExhaustionScanner(Scanner):
    scanner_id = "trend_exhaustion"
    name = "Trend Exhaustion"
    description = "Flags stretched moves far from VWAP/mean in ATR units (reversal watch)."
    category = "structure"
    default_params = {"stretch_atr": 2.5}
    params_schema = {
        "type": "object",
        "properties": {"stretch_atr": {"type": "number", "default": 2.5}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        s = ctx.snapshot
        dist = s.get("vwap.dist_atr")
        if dist is None:
            return flat(self, ctx, "insufficient_data", "No VWAP distance available.")
        stretch = self.params["stretch_atr"]
        if abs(dist) >= stretch:
            direction = Side.SHORT if dist > 0 else Side.LONG
            score = min(1.0, abs(dist) / (stretch * 2))
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=score,
                classification="exhaustion_watch",
                why=f"Price is stretched {dist:+.1f} ATR from VWAP — mean-reversion risk.",
                why_now=f"Distance from VWAP exceeded {stretch} ATR.",
                invalidation=InvalidationRule(
                    description="Price keeps extending in trend direction", kind="price"
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "vwap_distance_atr",
                        round(dist, 2),
                        0.6,
                        direction,
                        self.scanner_id,
                    )
                ],
                feature_refs={"vwap.dist_atr": dist},
            )
        return flat(self, ctx, "no_exhaustion", "Price not stretched enough for exhaustion.")


class MomentumIgnitionScanner(Scanner):
    scanner_id = "momentum_ignition"
    name = "Momentum Ignition"
    description = "Compression release with a volume impulse and range expansion."
    category = "structure"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        s = ctx.snapshot
        atr = s.get("atr.14") or 0.0
        if df is None or len(df) < 25 or atr <= 0:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        was_squeeze = sq.squeeze_on(df.iloc[:-1])
        now_squeeze = sq.squeeze_on(df)
        bar = df.iloc[-1]
        rng = float(bar["high"] - bar["low"])
        rvol = s.get("rvol.20") or 1.0
        released = was_squeeze and not now_squeeze
        expansion = rng > 1.4 * atr
        if released and expansion and rvol >= 1.3:
            direction = Side.LONG if bar["close"] >= bar["open"] else Side.SHORT
            score = 0.5 + 0.25 * min(rvol / 2, 1) + 0.25 * min(rng / atr / 2, 1)
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=score,
                classification="ignition_long" if direction == Side.LONG else "ignition_short",
                why="Volatility compression released with a volume-backed expansion bar.",
                why_now=f"Squeeze fired with {rng / atr:.1f} ATR range and RVOL {rvol:.1f}.",
                invalidation=InvalidationRule(
                    description="Expansion bar fully retraced", kind="price"
                ),
                evidence_for=[
                    ev(EK.PATTERN, "squeeze_release", 1.0, 0.4, direction, self.scanner_id),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.3, direction, self.scanner_id),
                ],
            )
        return flat(self, ctx, "no_ignition", "No compression-release ignition.")


class SqueezeCompressionScanner(Scanner):
    scanner_id = "squeeze_compression"
    name = "Squeeze & Compression"
    description = "Bollinger-inside-Keltner volatility squeeze — expansion watchlist."
    category = "volume"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None or len(df) < 25:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        on = sq.squeeze_on(df)
        bw = sq.bandwidth(df)
        if on:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=None,
                score=0.5,
                classification="squeeze_on",
                why="Bollinger Bands are inside the Keltner Channels — energy is coiling.",
                why_now=f"Bandwidth compressed to {bw:.3f}; a directional expansion is likely.",
                invalidation=InvalidationRule(
                    description="Squeeze releases (bands exit Keltner)", kind="price"
                ),
                evidence_for=[
                    ev(
                        EK.VOLUME,
                        "bandwidth",
                        round(bw or 0, 4),
                        0.5,
                        Side.NEUTRAL,
                        self.scanner_id,
                    )
                ],
            )
        return flat(self, ctx, "no_squeeze", "No active squeeze.")


class FailedMoveScanner(Scanner):
    scanner_id = "failed_move"
    name = "Failed Move"
    description = (
        "A breakout/breakdown that fails back through its level becomes reversal evidence."
    )
    category = "structure"
    default_params = {"lookback": _LB}
    params_schema = {
        "type": "object",
        "properties": {"lookback": {"type": "integer", "default": _LB}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        if df is None or len(df) < self.params["lookback"] + 4:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        ph, pl = _prior_extremes(df.iloc[:-2], self.params["lookback"])
        last3 = df.iloc[-3:]
        close = float(df["close"].iloc[-1])
        broke_up = float(last3["high"].max()) > ph and close < ph
        broke_dn = float(last3["low"].min()) < pl and close > pl
        if broke_up:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.55,
                classification="failed_breakout",
                why="Upside break failed back below resistance.",
                why_now=f"Price tagged above {ph:.2f} then closed back under.",
                invalidation=InvalidationRule(
                    description=f"Reclaim above {ph:.2f}", kind="price", level=ph, comparator="gt"
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "failed_breakout",
                        round(ph, 2),
                        0.55,
                        Side.SHORT,
                        self.scanner_id,
                    )
                ],
                level_map=levels(close=close, level=ph),
            )
        if broke_dn:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.55,
                classification="failed_breakdown",
                why="Downside break failed back above support.",
                why_now=f"Price tagged below {pl:.2f} then closed back over.",
                invalidation=InvalidationRule(
                    description=f"Loss of {pl:.2f}", kind="price", level=pl, comparator="lt"
                ),
                evidence_for=[
                    ev(
                        EK.PATTERN,
                        "failed_breakdown",
                        round(pl, 2),
                        0.55,
                        Side.LONG,
                        self.scanner_id,
                    )
                ],
                level_map=levels(close=close, level=pl),
            )
        return flat(self, ctx, "no_failure", "No failed move detected.")


class BiggerMoveScanner(Scanner):
    scanner_id = "bigger_move"
    name = "Bigger-Than-Expected Move Detector"
    description = "Flags abnormal moves via the z-score of the latest return vs history."
    category = "structure"
    default_params = {"z_threshold": 2.5, "lookback": 100}
    params_schema = {
        "type": "object",
        "properties": {
            "z_threshold": {"type": "number", "default": 2.5},
            "lookback": {"type": "integer", "default": 100},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        df = _frame(ctx)
        lb = self.params["lookback"]
        if df is None or len(df) < 30:
            return flat(self, ctx, "insufficient_data", "Not enough bars.")
        rets = np.log(df["close"] / df["close"].shift(1)).dropna()
        hist = rets.iloc[-lb:-1] if len(rets) > lb else rets.iloc[:-1]
        if len(hist) < 10 or hist.std() == 0:
            return flat(self, ctx, "insufficient_data", "Not enough return history.")
        z = (rets.iloc[-1] - hist.mean()) / hist.std()
        if abs(z) >= self.params["z_threshold"]:
            direction = Side.LONG if z > 0 else Side.SHORT
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=min(1.0, abs(z) / (self.params["z_threshold"] * 2)),
                classification="abnormal_move",
                why=f"The latest move is {z:+.1f}σ vs its own history — needs explanation.",
                why_now=f"Return z-score breached ±{self.params['z_threshold']}.",
                invalidation=InvalidationRule(
                    description="Move normalizes / fully retraces", kind="price"
                ),
                evidence_for=[
                    ev(EK.PATTERN, "return_zscore", round(z, 2), 0.6, direction, self.scanner_id)
                ],
                feature_refs={"return_z": float(z)},
            )
        return flat(self, ctx, "normal_move", "Latest move within normal range.")
