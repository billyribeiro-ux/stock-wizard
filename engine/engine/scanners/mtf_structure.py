"""Multi-Timeframe Market Structure scanner.

Tells the system whether a setup moves *with* or *against* higher-timeframe structure.
Triggers when the lower timeframe prints a Break of Structure / Change of Character in
the direction of the higher-timeframe trend.
"""

from __future__ import annotations

from ..features import atr as atr_mod
from ..features import price_structure as struct
from ..features.base import ohlcv_to_frame
from ..schemas import (
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    InvalidationRule,
    ScannerResult,
    Side,
)
from .base import ScanContext, Scanner


class MtfStructureScanner(Scanner):
    scanner_id = "mtf_structure"
    name = "Multi-Timeframe Market Structure"
    description = (
        "Maps HH/HL/LH/LL, BOS and CHoCH across timeframes; triggers when the lower "
        "timeframe breaks structure in the direction of the higher-timeframe trend."
    )
    category = "structure"
    default_params = {"swing_k": 2, "atr_period": 14}
    params_schema = {
        "type": "object",
        "properties": {
            "swing_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "default": 2,
                "title": "Swing pivot window (±k bars)",
            },
            "atr_period": {
                "type": "integer",
                "minimum": 5,
                "maximum": 50,
                "default": 14,
                "title": "ATR period",
            },
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        k = int(self._p("swing_k", ctx))
        atr_period = int(self._p("atr_period", ctx))

        if ctx.ohlcv is None or len(ctx.ohlcv) < 4 * k + 5:
            return self._flat(ctx, "insufficient_data", "Not enough bars to map structure.")

        ltf_df = ohlcv_to_frame(ctx.ohlcv)
        ltf = struct.classify_structure(ltf_df, k)
        a = atr_mod.atr_last(ltf_df, atr_period) or 0.0
        close = float(ltf_df["close"].iloc[-1])

        htf = None
        if ctx.htf_ohlcv is not None and len(ctx.htf_ohlcv) >= 4 * k + 5:
            htf = struct.classify_structure(ohlcv_to_frame(ctx.htf_ohlcv), k)
        htf_trend = htf.trend if htf else ltf.trend

        # Trigger: LTF BOS/CHoCH aligned with HTF trend.
        ltf_break = ltf.last_choch or ltf.last_bos
        triggered = False
        direction: Side | None = None
        classification = "no_trade"
        if htf_trend == "up" and ltf_break == "up":
            triggered, direction, classification = True, Side.LONG, "continuation_long"
        elif htf_trend == "down" and ltf_break == "down":
            triggered, direction, classification = True, Side.SHORT, "continuation_short"
        elif ltf.last_choch:
            # Counter-trend CHoCH: a possible early reversal, lower conviction.
            direction = Side.LONG if ltf.last_choch == "up" else Side.SHORT
            classification = "reversal_watch"

        ev_for: list[EvidenceItem] = []
        ev_against: list[EvidenceItem] = []
        agree = htf_trend == ltf.trend and ltf.trend != "range"
        ev_for.append(
            EvidenceItem(
                kind=EvidenceKind.PATTERN,
                label=f"htf_trend_{htf_trend}",
                value=htf_trend,
                weight=0.4,
                direction=_trend_side(htf_trend),
                source="mtf_structure",
            )
        )
        if ltf_break:
            ev_for.append(
                EvidenceItem(
                    kind=EvidenceKind.PATTERN,
                    label=f"ltf_{'choch' if ltf.last_choch else 'bos'}_{ltf_break}",
                    value=ltf_break,
                    weight=0.4,
                    direction=_trend_side(ltf_break),
                    source="mtf_structure",
                )
            )
        if not agree and ltf.trend != "range":
            ev_against.append(
                EvidenceItem(
                    kind=EvidenceKind.PATTERN,
                    label="timeframe_conflict",
                    value=f"{htf_trend} vs {ltf.trend}",
                    weight=0.3,
                    direction=Side.NEUTRAL,
                    source="mtf_structure",
                )
            )

        score = _clip(0.5 * float(triggered) + 0.3 * float(agree) + 0.2 * float(bool(ltf_break)))

        inval_level = ltf.last_swing_low if direction == Side.LONG else ltf.last_swing_high
        invalidation = InvalidationRule(
            description=(
                f"Close back beyond the broken swing ({inval_level})"
                if inval_level is not None
                else "Structure re-breaks against the signal"
            ),
            kind="structure",
            level=float(inval_level) if inval_level is not None else None,
            comparator="lt" if direction == Side.LONG else "gt",
        )

        evidence = EvidencePacket(
            why=(
                f"Higher-timeframe trend is {htf_trend}; lower timeframe "
                f"{'broke structure ' + ltf_break if ltf_break else 'has not confirmed'}."
            ),
            why_now=(
                f"LTF {'CHoCH' if ltf.last_choch else 'BOS'} {ltf_break} just printed."
                if ltf_break
                else "No fresh structure break; monitoring."
            ),
            evidence_for=ev_for,
            evidence_against=ev_against,
            invalidation=invalidation,
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
            levels=_levels(close, a, ltf),
            feature_refs={
                "struct.trend": ctx.snapshot.get("struct.trend"),
                "atr.14": a,
            },
            evidence=evidence,
            params=self.params,
        )

    def _flat(self, ctx: ScanContext, classification: str, why: str) -> ScannerResult:
        return ScannerResult(
            run_id=ctx.run_id,
            scanner_id=self.scanner_id,
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            ts=ctx.snapshot.ts,
            triggered=False,
            direction=None,
            score=0.0,
            classification=classification,
            evidence=EvidencePacket(
                why=why,
                why_now="—",
                invalidation=InvalidationRule(description="n/a", kind="structure"),
                confidence=0.0,
            ),
            params=self.params,
        )


def _trend_side(trend: str) -> Side:
    return {"up": Side.LONG, "down": Side.SHORT}.get(trend, Side.NEUTRAL)


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _levels(close: float, atr: float, ltf: struct.StructureState) -> dict:
    from decimal import Decimal

    out: dict[str, Decimal] = {"close": Decimal(str(round(close, 4)))}
    if ltf.last_swing_high is not None:
        out["swing_high"] = Decimal(str(round(ltf.last_swing_high, 4)))
    if ltf.last_swing_low is not None:
        out["swing_low"] = Decimal(str(round(ltf.last_swing_low, 4)))
    return out
