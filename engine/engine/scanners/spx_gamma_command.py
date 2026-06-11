"""SPX 0DTE Gamma Command scanner — the dedicated zero-DTE options engine.

Combines GEX-by-strike, gamma walls, the gamma-flip level, time-to-close, and price
context to classify each opportunity as scalp / reversal / top / bottom / gamma squeeze
/ hedge-wall rejection / no-trade.

Regime logic:
  • Spot ABOVE flip (positive gamma): dealers suppress volatility -> fade extremes,
    reversals at walls (mean-reversion).
  • Spot BELOW flip (negative gamma): dealers amplify moves -> momentum/scalps,
    squeezes through walls.
Defaults to SPY (yfinance SPX 0DTE coverage is thin); ``underlying`` is a param.
"""

from __future__ import annotations

from decimal import Decimal

from common.timeutils import minutes_to_close

from ..schemas import (
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    InvalidationRule,
    ScannerResult,
    Side,
)
from .base import ScanContext, Scanner


class SpxGammaCommandScanner(Scanner):
    scanner_id = "spx_gamma_command"
    name = "SPX 0DTE Gamma Command"
    description = (
        "Zero-DTE gamma engine: GEX walls, gamma flip, hedge pressure and time-of-day "
        "classify scalp vs reversal vs top/bottom vs squeeze vs no-trade."
    )
    category = "options_gamma"
    default_params = {
        "underlying": "SPY",
        "wall_atr": 0.5,
        "flip_band_atr": 0.35,
        "reversal_minutes": 60,
    }
    params_schema = {
        "type": "object",
        "properties": {
            "underlying": {
                "type": "string",
                "default": "SPY",
                "title": "Underlying (SPY proxy; SPX best-effort)",
            },
            "wall_atr": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 2.0,
                "default": 0.5,
                "title": "Wall proximity (ATR units)",
            },
            "flip_band_atr": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 2.0,
                "default": 0.35,
                "title": "Flip chop band (ATR units)",
            },
            "reversal_minutes": {
                "type": "integer",
                "minimum": 10,
                "maximum": 390,
                "default": 60,
                "title": "Min minutes-to-close to allow a reversal call",
            },
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        s = ctx.snapshot
        spot = s.get("gex.spot") or s.get("price.close")
        flip = s.get("gex.flip")
        total = s.get("gex.total")
        call_wall = s.get("gex.call_wall")
        put_wall = s.get("gex.put_wall")
        atr = s.get("atr.14") or 0.0
        rvol = s.get("rvol.20") or 0.0
        degraded = (s.get("gex.degraded") or 0.0) >= 1.0
        wall_atr = float(self._p("wall_atr", ctx))
        flip_band_atr = float(self._p("flip_band_atr", ctx))
        reversal_minutes = float(self._p("reversal_minutes", ctx))

        if spot is None or total is None or atr <= 0:
            return _flat(self, ctx, "insufficient_data", "No gamma profile / ATR available.")

        mins_left = minutes_to_close(ctx.as_of)
        positive_gamma = total >= 0 if flip is None else spot >= flip

        dist_call = ((call_wall - spot) / atr) if call_wall is not None else None
        dist_put = ((spot - put_wall) / atr) if put_wall is not None else None
        dist_flip = (abs(spot - flip) / atr) if flip is not None else None

        ev_for: list[EvidenceItem] = []
        ev_against: list[EvidenceItem] = []
        triggered = False
        direction: Side | None = None
        classification = "no_trade"

        near_call = dist_call is not None and 0 <= dist_call <= wall_atr
        near_put = dist_put is not None and 0 <= dist_put <= wall_atr
        in_chop = dist_flip is not None and dist_flip <= flip_band_atr

        if degraded:
            ev_against.append(
                _ev(EvidenceKind.DATA_QUALITY, "degraded_chain", 1.0, 0.5, Side.NEUTRAL)
            )
            classification = "no_trade"
        elif positive_gamma:
            # Positive gamma -> fade walls / mean-revert.
            allow_reversal = mins_left >= reversal_minutes
            if near_call:
                triggered, direction = True, Side.SHORT
                classification = "top" if allow_reversal else "scalp_short"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "call_wall_rejection", call_wall, 0.45, Side.SHORT)
                )
            elif near_put:
                triggered, direction = True, Side.LONG
                classification = "bottom" if allow_reversal else "scalp_long"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "put_wall_support", put_wall, 0.45, Side.LONG)
                )
            elif in_chop:
                classification = "no_trade"
                ev_against.append(
                    _ev(EvidenceKind.OPTIONS, "pinned_near_flip", flip, 0.3, Side.NEUTRAL)
                )
            else:
                # Drift back toward flip (value).
                direction = Side.SHORT if (flip is not None and spot > flip) else Side.LONG
                triggered = True
                classification = "reversal_short" if direction == Side.SHORT else "reversal_long"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "positive_gamma_meanrevert", total, 0.35, direction)
                )
        else:
            # Negative gamma -> momentum / squeezes.
            if dist_call is not None and dist_call < 0:  # spot above call wall
                triggered, direction, classification = True, Side.LONG, "gamma_squeeze"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "breach_call_wall", call_wall, 0.5, Side.LONG)
                )
            elif dist_put is not None and dist_put < 0:  # spot below put wall
                triggered, direction, classification = True, Side.SHORT, "gamma_squeeze"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "breach_put_wall", put_wall, 0.5, Side.SHORT)
                )
            elif in_chop:
                classification = "no_trade"
                ev_against.append(
                    _ev(EvidenceKind.OPTIONS, "near_flip_negative", flip, 0.25, Side.NEUTRAL)
                )
            else:
                direction = Side.LONG if (flip is not None and spot >= flip) else Side.SHORT
                triggered = True
                classification = "scalp_long" if direction == Side.LONG else "scalp_short"
                ev_for.append(
                    _ev(EvidenceKind.OPTIONS, "negative_gamma_momentum", total, 0.4, direction)
                )

        ev_for.append(
            _ev(
                EvidenceKind.OPTIONS,
                "regime",
                "positive_gamma" if positive_gamma else "negative_gamma",
                0.25,
                direction or Side.NEUTRAL,
            )
        )
        if rvol:
            ev_for.append(
                _ev(
                    EvidenceKind.VOLUME,
                    "rvol",
                    round(rvol, 2),
                    0.2 if rvol >= 1.2 else 0.1,
                    direction or Side.NEUTRAL,
                )
            )
        ev_for.append(
            _ev(EvidenceKind.TIME, "minutes_to_close", round(mins_left, 0), 0.15, Side.NEUTRAL)
        )

        score = self._score(
            triggered, positive_gamma, near_call, near_put, in_chop, rvol, total, degraded
        )

        invalidation = self._invalidation(
            direction, classification, spot, flip, call_wall, put_wall
        )

        evidence = EvidencePacket(
            why=self._why(positive_gamma, classification, spot, flip, call_wall, put_wall),
            why_now=self._why_now(classification, mins_left, near_call, near_put),
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
            ts=s.ts,
            triggered=triggered,
            direction=direction,
            score=score,
            classification=classification,
            levels=_levels(spot, flip, call_wall, put_wall),
            feature_refs={
                "gex.total": total,
                "gex.flip": flip,
                "gex.call_wall": call_wall,
                "gex.put_wall": put_wall,
                "atr.14": atr,
                "minutes_to_close": mins_left,
            },
            evidence=evidence,
            params=self.params,
        )

    def _score(
        self, triggered, positive_gamma, near_call, near_put, in_chop, rvol, total, degraded
    ):
        if degraded or not triggered:
            return 0.0
        base = 0.45
        if near_call or near_put:
            base += 0.2
        if rvol >= 1.2:
            base += 0.15
        if in_chop:
            base -= 0.25
        # Conviction from |total GEX| (log-scaled, capped).
        import math

        mag = min(0.2, math.log10(abs(total) + 1) / 50.0) if total else 0.0
        return max(0.0, min(1.0, base + mag))

    def _why(self, positive_gamma, classification, spot, flip, call_wall, put_wall):
        regime = (
            "positive-gamma (dealers suppress vol)"
            if positive_gamma
            else "negative-gamma (dealers amplify)"
        )
        flip_txt = f", flip {flip:.2f}" if flip is not None else ""
        return (
            f"Spot {spot:.2f} in {regime}{flip_txt}; call wall {call_wall}, put wall {put_wall}. "
            f"Setup classified as {classification.replace('_', ' ')}."
        )

    def _why_now(self, classification, mins_left, near_call, near_put):
        if near_call:
            return f"Price is testing the call (resistance) wall with {mins_left:.0f}m to close."
        if near_put:
            return f"Price is testing the put (support) wall with {mins_left:.0f}m to close."
        if classification == "gamma_squeeze":
            return "Spot breached a gamma wall in negative-gamma; hedging may accelerate the move."
        if classification == "no_trade":
            return "Evidence is balanced / pinned near the flip; standing aside."
        return f"Gamma regime favors this lean with {mins_left:.0f}m to close."

    def _invalidation(self, direction, classification, spot, flip, call_wall, put_wall):
        if direction == Side.SHORT and call_wall is not None:
            return InvalidationRule(
                description=f"Acceptance above the call wall {call_wall}",
                kind="price",
                level=float(call_wall),
                comparator="gt",
            )
        if direction == Side.LONG and put_wall is not None:
            return InvalidationRule(
                description=f"Breakdown below the put wall {put_wall}",
                kind="price",
                level=float(put_wall),
                comparator="lt",
            )
        if flip is not None:
            return InvalidationRule(
                description=f"Spot crosses the gamma flip {flip:.2f}",
                kind="options",
                level=float(flip),
                comparator="crosses",
            )
        return InvalidationRule(description="Regime flips", kind="options")


def _ev(kind, label, value, weight, direction):
    return EvidenceItem(
        kind=kind,
        label=label,
        value=value,
        weight=weight,
        direction=direction,
        source="spx_gamma_command",
    )


def _levels(spot, flip, call_wall, put_wall):
    out = {"spot": Decimal(str(round(spot, 4)))}
    if flip is not None:
        out["flip"] = Decimal(str(round(flip, 4)))
    if call_wall is not None:
        out["call_wall"] = Decimal(str(round(call_wall, 4)))
    if put_wall is not None:
        out["put_wall"] = Decimal(str(round(put_wall, 4)))
    return out


def _flat(scanner: Scanner, ctx: ScanContext, classification: str, why: str) -> ScannerResult:
    return ScannerResult(
        run_id=ctx.run_id,
        scanner_id=scanner.scanner_id,
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
            invalidation=InvalidationRule(description="n/a", kind="options"),
            confidence=0.0,
        ),
        params=scanner.params,
    )
