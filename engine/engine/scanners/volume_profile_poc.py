"""Volume Profile POC/VAH/VAL scanner.

Classifies where price sits relative to the auction's value area: acceptance or
rejection at the value-area edges, a POC retest, or balance (no trade). Volume
confirmation (RVOL) separates real acceptance from a fade.
"""

from __future__ import annotations

from decimal import Decimal

from ..schemas import (
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    InvalidationRule,
    ScannerResult,
    Side,
)
from .base import ScanContext, Scanner


class VolumeProfilePocScanner(Scanner):
    scanner_id = "volume_profile_poc"
    name = "Volume Profile POC/VAH/VAL"
    description = (
        "Builds the volume-by-price profile and classifies acceptance/rejection at the "
        "value-area edges, POC retests, and balance vs imbalance."
    )
    category = "volume"
    default_params = {"rvol_accept": 1.2, "poc_band_frac": 0.20}
    params_schema = {
        "type": "object",
        "properties": {
            "rvol_accept": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 5,
                "default": 1.2,
                "title": "RVOL needed to call acceptance",
            },
            "poc_band_frac": {
                "type": "number",
                "minimum": 0.05,
                "maximum": 0.5,
                "default": 0.20,
                "title": "POC balance band (fraction of value-area width)",
            },
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        s = ctx.snapshot
        poc, vah, val = s.get("vp.poc"), s.get("vp.vah"), s.get("vp.val")
        close = s.get("price.close")
        atr = s.get("atr.14") or 0.0
        rvol = s.get("rvol.20") or 0.0
        rvol_accept = float(self._p("rvol_accept", ctx))
        band_frac = float(self._p("poc_band_frac", ctx))

        if poc is None or vah is None or val is None or close is None:
            return _flat(self, ctx, "insufficient_data", "Profile could not be built.")

        va_width = max(vah - val, 1e-9)
        poc_band = band_frac * va_width

        triggered = False
        direction: Side | None = None
        classification = "balance"
        ev_for: list[EvidenceItem] = []
        ev_against: list[EvidenceItem] = []

        accepted = rvol >= rvol_accept
        if close > vah:
            if accepted:
                triggered, direction, classification = True, Side.LONG, "acceptance_above_value"
            else:
                triggered, direction, classification = True, Side.SHORT, "vah_rejection"
        elif close < val:
            if accepted:
                triggered, direction, classification = True, Side.SHORT, "breakdown_below_value"
            else:
                triggered, direction, classification = True, Side.LONG, "val_reclaim_watch"
        elif abs(close - poc) <= poc_band:
            classification = "poc_balance"
        else:
            classification = "inside_value"

        ev_for.append(
            EvidenceItem(
                kind=EvidenceKind.LEVEL,
                label="location_vs_value",
                value=classification,
                weight=0.4,
                direction=direction or Side.NEUTRAL,
                source="volume_profile",
            )
        )
        ev_for.append(
            EvidenceItem(
                kind=EvidenceKind.VOLUME,
                label="rvol",
                value=round(rvol, 2),
                weight=0.35 if accepted else 0.15,
                direction=direction or Side.NEUTRAL,
                source="volume_profile",
            )
        )
        if triggered and not accepted:
            ev_against.append(
                EvidenceItem(
                    kind=EvidenceKind.VOLUME,
                    label="weak_volume",
                    value=round(rvol, 2),
                    weight=0.3,
                    direction=Side.NEUTRAL,
                    source="volume_profile",
                )
            )

        score = _clip(
            0.45 * float(triggered)
            + 0.35 * float(accepted)
            + 0.2 * _proximity(close, atr, vah, val)
        )

        inval_level = val if direction == Side.LONG else vah
        invalidation = InvalidationRule(
            description=f"Close back inside value (beyond {'VAL' if direction == Side.LONG else 'VAH'} {inval_level:.2f})",
            kind="price",
            level=float(inval_level),
            comparator="lt" if direction == Side.LONG else "gt",
        )

        evidence = EvidencePacket(
            why=f"Price is {classification.replace('_', ' ')} (POC {poc:.2f}, VA {val:.2f}-{vah:.2f}).",
            why_now=(
                f"Close {close:.2f} {'accepted beyond' if accepted else 'tested'} the value-area edge."
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
            ts=s.ts,
            triggered=triggered,
            direction=direction,
            score=score,
            classification=classification,
            levels={
                "poc": Decimal(str(round(poc, 4))),
                "vah": Decimal(str(round(vah, 4))),
                "val": Decimal(str(round(val, 4))),
                "close": Decimal(str(round(close, 4))),
            },
            feature_refs={"vp.poc": poc, "vp.vah": vah, "vp.val": val, "rvol.20": rvol},
            evidence=evidence,
            params=self.params,
        )


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _proximity(close: float, atr: float, vah: float, val: float) -> float:
    if atr <= 0:
        return 0.0
    d = min(abs(close - vah), abs(close - val)) / atr
    return _clip(1.0 - d)


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
            invalidation=InvalidationRule(description="n/a", kind="price"),
            confidence=0.0,
        ),
        params=scanner.params,
    )
